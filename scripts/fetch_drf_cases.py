"""
DRF API에서 판례/헌재결정례를 수집하여 Vertex AI Search JSONL로 변환.

- 판례(prec): 최신 5,000건 (lawSearch.do, 메타데이터만 — 본문은 OPEN API 신청 필요)
- 헌재결정례(detc): 최신 3,000건 (lawSearch.do 목록 + lawService.do 상세)

사용법:
    # 전체 (수집 + 변환 + 업로드 + 임포트)
    python scripts/fetch_drf_cases.py

    # 수집만
    python scripts/fetch_drf_cases.py --fetch-only

    # 변환+업로드만 (기존 수집 데이터 사용)
    python scripts/fetch_drf_cases.py --import-only

    # 특정 소스만
    python scripts/fetch_drf_cases.py --sources prec
    python scripts/fetch_drf_cases.py --sources detc
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
OUTPUT_DIR = os.path.join(BASE_DIR, "vertex_expansion")
PREC_RAW_DIR = os.path.join(OUTPUT_DIR, "prec_raw")
DETC_RAW_DIR = os.path.join(OUTPUT_DIR, "detc_raw")
PREC_JSONL = os.path.join(OUTPUT_DIR, "prec_expansion.jsonl")
DETC_JSONL = os.path.join(OUTPUT_DIR, "detc_expansion.jsonl")
MERGED_JSONL = os.path.join(OUTPUT_DIR, "cases_expansion.jsonl")

# GCS / Vertex
GCS_BUCKET = "gs://lawmadi-vertex-data"
PROJECT_ID = "lawmadi-db"
LOCATION = "global"
DATA_STORE_ID = "lawmadi-legal-cache"

# Limits
PREC_LIMIT = 5000
DETC_LIMIT = 3000
PAGE_SIZE = 100  # DRF max per page


def _make_doc_id(prefix: str, *parts: str) -> str:
    raw = ":".join([prefix] + list(parts))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _api_get(url: str, retries: int = 3, delay: float = 1.0) -> dict | None:
    """DRF API GET with retry."""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "LawmadiOS/1.0")
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError) as e:
            print(f"    API error (attempt {attempt+1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1))
    return None


# ─── 1. 판례 수집 (메타데이터) ──────────────────────────────────

def fetch_precedents() -> int:
    """DRF lawSearch.do?target=prec 최신 5,000건 메타데이터 수집."""
    os.makedirs(PREC_RAW_DIR, exist_ok=True)
    total = 0
    page = 1

    print(f"  판례 메타데이터 수집 시작 (목표: {PREC_LIMIT}건)")

    while total < PREC_LIMIT:
        url = (
            f"{DRF_BASE}/lawSearch.do?"
            f"OC={OC}&target=prec&type=JSON"
            f"&display={PAGE_SIZE}&page={page}"
            f"&sort=date"  # 최신순
        )
        data = _api_get(url)
        if not data:
            print(f"    page {page} 실패, 중단")
            break

        # PrecSearch > prec (list)
        prec_search = data.get("PrecSearch", {})
        items = prec_search.get("prec", [])
        if not items:
            print(f"    page {page} 데이터 없음, 완료")
            break

        if isinstance(items, dict):
            items = [items]

        # 페이지별 저장
        out_path = os.path.join(PREC_RAW_DIR, f"prec_page_{page:04d}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)

        total += len(items)
        if page % 10 == 0:
            print(f"    page {page}: {total}건 수집")

        page += 1
        time.sleep(0.3)  # rate limit

    print(f"  판례 메타데이터: {total}건 수집 완료")
    return total


# ─── 2. 헌재결정례 수집 (목록 + 상세) ──────────────────────────

def fetch_detc_list() -> list[dict]:
    """DRF lawSearch.do?target=detc 최신 3,000건 목록 수집."""
    all_items = []
    page = 1

    print(f"  헌재결정례 목록 수집 시작 (목표: {DETC_LIMIT}건)")

    while len(all_items) < DETC_LIMIT:
        url = (
            f"{DRF_BASE}/lawSearch.do?"
            f"OC={OC}&target=detc&type=JSON"
            f"&display={PAGE_SIZE}&page={page}"
        )
        data = _api_get(url)
        if not data:
            print(f"    page {page} 실패, 중단")
            break

        detc_search = data.get("DetcSearch", data.get("LawSearch", {}))
        items = detc_search.get("Detc", detc_search.get("detc", []))
        if not items:
            print(f"    page {page} 데이터 없음, 완료")
            break

        if isinstance(items, dict):
            items = [items]

        all_items.extend(items)
        if page % 10 == 0:
            print(f"    page {page}: {len(all_items)}건")

        page += 1
        time.sleep(0.3)

    all_items = all_items[:DETC_LIMIT]
    print(f"  헌재결정례 목록: {len(all_items)}건 수집")
    return all_items


def fetch_detc_details(items: list[dict]) -> int:
    """각 헌재결정례 상세 조회 (lawService.do?target=detc)."""
    os.makedirs(DETC_RAW_DIR, exist_ok=True)
    success = 0
    fail = 0

    print(f"  헌재결정례 상세 수집 시작 ({len(items)}건)")

    for i, item in enumerate(items):
        serial = item.get("헌재결정례일련번호", "")
        if not serial:
            # try alternative keys
            serial = item.get("ID", item.get("id", ""))
        if not serial:
            fail += 1
            continue

        out_path = os.path.join(DETC_RAW_DIR, f"detc_{serial}.json")
        if os.path.exists(out_path):
            success += 1
            continue

        url = (
            f"{DRF_BASE}/lawService.do?"
            f"OC={OC}&target=detc&ID={serial}&type=JSON"
        )
        data = _api_get(url)
        if data:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            success += 1
        else:
            fail += 1

        if (i + 1) % 100 == 0:
            print(f"    {i+1}/{len(items)} 처리 (성공: {success}, 실패: {fail})")

        time.sleep(0.5)  # rate limit (상세 조회는 더 느리게)

    print(f"  헌재결정례 상세: 성공 {success}, 실패 {fail}")
    return success


# ─── 3. JSONL 변환 ────────────────────────────────────────────

def transform_precedents() -> int:
    """수집된 판례 메타데이터를 Vertex AI Search JSONL로 변환."""
    if not os.path.isdir(PREC_RAW_DIR):
        print("  판례 raw 데이터 없음")
        return 0

    doc_count = 0
    with open(PREC_JSONL, "w", encoding="utf-8") as out:
        for fname in sorted(os.listdir(PREC_RAW_DIR)):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(PREC_RAW_DIR, fname)
            with open(path, "r", encoding="utf-8") as f:
                items = json.load(f)

            for item in items:
                case_no = item.get("사건번호", "")
                case_name = item.get("사건명", "")
                court = item.get("법원명", "")
                date = item.get("선고일자", "")
                case_type = item.get("사건종류명", "")
                serial = item.get("판례일련번호", "")

                if not case_no:
                    continue

                doc_id = _make_doc_id("prec", serial or case_no)

                content = (
                    f"[판례] {case_name}\n"
                    f"사건번호: {case_no}\n"
                    f"법원: {court}\n"
                    f"선고일자: {date}\n"
                    f"사건종류: {case_type}\n"
                    f"판례일련번호: {serial}"
                )

                doc = {
                    "id": doc_id,
                    "structData": {
                        "ssot_type": "precedent",
                        "law_name": case_name,
                        "label": "판례",
                        "target": "prec",
                        "endpoint": "lawSearch.do",
                        "case_no": case_no,
                        "court": court,
                        "date": date,
                        "case_type": case_type,
                        "serial": serial,
                        "keywords": f"{case_name} {case_type}",
                        "key_articles_json": "[]",
                        "key_precedents_json": json.dumps(
                            [{"사건번호": case_no, "사건명": case_name}],
                            ensure_ascii=False,
                        ),
                        "key_qa_json": "[]",
                        "qa_count": 0,
                        "article_count": 0,
                    },
                    "content": {
                        "mimeType": "text/plain",
                        "rawBytes": base64.b64encode(
                            content.encode("utf-8")
                        ).decode("ascii"),
                    },
                }
                out.write(json.dumps(doc, ensure_ascii=False) + "\n")
                doc_count += 1

    print(f"  판례 JSONL: {doc_count}건 변환")
    return doc_count


def transform_detc() -> int:
    """수집된 헌재결정례 상세를 Vertex AI Search JSONL로 변환."""
    if not os.path.isdir(DETC_RAW_DIR):
        print("  헌재결정례 raw 데이터 없음")
        return 0

    doc_count = 0
    with open(DETC_JSONL, "w", encoding="utf-8") as out:
        for fname in sorted(os.listdir(DETC_RAW_DIR)):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(DETC_RAW_DIR, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

            # 헌재결정례 상세 구조 파싱 (DetcService 키)
            detc_info = data.get("DetcService", data.get("헌재결정례", data))
            if isinstance(detc_info, list):
                detc_info = detc_info[0] if detc_info else {}

            case_no = detc_info.get("사건번호", "")
            case_name = detc_info.get("사건명", "")
            decision_type = detc_info.get("사건종류명", "")
            decision_date = detc_info.get("종국일자", "")
            serial = detc_info.get("헌재결정례일련번호", fname.replace("detc_", "").replace(".json", ""))

            # 핵심 내용 필드
            holding = detc_info.get("판시사항", "")
            summary = detc_info.get("결정요지", "")
            ref_articles = detc_info.get("참조조문", "")
            ref_cases = detc_info.get("참조판례", "")
            full_text = detc_info.get("전문", "")

            if not case_no and not holding:
                continue

            doc_id = _make_doc_id("detc", str(serial))

            # content: 판시사항 + 결정요지 중심 (전문은 너무 길 수 있으므로 5000자 제한)
            content_parts = [f"[헌재결정례] {case_no} {case_name}"]
            if decision_date:
                content_parts.append(f"종국일자: {decision_date}")
            if decision_type:
                content_parts.append(f"사건종류: {decision_type}")
            if ref_articles:
                content_parts.append(f"참조조문: {ref_articles[:500]}")
            if holding:
                content_parts.append(f"판시사항: {holding[:2000]}")
            if summary:
                content_parts.append(f"결정요지: {summary[:3000]}")
            if ref_cases:
                content_parts.append(f"참조판례: {ref_cases[:500]}")
            if full_text and len("\n".join(content_parts)) < 3000:
                # 전문은 content가 부족할 때만 추가
                remaining = 8000 - len("\n".join(content_parts))
                if remaining > 500:
                    content_parts.append(f"전문(발췌): {full_text[:remaining]}")

            content_text = "\n".join(content_parts)

            doc = {
                "id": doc_id,
                "structData": {
                    "ssot_type": "constitutional_decision",
                    "law_name": case_name or case_no,
                    "label": "헌재결정례",
                    "target": "detc",
                    "endpoint": "lawService.do",
                    "case_no": case_no,
                    "decision_type": decision_type,
                    "date": decision_date,
                    "serial": str(serial),
                    "keywords": f"{case_name} {decision_type} {case_no}",
                    "key_articles_json": json.dumps(
                        [{"참조조문": ref_articles[:200]}] if ref_articles else [],
                        ensure_ascii=False,
                    ),
                    "key_precedents_json": json.dumps(
                        [{"참조판례": ref_cases[:200]}] if ref_cases else [],
                        ensure_ascii=False,
                    ),
                    "key_qa_json": "[]",
                    "qa_count": 0,
                    "article_count": 0,
                },
                "content": {
                    "mimeType": "text/plain",
                    "rawBytes": base64.b64encode(
                        content_text.encode("utf-8")
                    ).decode("ascii"),
                },
            }
            out.write(json.dumps(doc, ensure_ascii=False) + "\n")
            doc_count += 1

    print(f"  헌재결정례 JSONL: {doc_count}건 변환")
    return doc_count


# ─── 4. 머지 + 업로드 + 임포트 ────────────────────────────────

def merge_jsonl(sources: list[str]) -> int:
    """개별 JSONL을 하나로 머지."""
    total = 0
    with open(MERGED_JSONL, "w", encoding="utf-8") as out:
        for src in sources:
            path = PREC_JSONL if src == "prec" else DETC_JSONL
            if not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    out.write(line)
                    total += 1
    print(f"  머지: {total}건 → {MERGED_JSONL}")
    return total


def upload_to_gcs():
    """JSONL을 GCS에 업로드."""
    gcs_path = f"{GCS_BUCKET}/cases_expansion.jsonl"
    cmd = ["gsutil", "cp", MERGED_JSONL, gcs_path]
    print(f"  GCS 업로드: {gcs_path}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  GCS 업로드 실패: {result.stderr}")
        sys.exit(1)
    print("  GCS 업로드 완료")


def import_to_datastore():
    """Vertex AI Search 데이터스토어에 임포트."""
    gcs_path = f"{GCS_BUCKET}/cases_expansion.jsonl"
    cmd = [
        "gcloud", "alpha", "discovery-engine", "documents", "import",
        f"--project={PROJECT_ID}",
        f"--location={LOCATION}",
        f"--data-store={DATA_STORE_ID}",
        f"--gcs-uri={gcs_path}",
        "--reconciliation-mode=incremental",
    ]
    print(f"  Vertex AI Search 임포트 시작...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  임포트 실패: {result.stderr}")
        # Try alternative command
        cmd2 = [
            "curl", "-s", "-X", "POST",
            f"https://discoveryengine.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/dataStores/{DATA_STORE_ID}/branches/default_branch/documents:import",
            "-H", "Authorization: Bearer $(gcloud auth print-access-token)",
            "-H", "Content-Type: application/json",
            "-d", json.dumps({
                "gcsSource": {"inputUris": [gcs_path.replace("gs://", "gs://")]},
                "reconciliationMode": "INCREMENTAL",
            }),
        ]
        print("  대체 방법으로 임포트 시도...")
        result2 = subprocess.run(cmd2, capture_output=True, text=True, shell=False)
        print(f"  결과: {result2.stdout[:500]}")
    else:
        print(f"  임포트 완료: {result.stdout[:500]}")


# ─── Main ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="DRF 판례/헌재결정례 수집 → Vertex AI Search")
    parser.add_argument("--fetch-only", action="store_true", help="수집만")
    parser.add_argument("--import-only", action="store_true", help="변환+업로드만")
    parser.add_argument("--transform-only", action="store_true", help="변환만")
    parser.add_argument("--sources", type=str, default="prec,detc", help="소스 (prec,detc)")
    args = parser.parse_args()

    sources = [s.strip() for s in args.sources.split(",")]
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("DRF 판례/헌재결정례 → Vertex AI Search")
    print(f"소스: {sources}")
    print("=" * 60)

    # 1. 수집
    if not args.import_only and not args.transform_only:
        if "prec" in sources:
            print("\n[1/4] 판례 수집")
            fetch_precedents()

        if "detc" in sources:
            print("\n[2/4] 헌재결정례 수집")
            items = fetch_detc_list()
            if items:
                fetch_detc_details(items)

    if args.fetch_only:
        print("\n수집 완료 (--fetch-only)")
        return

    # 2. JSONL 변환
    print("\n[3/4] JSONL 변환")
    counts = {}
    if "prec" in sources:
        counts["prec"] = transform_precedents()
    if "detc" in sources:
        counts["detc"] = transform_detc()

    total = merge_jsonl(sources)
    print(f"\n변환 결과: {counts}")
    print(f"총 문서: {total}건")

    if args.transform_only:
        print("\n변환 완료 (--transform-only)")
        return

    # 3. 업로드 + 임포트
    if total > 0:
        print("\n[4/4] GCS 업로드 + Vertex AI Search 임포트")
        upload_to_gcs()
        import_to_datastore()

    print("\n완료!")


if __name__ == "__main__":
    main()
