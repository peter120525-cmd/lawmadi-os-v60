#!/usr/bin/env python3
"""리더별 전문분야 주요 법령 관련 최신 대법원 판례 수집 → GCS 저장.

DRF lawSearch.do (target=prec) → 사건종류별 최신 판례 목록
→ 판례상세링크로 전문(판시사항+판결요지+참조조문) 수집
→ 리더 전문분야 매핑 → GCS 업로드

Usage:
    python scripts/prefetch_precedent_cache.py
"""
import os
import sys
import json
import time
import hashlib
import requests
import re
from collections import defaultdict

# ── 설정 ──
DRF_KEY = os.getenv("LAWGO_DRF_OC") or os.popen(
    "gcloud secrets versions access latest --secret=LAWGO_DRF_OC --project=lawmadi-db 2>/dev/null"
).read().strip()

DRF_SEARCH_URL = "https://www.law.go.kr/DRF/lawSearch.do"
DRF_SERVICE_URL = "https://www.law.go.kr/DRF/lawService.do"
GCS_BUCKET = "lawmadi-media"
GCS_PATH = "cache/precedent_cache.json"
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "precedent_cache.json")

# 사건종류코드 → 리더 매핑
CASE_TYPE_LEADERS = {
    "400101": {"name": "민사", "leaders": ["L01", "L06", "L08", "L10", "L11", "L12"]},
    "400102": {"name": "형사", "leaders": ["L22", "L25"]},
    "400103": {"name": "가사", "leaders": ["L41", "L57"]},
    "400106": {"name": "특허", "leaders": ["L26"]},
    "400107": {"name": "일반행정", "leaders": ["L31", "L27", "L32"]},
    "400108": {"name": "세무", "leaders": ["L20", "L24"]},
}

# 리더별 핵심 법령 키워드 (사건명 매칭용)
LEADER_KEYWORDS = {
    "L02": ["부동산", "토지", "건물", "소유권", "등기"],
    "L03": ["건설", "공사", "하자", "도급"],
    "L07": ["교통", "사고", "손해배상", "보험"],
    "L08": ["임대차", "보증금", "전세", "월세", "임차"],
    "L13": ["상법", "회사", "주식", "배당"],
    "L14": ["합병", "인수", "분할"],
    "L16": ["보험", "보험금"],
    "L17": ["국제", "무역", "수출"],
    "L21": ["정보통신", "개인정보", "해킹"],
    "L22": ["사기", "횡령", "배임", "폭행", "상해", "살인", "절도", "강도"],
    "L26": ["특허", "상표", "저작권", "실용신안"],
    "L27": ["환경", "폐기물", "오염"],
    "L30": ["해고", "임금", "근로", "퇴직", "노동"],
    "L31": ["행정", "처분", "허가", "인가", "취소"],
    "L32": ["공정거래", "독점", "담합", "카르텔"],
    "L34": ["개인정보", "정보보호"],
    "L38": ["소비자", "제조물", "하자"],
    "L41": ["이혼", "양육", "친권", "상속", "유류분"],
    "L43": ["산재", "산업재해", "업무상"],
    "L57": ["상속", "유언", "신탁"],
}

TOTAL_TARGET = 10000  # 전체 목표 1만건
PER_PAGE = 100
MAX_DETAIL_FETCH = 10000  # 상세 조회 최대 건수
session = requests.Session()
session.headers.update({"User-Agent": "LawmadiOS/v60 PrecedentPrefetch"})


def search_precedents(page=1, display=100):
    """DRF 판례 목록 조회 (최신순)."""
    params = {
        "OC": DRF_KEY,
        "target": "prec",
        "type": "JSON",
        "display": display,
        "page": page,
        "sort": "ddes",  # 최신순
    }
    try:
        r = session.get(DRF_SEARCH_URL, params=params, timeout=15)
        r.raise_for_status()
        d = r.json()
        items = d.get("PrecSearch", {}).get("prec", [])
        if isinstance(items, dict):
            items = [items]
        total = int(d.get("PrecSearch", {}).get("totalCnt", 0))
        return items, total
    except Exception as e:
        print(f"  ⚠️ 목록 조회 실패 (page={page}): {e}")
        return [], 0


def fetch_detail(prec_id):
    """판례 상세 조회 (판시사항+판결요지+참조조문+판례내용)."""
    params = {
        "OC": DRF_KEY,
        "target": "prec",
        "type": "JSON",
        "ID": prec_id,
    }
    try:
        r = session.get(DRF_SERVICE_URL, params=params, timeout=15)
        if r.status_code != 200:
            return None
        d = r.json()
        prec = d.get("PrecService", {})
        if not prec or "Law" in d:
            return None
        return prec
    except Exception:
        return None


def match_leaders(case_name, case_type_code):
    """사건명 + 사건종류코드로 관련 리더 매핑."""
    leaders = set()

    # 사건종류 기반 매핑
    ct = CASE_TYPE_LEADERS.get(case_type_code, {})
    if ct:
        leaders.update(ct.get("leaders", []))

    # 키워드 기반 매핑
    for leader_id, keywords in LEADER_KEYWORDS.items():
        for kw in keywords:
            if kw in case_name:
                leaders.add(leader_id)
                break

    return sorted(leaders) if leaders else ["L60"]  # 매칭 없으면 마디(L60)


def main():
    if not DRF_KEY:
        print("❌ LAWGO_DRF_OC 환경변수 없음")
        sys.exit(1)

    print(f"🔍 대법원 최신 판례 수집 시작 (목표: {TOTAL_TARGET}건)")
    print()

    # Step 1: 판례 목록 수집 (대법원만 필터)
    all_items = []
    page = 1
    while len(all_items) < TOTAL_TARGET * 2:  # 대법원 필터 후 충분한 양 확보
        items, total = search_precedents(page=page, display=PER_PAGE)
        if not items:
            break
        # 대법원 판례만 필터
        sc_items = [i for i in items if "대법원" in i.get("사건번호", "") or "대법원" in i.get("법원명", "")]
        all_items.extend(sc_items)
        print(f"  page {page}: {len(items)}건 조회, 대법원 {len(sc_items)}건 (누적: {len(all_items)}건)")
        if len(all_items) >= TOTAL_TARGET:
            break
        page += 1
        time.sleep(0.3)

    all_items = all_items[:TOTAL_TARGET]
    print(f"\n✅ 대법원 판례 {len(all_items)}건 목록 수집 완료")

    # 사건종류 분포
    type_dist = defaultdict(int)
    for item in all_items:
        type_dist[item.get("사건종류명", "기타")] += 1
    print(f"  사건종류 분포: {dict(type_dist)}")

    # Step 2: 상세 조회 (판시사항+판결요지)
    print(f"\n📖 판례 상세 수집 시작 ({min(len(all_items), MAX_DETAIL_FETCH)}건)...")
    cache = []
    success = 0
    fail = 0

    for idx, item in enumerate(all_items[:MAX_DETAIL_FETCH]):
        prec_id = item.get("판례일련번호", "")
        case_no = item.get("사건번호", "")
        case_name = item.get("사건명", "")
        case_type_code = item.get("사건종류코드", "")

        detail = fetch_detail(prec_id)

        if detail:
            ruling = detail.get("판시사항", "") or ""
            summary = detail.get("판결요지", "") or ""
            ref_articles = detail.get("참조조문", "") or ""
            ref_cases = detail.get("참조판례", "") or ""
            content = detail.get("판례내용", "") or ""

            # 핵심 정보만 저장 (전문은 너무 크므로 판시사항+요지+참조조문)
            leaders = match_leaders(case_name, case_type_code)

            entry = {
                "id": prec_id,
                "case_no": case_no,
                "case_name": case_name,
                "case_type": item.get("사건종류명", ""),
                "date": item.get("선고일자", ""),
                "verdict": item.get("판결유형", ""),
                "court": item.get("법원명", "") or "대법원",
                "ruling": ruling,  # 판시사항
                "summary": summary,  # 판결요지
                "ref_articles": ref_articles,  # 참조조문
                "ref_cases": ref_cases,  # 참조판례
                "leaders": leaders,
            }
            cache.append(entry)
            success += 1
        else:
            fail += 1

        if (idx + 1) % 50 == 0:
            print(f"  진행: {idx + 1}/{min(len(all_items), MAX_DETAIL_FETCH)} (성공: {success}, 실패: {fail})")
            time.sleep(0.5)  # rate limit 방지
        else:
            time.sleep(0.2)

    print(f"\n✅ 상세 수집 완료: 성공 {success}건, 실패 {fail}건")

    # Step 3: 리더별 통계
    leader_dist = defaultdict(int)
    for entry in cache:
        for lid in entry.get("leaders", []):
            leader_dist[lid] += 1
    print(f"\n📊 리더별 판례 매핑:")
    for lid in sorted(leader_dist.keys()):
        print(f"  {lid}: {leader_dist[lid]}건")

    # Step 4: 저장
    output = {
        "version": "v1.0",
        "generated": time.strftime("%Y-%m-%d %H:%M:%S KST", time.localtime()),
        "total": len(cache),
        "source": "법제처 DRF API (lawSearch.do + lawService.do, target=prec)",
        "leader_distribution": dict(leader_dist),
        "case_type_distribution": dict(type_dist),
        "precedents": cache,
    }

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    file_size = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)
    print(f"\n💾 로컬 저장: {OUTPUT_FILE} ({file_size:.1f}MB)")

    # Step 5: GCS 업로드
    try:
        from google.cloud import storage
        client = storage.Client(project="lawmadi-db")
        bucket = client.bucket(GCS_BUCKET)
        blob = bucket.blob(GCS_PATH)
        blob.upload_from_filename(OUTPUT_FILE, content_type="application/json")
        print(f"☁️  GCS 업로드: gs://{GCS_BUCKET}/{GCS_PATH}")
    except ImportError:
        # gsutil fallback
        os.system(f'gsutil -q cp {OUTPUT_FILE} gs://{GCS_BUCKET}/{GCS_PATH}')
        print(f"☁️  GCS 업로드 (gsutil): gs://{GCS_BUCKET}/{GCS_PATH}")
    except Exception as e:
        print(f"⚠️ GCS 업로드 실패: {e}")
        print(f"  수동 업로드: gsutil cp {OUTPUT_FILE} gs://{GCS_BUCKET}/{GCS_PATH}")

    print(f"\n🎉 완료! {len(cache)}건 판례 캐시 생성")


if __name__ == "__main__":
    main()
