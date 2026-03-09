"""
지능형 법령검색 API(aiSearch)로 주요 법률 키워드별 조문 수집 → Vertex AI Search 임포트.

법령조문 + 연관법령을 함께 수집하여 데이터스토어 보강.

사용법:
    python scripts/fetch_ai_search_articles.py
    python scripts/fetch_ai_search_articles.py --step fetch
    python scripts/fetch_ai_search_articles.py --step transform
    python scripts/fetch_ai_search_articles.py --step import
"""

import json
import os
import sys
import time
import hashlib
import base64
import argparse
import subprocess
import urllib.request
import urllib.parse
import urllib.error

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DRF_BASE = "https://www.law.go.kr/DRF/lawSearch.do"
OC = os.getenv("LAWGO_DRF_OC", "choepeter")

OUTPUT_DIR = os.path.join(BASE_DIR, "vertex_expansion", "ai_search")
RAW_DIR = os.path.join(OUTPUT_DIR, "raw")
JSONL_PATH = os.path.join(OUTPUT_DIR, "ai_search.jsonl")

GCS_BUCKET = "gs://lawmadi-vertex-data"
GCS_PATH = f"{GCS_BUCKET}/ai_search.jsonl"
PROJECT_ID = "lawmadi-db"
LOCATION = "global"
DATA_STORE_ID = "lawmadi-legal-cache"

# 주요 법률 키워드 (일상적 법률 상담에서 빈출)
KEYWORDS = [
    # 민사/계약
    "임대차 보증금 반환", "전세 사기", "매매계약 해제", "손해배상 청구",
    "채권 추심", "보증인 책임", "소멸시효", "부당이득 반환",
    "계약금 위약금", "하자 담보", "불법행위 손해배상",
    # 부동산
    "등기 이전", "공인중개사 책임", "재건축 재개발", "분양권 전매",
    "토지 수용 보상", "건축 허가", "용도변경", "지역권 통행권",
    # 가사/가족
    "이혼 재산분할", "양육권 양육비", "상속 유류분", "유언 효력",
    "친권 면접교섭", "혼인 무효 취소", "성년후견", "가정폭력 보호처분",
    # 형사
    "뺑소니", "음주운전 처벌", "사기죄 구성요건", "횡령 배임",
    "명예훼손 모욕", "폭행 상해", "성범죄 처벌", "마약 처벌",
    "도박 처벌", "절도 강도", "특수 공무집행방해",
    # 노동
    "부당해고 구제", "퇴직금 산정", "최저임금", "산재 보상",
    "직장 내 괴롭힘", "비정규직 차별", "근로시간 초과", "해고 예고",
    # 행정
    "행정심판 청구", "행정소송 제기", "과태료 부과", "영업정지 취소",
    "정보공개 청구", "개인정보 보호", "공무원 징계",
    # 세무
    "양도소득세", "종합소득세", "부가가치세 환급", "상속세 증여세",
    "체납 처분", "가산세 감면",
    # 소비자/생활
    "소비자 보호 환불", "전자상거래 반품", "의료사고 손해배상",
    "교통사고 합의", "보험금 청구", "층간소음 분쟁",
    # 회사/상사
    "주주 권리", "이사 책임", "법인 설립", "합병 분할",
    # 지식재산
    "특허 침해", "상표권 보호", "저작권 침해",
    # 국제/외국인
    "외국인 체류 비자", "귀화 국적", "국제 입양",
]


def _api_get(url: str, retries: int = 2) -> dict | None:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "LawmadiOS/1.0")
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1)
    return None


def _make_doc_id(law_id: str, article_no: str) -> str:
    raw = f"aiSearch:{law_id}:{article_no}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def step_fetch():
    """aiSearch + aiRltLs로 키워드별 조문 수집."""
    os.makedirs(RAW_DIR, exist_ok=True)

    print(f"\n[1/3] 지능형 법령검색 수집 ({len(KEYWORDS)}개 키워드)")

    total_articles = 0
    seen_ids = set()

    for i, kw in enumerate(KEYWORDS):
        kw_encoded = urllib.parse.quote(kw)

        # aiSearch: 법령조문 (search=0)
        url = f"{DRF_BASE}?OC={OC}&target=aiSearch&type=JSON&search=0&query={kw_encoded}&display=50"
        data = _api_get(url)

        articles = []
        if data:
            ai = data.get("aiSearch", {})
            items = ai.get("법령조문", [])
            if isinstance(items, dict):
                items = [items]
            for item in items:
                aid = f"{item.get('법령ID','')}_{item.get('조문번호','')}"
                if aid not in seen_ids:
                    seen_ids.add(aid)
                    articles.append(item)

        # aiRltLs: 연관법령 (search=0)
        url2 = f"{DRF_BASE}?OC={OC}&target=aiRltLs&type=JSON&search=0&query={kw_encoded}"
        data2 = _api_get(url2)
        related = []
        if data2:
            ai2 = data2.get("aiRltLs", {})
            items2 = ai2.get("법령조문", [])
            if isinstance(items2, dict):
                items2 = [items2]
            for item in items2:
                aid = f"{item.get('법령ID','')}_{item.get('조문번호','')}"
                if aid not in seen_ids:
                    seen_ids.add(aid)
                    related.append(item)

        # 저장
        out_path = os.path.join(RAW_DIR, f"kw_{i:03d}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({
                "keyword": kw,
                "articles": articles,
                "related": related,
            }, f, ensure_ascii=False, indent=2)

        total_articles += len(articles) + len(related)

        if (i + 1) % 10 == 0:
            print(f"    {i+1}/{len(KEYWORDS)} 키워드 처리, 누적 조문: {total_articles}건")

        time.sleep(0.5)

    print(f"  수집 완료: {total_articles}건 (중복 제거 후)")
    return total_articles


def step_transform():
    """수집된 조문을 JSONL로 변환."""
    if not os.path.isdir(RAW_DIR):
        print("  raw 디렉토리 없음")
        return 0

    print(f"\n[2/3] JSONL 변환")

    doc_count = 0
    total_bytes = 0
    seen_ids = set()

    with open(JSONL_PATH, "w", encoding="utf-8") as out:
        for fname in sorted(os.listdir(RAW_DIR)):
            if not fname.endswith(".json"):
                continue

            path = os.path.join(RAW_DIR, fname)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            keyword = data.get("keyword", "")
            all_items = data.get("articles", []) + data.get("related", [])

            for item in all_items:
                law_id = item.get("법령ID", "")
                law_name = item.get("법령명", "")
                article_no = item.get("조문번호", "")
                article_branch = item.get("조문가지번호", "")
                article_title = item.get("조문제목", "")
                article_content = item.get("조문내용", "")
                enact_date = item.get("시행일자", "")

                if not law_id or not article_content:
                    continue

                doc_id = _make_doc_id(law_id, f"{article_no}-{article_branch}")
                if doc_id in seen_ids:
                    continue
                seen_ids.add(doc_id)

                content_text = (
                    f"[법령조문] {law_name} 제{article_no}조"
                    f"{f'의{article_branch}' if article_branch and article_branch != '0' else ''}"
                    f"{f' ({article_title})' if article_title else ''}\n"
                    f"시행일자: {enact_date}\n"
                    f"조문내용: {article_content}"
                )
                content_bytes = content_text.encode("utf-8")

                doc = {
                    "id": doc_id,
                    "structData": {
                        "ssot_type": "ai_search_article",
                        "law_name": law_name,
                        "label": "법령조문(AI검색)",
                        "target": "aiSearch",
                        "endpoint": "lawSearch.do",
                        "law_id": law_id,
                        "article_no": article_no,
                        "article_title": article_title or "",
                        "date": str(enact_date),
                        "keywords": f"{law_name} {article_title} {keyword}",
                        "key_articles_json": json.dumps(
                            [{"조문": f"제{article_no}조", "제목": article_title or ""}],
                            ensure_ascii=False,
                        ),
                        "key_article_texts_json": json.dumps(
                            [article_content[:500]],
                            ensure_ascii=False,
                        ),
                        "key_precedents_json": "[]",
                        "key_qa_json": "[]",
                        "qa_count": 0,
                        "article_count": 1,
                    },
                    "content": {
                        "mimeType": "text/plain",
                        "rawBytes": base64.b64encode(content_bytes).decode("ascii"),
                    },
                }
                out.write(json.dumps(doc, ensure_ascii=False) + "\n")
                doc_count += 1
                total_bytes += len(content_bytes)

    print(f"  JSONL 변환 완료: {doc_count}건, {total_bytes / 1024 / 1024:.1f} MB")
    return doc_count


def step_import():
    """GCS 업로드 + Vertex AI Search 임포트."""
    if not os.path.exists(JSONL_PATH):
        print("  JSONL 파일 없음")
        return

    size_mb = os.path.getsize(JSONL_PATH) / 1024 / 1024
    with open(JSONL_PATH, "r") as f:
        line_count = sum(1 for _ in f)

    print(f"\n[3/3] GCS 업로드 + Vertex AI Search 임포트")
    print(f"  파일: {line_count}건, {size_mb:.1f} MB")

    result = subprocess.run(
        ["gsutil", "cp", JSONL_PATH, GCS_PATH],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  GCS 업로드 실패: {result.stderr}")
        sys.exit(1)
    print("  GCS 업로드 완료")

    print("  Vertex AI Search 임포트 시작 (INCREMENTAL)...")
    token = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True, text=True,
    ).stdout.strip()

    import_url = (
        f"https://discoveryengine.googleapis.com/v1/projects/{PROJECT_ID}"
        f"/locations/{LOCATION}/collections/default_collection"
        f"/dataStores/{DATA_STORE_ID}/branches/default_branch"
        f"/documents:import"
    )
    payload = {
        "gcsSource": {"inputUris": [GCS_PATH]},
        "reconciliationMode": "INCREMENTAL",
    }

    req = urllib.request.Request(
        import_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "x-goog-user-project": PROJECT_ID,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            print(f"  임포트 작업 시작: {result.get('name', '')}")
    except urllib.error.HTTPError as e:
        print(f"  임포트 실패 ({e.code}): {e.read().decode('utf-8')[:500]}")
    except Exception as e:
        print(f"  임포트 실패: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="지능형 법령검색 조문 수집 → Vertex AI Search"
    )
    parser.add_argument(
        "--step",
        choices=["fetch", "transform", "import", "all"],
        default="all",
    )
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("지능형 법령검색(aiSearch) 조문 수집 → Vertex AI Search")
    print(f"키워드: {len(KEYWORDS)}개")
    print("=" * 60)

    if args.step in ("all", "fetch"):
        step_fetch()
    if args.step in ("all", "transform"):
        step_transform()
    if args.step in ("all", "import"):
        step_import()

    print("\n완료!")


if __name__ == "__main__":
    main()
