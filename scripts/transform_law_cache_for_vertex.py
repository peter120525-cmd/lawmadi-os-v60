"""
law_cache_1~7.json → Vertex AI Search용 JSONL 변환 + GCS 업로드 + Data Store 임포트.

사용법:
    # 1) 변환만
    python scripts/transform_law_cache_for_vertex.py --transform-only

    # 2) 변환 + GCS 업로드 + 임포트 (전체)
    python scripts/transform_law_cache_for_vertex.py

    # 3) 기존 JSONL로 임포트만
    python scripts/transform_law_cache_for_vertex.py --import-only
"""

import json
import os
import sys
import argparse
import hashlib
import subprocess

# 프로젝트 루트 기준
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_FILES = [f"law_cache_{i}.json" for i in range(1, 8)]
OUTPUT_FILE = os.path.join(BASE_DIR, "law_cache_vertex.jsonl")

GCS_BUCKET = "gs://lawmadi-vertex-data"
GCS_PATH = f"{GCS_BUCKET}/law_cache_vertex.jsonl"
PROJECT_ID = "lawmadi-db"
LOCATION = "global"
DATA_STORE_ID = "lawmadi-legal-cache"


def _make_doc_id(ssot_type: str, law_name: str) -> str:
    """ssot_type + law_name → deterministic document ID (Vertex AI Search용)."""
    raw = f"{ssot_type}:{law_name}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _build_content_text(law_name: str, law_info: dict, ssot_type: str) -> str:
    """검색용 content 텍스트 생성 (시맨틱 검색 대상)."""
    parts = [f"[{ssot_type}] {law_name}"]

    # 키워드
    keywords = law_info.get("keywords", [])
    if keywords:
        parts.append(f"키워드: {', '.join(keywords[:20])}")

    # 핵심 조문 요약
    for art in law_info.get("key_articles", [])[:20]:
        조문 = art.get("조문", "")
        제목 = art.get("제목", "")
        if 조문:
            parts.append(f"조문: {조문} {제목}".strip())

    # 조문 원문
    for text in law_info.get("key_article_texts", [])[:10]:
        parts.append(f"원문: {text[:500]}")

    # 판례 요지
    for prec in law_info.get("key_precedents", [])[:5]:
        parts.append(f"판례: {prec[:300]}")

    # 대표 Q&A
    for qa in law_info.get("key_qa", [])[:5]:
        q = qa.get("q", "")
        a = qa.get("a", "")
        if q:
            parts.append(f"Q: {q}")
        if a:
            parts.append(f"A: {a[:300]}")

    return "\n".join(parts)


def transform() -> int:
    """law_cache JSON → JSONL 변환. 반환: 문서 수."""
    all_cache: dict = {}

    for cf in CACHE_FILES:
        path = os.path.join(BASE_DIR, cf)
        if not os.path.exists(path):
            print(f"⚠️  {cf} 미존재 — 스킵")
            continue
        print(f"📂 로딩: {cf} ...", end=" ", flush=True)
        with open(path, "r", encoding="utf-8") as f:
            part = json.load(f)
        for stype, sdata in part.items():
            if stype in all_cache:
                all_cache[stype]["entries"].update(sdata.get("entries", {}))
            else:
                all_cache[stype] = sdata
        print("✅")

    doc_count = 0
    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        for stype, type_data in all_cache.items():
            label = type_data.get("label", "")
            target = type_data.get("target", "")
            endpoint = type_data.get("endpoint", "")
            entries = type_data.get("entries", {})

            for law_name, law_info in entries.items():
                doc_id = _make_doc_id(stype, law_name)
                content_text = _build_content_text(law_name, law_info, stype)

                # Vertex AI Search: structData + content (content는 별도 oneof)
                doc = {
                    "id": doc_id,
                    "structData": {
                        "ssot_type": stype,
                        "law_name": law_name,
                        "label": label,
                        "target": target,
                        "endpoint": endpoint,
                        "keywords": ", ".join(law_info.get("keywords", [])[:20]),
                        "key_articles_json": json.dumps(
                            law_info.get("key_articles", [])[:20], ensure_ascii=False
                        ),
                        "key_article_texts_json": json.dumps(
                            law_info.get("key_article_texts", [])[:20], ensure_ascii=False
                        ),
                        "key_precedents_json": json.dumps(
                            law_info.get("key_precedents", [])[:10], ensure_ascii=False
                        ),
                        "key_qa_json": json.dumps(
                            law_info.get("key_qa", [])[:5], ensure_ascii=False
                        ),
                        "qa_count": law_info.get("qa_count", 0),
                    },
                    "content": {
                        "mimeType": "text/plain",
                        "rawBytes": __import__("base64").b64encode(
                            content_text.encode("utf-8")
                        ).decode("ascii"),
                    },
                }
                out.write(json.dumps(doc, ensure_ascii=False) + "\n")
                doc_count += 1

    print(f"\n✅ 변환 완료: {doc_count}개 문서 → {OUTPUT_FILE}")
    file_size_mb = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)
    print(f"   파일 크기: {file_size_mb:.1f} MB")
    return doc_count


def upload_to_gcs():
    """JSONL → GCS 업로드."""
    print(f"\n📤 GCS 업로드: {OUTPUT_FILE} → {GCS_PATH}")
    result = subprocess.run(
        ["gsutil", "cp", OUTPUT_FILE, GCS_PATH],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"❌ GCS 업로드 실패: {result.stderr}")
        sys.exit(1)
    print("✅ GCS 업로드 완료")


def import_to_datastore(mode: str = "FULL"):
    """GCS JSONL → Vertex AI Search Data Store 임포트."""
    if mode == "FULL":
        print("\n⚠️  FULL 모드: 기존 데이터스토어의 모든 문서가 교체됩니다.")
        confirm = input("   계속하시겠습니까? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("   임포트 취소됨.")
            return None
    print(f"\n📥 Data Store 임포트 시작 (mode={mode})...")

    import_url = (
        f"https://discoveryengine.googleapis.com/v1/"
        f"projects/{PROJECT_ID}/locations/{LOCATION}/"
        f"collections/default_collection/dataStores/{DATA_STORE_ID}/"
        f"branches/default_branch/documents:import"
    )

    # access token
    token_result = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True, text=True,
    )
    if token_result.returncode != 0:
        print(f"❌ 인증 토큰 획득 실패: {token_result.stderr}")
        sys.exit(1)
    token = token_result.stdout.strip()

    import_body = {
        "gcsSource": {
            "inputUris": [GCS_PATH],
            "dataSchema": "document",
        },
        "reconciliationMode": mode,
    }

    curl_result = subprocess.run(
        [
            "curl", "-s", "-X", "POST",
            "-H", f"Authorization: Bearer {token}",
            "-H", "Content-Type: application/json",
            "-H", f"X-Goog-User-Project: {PROJECT_ID}",
            import_url,
            "-d", json.dumps(import_body),
        ],
        capture_output=True, text=True,
    )

    if curl_result.returncode != 0:
        print(f"❌ 임포트 API 호출 실패: {curl_result.stderr}")
        sys.exit(1)

    resp = json.loads(curl_result.stdout)
    op_name = resp.get("name", "")
    print(f"✅ 임포트 시작됨: {op_name}")
    print("   (완료까지 수분 소요 — Cloud Console에서 진행 상황 확인)")
    return op_name


def main():
    parser = argparse.ArgumentParser(description="law_cache → Vertex AI Search 변환/임포트")
    parser.add_argument("--transform-only", action="store_true", help="JSONL 변환만 수행")
    parser.add_argument("--import-only", action="store_true", help="기존 JSONL로 임포트만 수행")
    parser.add_argument(
        "--mode", choices=["FULL", "INCREMENTAL"], default="FULL",
        help="reconciliationMode (FULL=전체교체, INCREMENTAL=추가만, 기본: FULL)",
    )
    args = parser.parse_args()

    if args.import_only:
        if not os.path.exists(OUTPUT_FILE):
            print(f"❌ {OUTPUT_FILE} 미존재. --transform-only 먼저 실행하세요.")
            sys.exit(1)
        upload_to_gcs()
        import_to_datastore(mode=args.mode)
        return

    doc_count = transform()
    if doc_count == 0:
        print("❌ 변환된 문서가 없습니다.")
        sys.exit(1)

    if args.transform_only:
        return

    upload_to_gcs()
    import_to_datastore(mode=args.mode)


if __name__ == "__main__":
    main()
