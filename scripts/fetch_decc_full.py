"""
행정심판례 전수 수집 → Vertex AI Search 임포트.

법제처 DRF API로 행정심판례(~34,500건)를 본문 포함 수집.
건당 ~8KB, 전체 ~270MB 예상.

사용법:
    python scripts/fetch_decc_full.py
    python scripts/fetch_decc_full.py --step list
    python scripts/fetch_decc_full.py --step detail
    python scripts/fetch_decc_full.py --step transform
    python scripts/fetch_decc_full.py --step import
    python scripts/fetch_decc_full.py --limit 10000  # 최신 1만건만
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
import urllib.error

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# DRF API
DRF_BASE = "http://www.law.go.kr/DRF"
OC = "choepeter"

# Output
OUTPUT_DIR = os.path.join(BASE_DIR, "vertex_expansion", "decc_full")
LIST_DIR = os.path.join(OUTPUT_DIR, "list")
DETAIL_DIR = os.path.join(OUTPUT_DIR, "detail")
JSONL_PATH = os.path.join(OUTPUT_DIR, "decc_full.jsonl")
PROGRESS_FILE = os.path.join(OUTPUT_DIR, "progress.json")

# GCS / Vertex
GCS_BUCKET = "gs://lawmadi-vertex-data"
GCS_PATH = f"{GCS_BUCKET}/decc_full.jsonl"
PROJECT_ID = "lawmadi-db"
LOCATION = "global"
DATA_STORE_ID = "lawmadi-legal-cache"

# 수집 설정
DEFAULT_LIMIT = 35000
PAGE_SIZE = 100
DETAIL_DELAY = 0.4
LIST_DELAY = 0.3


def _api_get(url: str, retries: int = 3, delay: float = 1.0) -> dict | None:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "LawmadiOS/1.0")
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError,
                json.JSONDecodeError, TimeoutError) as e:
            print(f"    API error (attempt {attempt+1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1))
    return None


def _make_doc_id(serial: str) -> str:
    raw = f"decc_full:{serial}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _save_progress(step: str, data: dict):
    progress = {}
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            progress = json.load(f)
    progress[step] = data
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


# ─── 1단계: 목록 수집 ──────────────────────────────────────────

def step_list(limit: int):
    os.makedirs(LIST_DIR, exist_ok=True)
    total = 0
    page = 1
    all_serials = []

    print(f"\n[1/4] 행정심판례 목록 수집 (목표: {limit}건)")

    while total < limit:
        url = (
            f"{DRF_BASE}/lawSearch.do?"
            f"OC={OC}&target=decc&type=JSON"
            f"&display={PAGE_SIZE}&page={page}"
            f"&sort=ddes"
        )
        data = _api_get(url)
        if not data:
            print(f"    page {page} 실패, 중단")
            break

        decc_data = data.get("Decc", data.get("DeccSearch", data))
        items = decc_data.get("decc", [])
        if not items:
            print(f"    page {page} 데이터 없음, 완료")
            break
        if isinstance(items, dict):
            items = [items]

        out_path = os.path.join(LIST_DIR, f"page_{page:04d}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)

        for item in items:
            serial = item.get("행정심판재결례일련번호", "")
            if serial:
                all_serials.append(str(serial))

        total += len(items)
        if page % 20 == 0:
            print(f"    page {page}: {total}건 수집")

        page += 1
        time.sleep(LIST_DELAY)

    all_serials = all_serials[:limit]
    serials_path = os.path.join(OUTPUT_DIR, "serials.json")
    with open(serials_path, "w") as f:
        json.dump(all_serials, f)

    _save_progress("list", {"total": len(all_serials), "pages": page - 1})
    print(f"  목록 수집 완료: {len(all_serials)}건")
    return all_serials


# ─── 2단계: 본문 수집 ──────────────────────────────────────────

def step_detail():
    os.makedirs(DETAIL_DIR, exist_ok=True)

    serials_path = os.path.join(OUTPUT_DIR, "serials.json")
    if not os.path.exists(serials_path):
        print("  serials.json 없음. 먼저 --step list 실행")
        return 0

    with open(serials_path, "r") as f:
        serials = json.load(f)

    print(f"\n[2/4] 행정심판례 본문 수집 ({len(serials)}건)")

    success = 0
    skipped = 0
    fail = 0

    for i, serial in enumerate(serials):
        out_path = os.path.join(DETAIL_DIR, f"{serial}.json")
        if os.path.exists(out_path):
            skipped += 1
            success += 1
            continue

        url = (
            f"{DRF_BASE}/lawService.do?"
            f"OC={OC}&target=decc&ID={serial}&type=JSON"
        )
        data = _api_get(url, retries=3, delay=2.0)

        # API returns PrecService key for decc too
        svc = None
        if data:
            svc = data.get("DeccService", data.get("PrecService", None))

        if svc:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(svc, f, ensure_ascii=False, indent=2)
            success += 1
        else:
            fail += 1

        done = i + 1
        if done % 100 == 0:
            pct = done / len(serials) * 100
            print(f"    {done}/{len(serials)} ({pct:.1f}%) — 성공: {success}, 실패: {fail}")

        time.sleep(DETAIL_DELAY)

    _save_progress("detail", {"success": success, "skipped": skipped, "fail": fail})
    print(f"  본문 수집 완료: 성공 {success} (스킵 {skipped}), 실패 {fail}")
    return success


# ─── 3단계: JSONL 변환 ─────────────────────────────────────────

def step_transform():
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

            case_name = svc.get("사건명", "")
            case_no = svc.get("사건번호", "")
            disposal_date = svc.get("처분일자", "")
            decision_date = svc.get("의결일자", "")
            disposal_org = svc.get("처분청", "")
            decision_org = svc.get("재결청", "")
            decision_type = svc.get("재결례유형명", "")
            order = svc.get("주문", "")
            claim = svc.get("청구취지", "")
            reason = svc.get("이유", "")
            summary = svc.get("재결요지", "")

            if not case_no and not case_name:
                continue

            doc_id = _make_doc_id(serial)

            content_parts = [
                f"[행정심판례] {case_name}",
                f"사건번호: {case_no}",
                f"의결일자: {decision_date}",
                f"재결청: {decision_org}",
                f"처분청: {disposal_org}",
                f"재결유형: {decision_type}",
            ]
            if order:
                content_parts.append(f"주문: {order}")
            if claim:
                content_parts.append(f"청구취지: {claim}")
            if summary:
                content_parts.append(f"재결요지: {summary[:5000]}")
            if reason:
                content_parts.append(f"이유: {reason[:10000]}")

            content_text = "\n".join(content_parts)
            content_bytes = content_text.encode("utf-8")

            keywords = " ".join(filter(None, [
                case_name, case_no, decision_org, decision_type,
                summary[:200] if summary else "",
            ]))

            doc = {
                "id": doc_id,
                "structData": {
                    "ssot_type": "administrative_adjudication",
                    "law_name": case_name,
                    "label": "행정심판례",
                    "target": "decc",
                    "endpoint": "lawService.do",
                    "case_no": case_no,
                    "date": str(decision_date),
                    "serial": serial,
                    "disposal_org": disposal_org,
                    "decision_org": decision_org,
                    "decision_type": decision_type,
                    "keywords": keywords[:500],
                    "has_summary": bool(summary),
                    "has_reason": bool(reason),
                    "key_articles_json": "[]",
                    "key_precedents_json": "[]",
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
    return doc_count


# ─── 4단계: 업로드 + 임포트 ────────────────────────────────────

def step_import():
    if not os.path.exists(JSONL_PATH):
        print("  JSONL 파일 없음")
        return

    size_mb = os.path.getsize(JSONL_PATH) / 1024 / 1024
    with open(JSONL_PATH, "r") as f:
        line_count = sum(1 for _ in f)

    print(f"\n[4/4] GCS 업로드 + Vertex AI Search 임포트")
    print(f"  파일: {line_count}건, {size_mb:.1f} MB")

    print(f"  GCS 업로드: {GCS_PATH}")
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
            _save_progress("import", {
                "operation": result.get("name", ""),
                "doc_count": line_count,
            })
    except urllib.error.HTTPError as e:
        print(f"  임포트 실패 ({e.code}): {e.read().decode('utf-8')[:500]}")
    except Exception as e:
        print(f"  임포트 실패: {e}")


# ─── Main ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="행정심판례 수집 → Vertex AI Search"
    )
    parser.add_argument(
        "--step",
        choices=["list", "detail", "transform", "import", "all"],
        default="all",
    )
    parser.add_argument(
        "--limit", type=int, default=DEFAULT_LIMIT,
        help=f"수집 건수 (기본: {DEFAULT_LIMIT})",
    )
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("행정심판례 수집 → Vertex AI Search")
    print(f"목표: {args.limit}건")
    print("=" * 60)

    if args.step in ("all", "list"):
        step_list(args.limit)
    if args.step in ("all", "detail"):
        step_detail()
    if args.step in ("all", "transform"):
        step_transform()
    if args.step in ("all", "import"):
        step_import()

    print("\n완료!")


if __name__ == "__main__":
    main()
