"""
대법원 판례 2만건 본문 포함 수집 → Vertex AI Search 임포트.

기존 fetch_drf_cases.py는 메타데이터만 수집했으나,
이 스크립트는 lawService.do로 판시사항/판결요지/판례내용 전문을 수집하여
Vertex AI Search 검색 품질을 극대화.

사용법:
    # 전체 파이프라인 (수집 → 변환 → 업로드 → 임포트)
    python scripts/fetch_prec_full.py

    # 단계별 실행
    python scripts/fetch_prec_full.py --step list      # 1단계: 목록 수집
    python scripts/fetch_prec_full.py --step detail     # 2단계: 본문 수집
    python scripts/fetch_prec_full.py --step transform  # 3단계: JSONL 변환
    python scripts/fetch_prec_full.py --step import     # 4단계: GCS 업로드 + 임포트

    # 수집 재개 (중단된 곳부터)
    python scripts/fetch_prec_full.py --step detail --resume
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

# DRF API
DRF_BASE = "http://www.law.go.kr/DRF"
OC = "choepeter"

# Output
OUTPUT_DIR = os.path.join(BASE_DIR, "vertex_expansion", "prec_full")
LIST_DIR = os.path.join(OUTPUT_DIR, "list")
DETAIL_DIR = os.path.join(OUTPUT_DIR, "detail")
JSONL_PATH = os.path.join(OUTPUT_DIR, "prec_full.jsonl")
PROGRESS_FILE = os.path.join(OUTPUT_DIR, "progress.json")

# GCS / Vertex
GCS_BUCKET = "gs://lawmadi-vertex-data"
GCS_PATH = f"{GCS_BUCKET}/prec_full.jsonl"
PROJECT_ID = "lawmadi-db"
LOCATION = "global"
DATA_STORE_ID = "lawmadi-legal-cache"

# 수집 설정
TARGET_COUNT = 20000
PAGE_SIZE = 100
DETAIL_DELAY = 0.4      # 본문 조회 간 딜레이 (초)
LIST_DELAY = 0.3         # 목록 조회 간 딜레이 (초)
MAX_CONTENT_LEN = 15000  # 판례내용 최대 길이 (chars)


def _api_get(url: str, retries: int = 3, delay: float = 1.0) -> dict | None:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "LawmadiOS/1.0")
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data
        except (urllib.error.URLError, urllib.error.HTTPError,
                json.JSONDecodeError, TimeoutError) as e:
            print(f"    API error (attempt {attempt+1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1))
    return None


def _make_doc_id(serial: str) -> str:
    raw = f"prec_full:{serial}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _save_progress(step: str, data: dict):
    progress = {}
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            progress = json.load(f)
    progress[step] = data
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def _load_progress(step: str) -> dict:
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f).get(step, {})
    return {}


# ─── 1단계: 대법원 판례 목록 수집 ───────────────────────────────

def step_list(limit: int = TARGET_COUNT):
    """lawSearch.do로 대법원 판례 목록(일련번호) 수집."""
    os.makedirs(LIST_DIR, exist_ok=True)
    total = 0
    page = 1

    print(f"\n[1/4] 대법원 판례 목록 수집 (목표: {limit}건)")
    print("  정렬: 최신순 (ddes)")

    all_serials = []

    while total < limit:
        url = (
            f"{DRF_BASE}/lawSearch.do?"
            f"OC={OC}&target=prec&type=JSON"
            f"&display={PAGE_SIZE}&page={page}"
            f"&sort=ddes"
        )
        data = _api_get(url)
        if not data:
            print(f"    page {page} 실패, 중단")
            break

        prec_search = data.get("PrecSearch", {})
        items = prec_search.get("prec", [])
        if not items:
            print(f"    page {page} 데이터 없음, 완료")
            break
        if isinstance(items, dict):
            items = [items]

        # 페이지별 저장
        out_path = os.path.join(LIST_DIR, f"page_{page:04d}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)

        for item in items:
            serial = item.get("판례일련번호", "")
            if serial:
                all_serials.append(str(serial))

        total += len(items)
        if page % 20 == 0:
            print(f"    page {page}: {total}건 수집")

        page += 1
        time.sleep(LIST_DELAY)

    # 일련번호 목록 저장
    all_serials = all_serials[:limit]
    serials_path = os.path.join(OUTPUT_DIR, "serials.json")
    with open(serials_path, "w") as f:
        json.dump(all_serials, f)

    _save_progress("list", {"total": len(all_serials), "pages": page - 1})
    print(f"  목록 수집 완료: {len(all_serials)}건")
    return all_serials


# ─── 2단계: 판례 본문 상세 수집 ─────────────────────────────────

def step_detail(resume: bool = False):
    """lawService.do로 각 판례의 본문(판시사항/판결요지/판례내용) 수집."""
    os.makedirs(DETAIL_DIR, exist_ok=True)

    serials_path = os.path.join(OUTPUT_DIR, "serials.json")
    if not os.path.exists(serials_path):
        print("  serials.json 없음. 먼저 --step list 실행 필요")
        return 0

    with open(serials_path, "r") as f:
        serials = json.load(f)

    print(f"\n[2/4] 판례 본문 수집 (총 {len(serials)}건)")

    success = 0
    skipped = 0
    fail = 0
    fail_serials = []

    for i, serial in enumerate(serials):
        out_path = os.path.join(DETAIL_DIR, f"{serial}.json")

        # 이미 수집된 파일이 있으면 스킵
        if os.path.exists(out_path):
            skipped += 1
            success += 1
            continue

        url = (
            f"{DRF_BASE}/lawService.do?"
            f"OC={OC}&target=prec&ID={serial}&type=JSON"
        )
        data = _api_get(url, retries=3, delay=2.0)

        if data and "PrecService" in data:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data["PrecService"], f, ensure_ascii=False, indent=2)
            success += 1
        else:
            fail += 1
            fail_serials.append(serial)

        done = i + 1
        if done % 100 == 0:
            elapsed_pct = done / len(serials) * 100
            print(f"    {done}/{len(serials)} ({elapsed_pct:.1f}%) — 성공: {success}, 스킵: {skipped}, 실패: {fail}")

        time.sleep(DETAIL_DELAY)

    # 실패 목록 저장
    if fail_serials:
        fail_path = os.path.join(OUTPUT_DIR, "failed_serials.json")
        with open(fail_path, "w") as f:
            json.dump(fail_serials, f)
        print(f"  실패 목록: {fail_path}")

    _save_progress("detail", {
        "success": success, "skipped": skipped, "fail": fail
    })
    print(f"  본문 수집 완료: 성공 {success} (스킵 {skipped}), 실패 {fail}")
    return success


# ─── 3단계: Vertex AI Search JSONL 변환 ─────────────────────────

def step_transform():
    """수집된 판례 본문을 고품질 JSONL로 변환."""
    if not os.path.isdir(DETAIL_DIR):
        print("  detail 디렉토리 없음")
        return 0

    print(f"\n[3/4] JSONL 변환")

    doc_count = 0
    total_bytes = 0

    with open(JSONL_PATH, "w", encoding="utf-8") as out:
        for fname in sorted(os.listdir(DETAIL_DIR)):
            if not fname.endswith(".json"):
                continue

            serial = fname.replace(".json", "")
            path = os.path.join(DETAIL_DIR, fname)

            try:
                with open(path, "r", encoding="utf-8") as f:
                    svc = json.load(f)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

            case_no = svc.get("사건번호", "")
            case_name = svc.get("사건명", "")
            court = svc.get("법원명", "")
            date = svc.get("선고일자", "")
            case_type = svc.get("사건종류명", "")
            verdict_type = svc.get("판결유형", "")
            court_code = str(svc.get("법원종류코드", ""))

            holding = svc.get("판시사항", "")
            summary = svc.get("판결요지", "")
            ref_articles = svc.get("참조조문", "")
            ref_cases = svc.get("참조판례", "")
            full_text = svc.get("판례내용", "")

            if not case_no and not holding:
                continue

            # 전원합의체 여부 감지
            is_en_banc = (
                "전원합의체" in full_text
                or "전원합의체" in holding
                or "전원합의체" in summary
            )

            doc_id = _make_doc_id(serial)

            # ── content 구성 (검색 품질 극대화) ──
            en_banc_tag = " [전원합의체]" if is_en_banc else ""
            content_parts = [
                f"[판례{en_banc_tag}] {case_name}",
                f"사건번호: {case_no}",
                f"법원: {court}",
                f"선고일자: {date}",
                f"사건종류: {case_type}",
                f"판결유형: {verdict_type}",
            ]

            if ref_articles:
                content_parts.append(f"참조조문: {ref_articles}")

            if holding:
                content_parts.append(f"판시사항: {holding}")

            if summary:
                content_parts.append(f"판결요지: {summary}")

            if ref_cases:
                content_parts.append(f"참조판례: {ref_cases}")

            if full_text:
                # 판례내용은 최대 길이 제한 적용
                content_parts.append(
                    f"판례내용: {full_text[:MAX_CONTENT_LEN]}"
                )

            content_text = "\n".join(content_parts)
            content_bytes = content_text.encode("utf-8")

            # ── structData (필터링/패싯용) ──
            keywords = " ".join(filter(None, [
                case_name, case_type, case_no, court,
                holding[:200] if holding else "",
            ]))

            doc = {
                "id": doc_id,
                "structData": {
                    "ssot_type": "precedent_full",
                    "law_name": case_name,
                    "label": "판례",
                    "target": "prec",
                    "endpoint": "lawService.do",
                    "case_no": case_no,
                    "court": court,
                    "court_code": court_code,
                    "date": date,
                    "case_type": case_type,
                    "verdict_type": verdict_type,
                    "serial": serial,
                    "keywords": keywords[:500],
                    "is_en_banc": is_en_banc,
                    "has_holding": bool(holding),
                    "has_summary": bool(summary),
                    "has_full_text": bool(full_text),
                    "key_articles_json": json.dumps(
                        [{"참조조문": ref_articles[:300]}] if ref_articles else [],
                        ensure_ascii=False,
                    ),
                    "key_precedents_json": json.dumps(
                        [{"참조판례": ref_cases[:300]}] if ref_cases else [],
                        ensure_ascii=False,
                    ),
                    "key_qa_json": "[]",
                    "qa_count": 0,
                    "article_count": 0,
                },
                "content": {
                    "mimeType": "text/plain",
                    "rawBytes": base64.b64encode(content_bytes).decode("ascii"),
                },
            }
            out.write(json.dumps(doc, ensure_ascii=False) + "\n")
            doc_count += 1
            total_bytes += len(content_bytes)

            if doc_count % 2000 == 0:
                print(f"    {doc_count}건 변환 ({total_bytes / 1024 / 1024:.1f} MB)")

    _save_progress("transform", {
        "doc_count": doc_count,
        "total_mb": round(total_bytes / 1024 / 1024, 1),
    })
    print(f"  JSONL 변환 완료: {doc_count}건, {total_bytes / 1024 / 1024:.1f} MB")
    print(f"  출력: {JSONL_PATH}")
    return doc_count


# ─── 4단계: GCS 업로드 + Vertex AI Search 임포트 ────────────────

def step_import():
    """JSONL을 GCS에 업로드하고 Vertex AI Search에 임포트."""
    if not os.path.exists(JSONL_PATH):
        print("  JSONL 파일 없음")
        return

    # 파일 크기 확인
    size_mb = os.path.getsize(JSONL_PATH) / 1024 / 1024
    with open(JSONL_PATH, "r") as f:
        line_count = sum(1 for _ in f)

    print(f"\n[4/4] GCS 업로드 + Vertex AI Search 임포트")
    print(f"  파일: {JSONL_PATH}")
    print(f"  문서: {line_count}건, {size_mb:.1f} MB")

    # GCS 업로드
    print(f"\n  GCS 업로드: {GCS_PATH}")
    result = subprocess.run(
        ["gsutil", "-o", "GSUtil:parallel_composite_upload_threshold=50M",
         "cp", JSONL_PATH, GCS_PATH],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  GCS 업로드 실패: {result.stderr}")
        sys.exit(1)
    print("  GCS 업로드 완료")

    # Vertex AI Search 임포트 (INCREMENTAL)
    print("\n  Vertex AI Search 임포트 시작 (INCREMENTAL)...")
    token_result = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True, text=True,
    )
    token = token_result.stdout.strip()

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
            op_name = result.get("name", "")
            print(f"  임포트 작업 시작됨: {op_name}")
            print("  (인덱싱 완료까지 수 분~수십 분 소요)")
            _save_progress("import", {
                "operation": op_name,
                "doc_count": line_count,
                "size_mb": round(size_mb, 1),
            })
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"  임포트 실패 ({e.code}): {body[:500]}")
    except Exception as e:
        print(f"  임포트 실패: {e}")


# ─── Main ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="대법원 판례 2만건 본문 수집 → Vertex AI Search"
    )
    parser.add_argument(
        "--step",
        choices=["list", "detail", "transform", "import", "all"],
        default="all",
        help="실행 단계 (기본: all)",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="중단된 곳부터 재개 (detail 단계)",
    )
    parser.add_argument(
        "--limit", type=int, default=TARGET_COUNT,
        help=f"수집 건수 (기본: {TARGET_COUNT})",
    )
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("대법원 판례 본문 수집 → Vertex AI Search")
    print(f"목표: {args.limit}건 (본문 포함 고품질)")
    print("=" * 60)

    if args.step in ("all", "list"):
        step_list(limit=args.limit)

    if args.step in ("all", "detail"):
        step_detail(resume=args.resume or args.step == "all")

    if args.step in ("all", "transform"):
        step_transform()

    if args.step in ("all", "import"):
        step_import()

    print("\n" + "=" * 60)
    progress = {}
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            progress = json.load(f)
    print("진행 상황:")
    for step, info in progress.items():
        print(f"  {step}: {info}")
    print("=" * 60)


if __name__ == "__main__":
    main()
