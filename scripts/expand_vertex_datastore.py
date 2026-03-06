"""
Vertex AI Search 데이터스토어 확장 스크립트.

3가지 데이터 소스를 JSONL로 변환하여 기존 데이터스토어에 추가 임포트:
  1. 조문 원문 (raw_v50 → 5,529개 법률의 전체 조문)
  2. 판례 Q&A (precedent_qa.jsonl → 880건)
  3. 일반 Q&A (all_qa_dataset.jsonl → 9,115건)

사용법:
    # 전체 실행 (변환 + 업로드 + 임포트)
    python scripts/expand_vertex_datastore.py

    # 변환만
    python scripts/expand_vertex_datastore.py --transform-only

    # 임포트만 (기존 JSONL 사용)
    python scripts/expand_vertex_datastore.py --import-only

    # 특정 소스만
    python scripts/expand_vertex_datastore.py --sources articles
    python scripts/expand_vertex_datastore.py --sources precedents,qa
"""

import json
import os
import sys
import argparse
import hashlib
import base64
import subprocess
import re
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Data sources
RAW_V50_DIR = "/home/peter120525/LawmadiLM/data/raw_v50"
PRECEDENT_QA_PATH = "/home/peter120525/LawmadiLM/data/processed/precedent_qa.jsonl"
ALL_QA_PATH = "/home/peter120525/LawmadiLM/data/processed/all_qa_dataset.jsonl"

# Output
OUTPUT_DIR = os.path.join(BASE_DIR, "vertex_expansion")
ARTICLES_JSONL = os.path.join(OUTPUT_DIR, "articles_expansion.jsonl")
PRECEDENTS_JSONL = os.path.join(OUTPUT_DIR, "precedents_expansion.jsonl")
QA_JSONL = os.path.join(OUTPUT_DIR, "qa_expansion.jsonl")
MERGED_JSONL = os.path.join(OUTPUT_DIR, "all_expansion.jsonl")

# GCS
GCS_BUCKET = "gs://lawmadi-vertex-data"
PROJECT_ID = "lawmadi-db"
LOCATION = "global"
DATA_STORE_ID = "lawmadi-legal-cache"


def _make_doc_id(prefix: str, *parts: str) -> str:
    raw = ":".join([prefix] + list(parts))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


# ─── 1. 조문 원문 변환 ───────────────────────────────────────

def transform_articles() -> int:
    """raw_v50 법률 파일에서 조문 원문을 추출하여 JSONL 변환."""
    if not os.path.isdir(RAW_V50_DIR):
        print(f"  raw_v50 디렉토리 없음: {RAW_V50_DIR}")
        return 0

    files = sorted([f for f in os.listdir(RAW_V50_DIR) if f.endswith("_raw.json")])
    print(f"  법률 파일: {len(files)}개")

    doc_count = 0
    with open(ARTICLES_JSONL, "w", encoding="utf-8") as out:
        for fi, fname in enumerate(files):
            law_name = fname.replace("_raw.json", "")
            path = os.path.join(RAW_V50_DIR, fname)

            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

            law_root = data.get("법령", {})
            units = law_root.get("조문", {}).get("조문단위", [])
            if not units:
                continue

            # 조문을 묶어서 법률당 1개 문서로 생성 (조문이 너무 많으면 분할)
            articles = []
            for u in units:
                if u.get("조문여부") == "전문":
                    continue
                num = u.get("조문번호", "")
                raw_content = u.get("조문내용", "")
                if isinstance(raw_content, list):
                    content = " ".join(str(x) for x in raw_content).strip()
                else:
                    content = str(raw_content).strip()
                if not content:
                    continue
                articles.append({
                    "num": num,
                    "text": content,
                })

            if not articles:
                continue

            # 법률당 최대 500조문씩 분할 (대형 법률 대응)
            chunk_size = 500
            for chunk_idx in range(0, len(articles), chunk_size):
                chunk = articles[chunk_idx:chunk_idx + chunk_size]
                suffix = f"_part{chunk_idx // chunk_size + 1}" if len(articles) > chunk_size else ""
                doc_id = _make_doc_id("art", law_name, str(chunk_idx))

                # content 텍스트: 조문 원문 전체
                content_lines = [f"[조문원문] {law_name}{suffix}"]
                for art in chunk:
                    content_lines.append(f"제{art['num']}조: {art['text'][:1000]}")

                content_text = "\n".join(content_lines)

                doc = {
                    "id": doc_id,
                    "structData": {
                        "ssot_type": "article_text",
                        "law_name": law_name,
                        "label": "조문원문",
                        "target": "law",
                        "endpoint": "lawService.do",
                        "keywords": "",
                        "key_articles_json": json.dumps(
                            [{"조문": f"제{a['num']}조"} for a in chunk[:20]],
                            ensure_ascii=False,
                        ),
                        "key_article_texts_json": json.dumps(
                            [a["text"][:500] for a in chunk[:20]],
                            ensure_ascii=False,
                        ),
                        "key_precedents_json": "[]",
                        "key_qa_json": "[]",
                        "qa_count": 0,
                        "article_count": len(chunk),
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

            if (fi + 1) % 500 == 0:
                print(f"    ... {fi + 1}/{len(files)} 파일 처리 ({doc_count}건)")

    print(f"  조문 원문: {doc_count}건 변환 완료")
    return doc_count


# ─── 2. 판례 Q&A 변환 ────────────────────────────────────────

def _extract_law_from_precedent(text: str) -> str:
    """판례 Q&A에서 관련 법률명 추출."""
    m = re.search(r'([가-힣]+(?:법|시행령|시행규칙|규정|규칙))', text)
    return m.group(1) if m else ""


def transform_precedents() -> int:
    """precedent_qa.jsonl → 판례 문서로 변환."""
    if not os.path.exists(PRECEDENT_QA_PATH):
        print(f"  판례 파일 없음: {PRECEDENT_QA_PATH}")
        return 0

    doc_count = 0
    # 판례 번호별로 그룹화
    prec_groups = defaultdict(list)

    with open(PRECEDENT_QA_PATH, "r", encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            instruction = d.get("instruction", "")
            output = d.get("output", "")

            # 판례 번호 추출
            m = re.search(r'(\d{4}[가-힣]+\d+)', instruction)
            case_id = m.group(1) if m else f"unknown_{doc_count}"

            prec_groups[case_id].append({
                "q": instruction,
                "a": output,
            })

    with open(PRECEDENTS_JSONL, "w", encoding="utf-8") as out:
        for case_id, qa_list in prec_groups.items():
            doc_id = _make_doc_id("prec_qa", case_id)

            # 첫 번째 Q&A에서 법률명 추출
            law_name = ""
            for qa in qa_list:
                law_name = _extract_law_from_precedent(qa["a"])
                if law_name:
                    break

            content_lines = [f"[판례] {case_id}"]
            if law_name:
                content_lines.append(f"관련법률: {law_name}")
            for qa in qa_list[:10]:
                content_lines.append(f"Q: {qa['q']}")
                content_lines.append(f"A: {qa['a'][:500]}")

            content_text = "\n".join(content_lines)

            doc = {
                "id": doc_id,
                "structData": {
                    "ssot_type": "precedent_qa",
                    "law_name": law_name or case_id,
                    "label": "판례Q&A",
                    "target": "prec",
                    "endpoint": "lawSearch.do",
                    "keywords": case_id,
                    "key_articles_json": "[]",
                    "key_article_texts_json": "[]",
                    "key_precedents_json": json.dumps(
                        [qa["a"][:300] for qa in qa_list[:5]],
                        ensure_ascii=False,
                    ),
                    "key_qa_json": json.dumps(
                        [{"q": qa["q"], "a": qa["a"][:300]} for qa in qa_list[:5]],
                        ensure_ascii=False,
                    ),
                    "qa_count": len(qa_list),
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

    print(f"  판례 Q&A: {doc_count}건 변환 완료 (원본 {sum(len(v) for v in prec_groups.values())}개 Q&A)")
    return doc_count


# ─── 3. 일반 Q&A 변환 ────────────────────────────────────────

def transform_qa() -> int:
    """all_qa_dataset.jsonl → Q&A 문서로 변환 (법률+조문별 그룹화)."""
    if not os.path.exists(ALL_QA_PATH):
        print(f"  QA 파일 없음: {ALL_QA_PATH}")
        return 0

    # 법률명 + 조문번호별 그룹화
    qa_groups = defaultdict(list)

    with open(ALL_QA_PATH, "r", encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            instruction = d.get("instruction", "")
            output = d.get("output", "")

            # "법률명 제N조" 패턴 추출
            m = re.search(r'([가-힣]+(?:\s+[가-힣]+)*(?:법|시행령|시행규칙|규정|규칙))\s*제(\d+)조', instruction)
            if m:
                key = f"{m.group(1)}__제{m.group(2)}조"
            else:
                # 법률명만이라도 추출
                m2 = re.search(r'([가-힣]+(?:법|시행령|시행규칙|규정|규칙))', instruction)
                if m2:
                    key = m2.group(1)
                else:
                    key = f"general__{hashlib.md5(instruction.encode()).hexdigest()[:8]}"

            qa_groups[key].append({
                "q": instruction,
                "a": output,
            })

    doc_count = 0
    with open(QA_JSONL, "w", encoding="utf-8") as out:
        for group_key, qa_list in qa_groups.items():
            doc_id = _make_doc_id("qa", group_key)

            # 법률명 추출
            parts = group_key.split("__")
            law_name = parts[0]
            article = parts[1] if len(parts) > 1 else ""

            content_lines = [f"[Q&A] {law_name} {article}".strip()]
            for qa in qa_list[:15]:
                content_lines.append(f"Q: {qa['q']}")
                content_lines.append(f"A: {qa['a'][:500]}")

            content_text = "\n".join(content_lines)

            doc = {
                "id": doc_id,
                "structData": {
                    "ssot_type": "qa",
                    "law_name": law_name,
                    "label": "Q&A",
                    "target": "law",
                    "endpoint": "lawSearch.do",
                    "keywords": article,
                    "key_articles_json": "[]",
                    "key_article_texts_json": "[]",
                    "key_precedents_json": "[]",
                    "key_qa_json": json.dumps(
                        [{"q": qa["q"], "a": qa["a"][:300]} for qa in qa_list[:5]],
                        ensure_ascii=False,
                    ),
                    "qa_count": len(qa_list),
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

    print(f"  일반 Q&A: {doc_count}건 변환 완료 (원본 {sum(len(v) for v in qa_groups.values())}개 Q&A)")
    return doc_count


# ─── 병합 + 업로드 + 임포트 ──────────────────────────────────

def merge_jsonl(sources: list) -> int:
    """개별 JSONL을 하나로 병합."""
    source_files = []
    if "articles" in sources and os.path.exists(ARTICLES_JSONL):
        source_files.append(ARTICLES_JSONL)
    if "precedents" in sources and os.path.exists(PRECEDENTS_JSONL):
        source_files.append(PRECEDENTS_JSONL)
    if "qa" in sources and os.path.exists(QA_JSONL):
        source_files.append(QA_JSONL)

    total = 0
    with open(MERGED_JSONL, "w", encoding="utf-8") as out:
        for sf in source_files:
            with open(sf, "r", encoding="utf-8") as f:
                for line in f:
                    out.write(line)
                    total += 1

    size_mb = os.path.getsize(MERGED_JSONL) / (1024 * 1024)
    print(f"\n  병합 완료: {total}건, {size_mb:.1f}MB → {MERGED_JSONL}")
    return total


def upload_to_gcs():
    """병합 JSONL → GCS 업로드."""
    gcs_path = f"{GCS_BUCKET}/expansion/all_expansion.jsonl"
    print(f"\n  GCS 업로드: {MERGED_JSONL} → {gcs_path}")
    result = subprocess.run(
        ["gcloud", "storage", "cp", MERGED_JSONL, gcs_path, "--project", PROJECT_ID],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  GCS 업로드 실패: {result.stderr}")
        sys.exit(1)
    print("  GCS 업로드 완료")
    return gcs_path


def import_to_datastore(gcs_path: str):
    """GCS JSONL → Vertex AI Search Data Store 임포트 (INCREMENTAL)."""
    print(f"\n  Data Store 임포트 시작 (INCREMENTAL)...")

    import_url = (
        f"https://discoveryengine.googleapis.com/v1/"
        f"projects/{PROJECT_ID}/locations/{LOCATION}/"
        f"collections/default_collection/dataStores/{DATA_STORE_ID}/"
        f"branches/default_branch/documents:import"
    )

    token_result = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True, text=True,
    )
    token = token_result.stdout.strip()

    import_body = {
        "gcsSource": {
            "inputUris": [gcs_path],
            "dataSchema": "document",
        },
        "reconciliationMode": "INCREMENTAL",
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
        print(f"  임포트 API 호출 실패: {curl_result.stderr}")
        sys.exit(1)

    resp = json.loads(curl_result.stdout)
    if "error" in resp:
        print(f"  임포트 에러: {resp['error'].get('message', resp['error'])}")
        sys.exit(1)

    op_name = resp.get("name", "")
    print(f"  임포트 시작됨: {op_name}")
    print("  (완료까지 수분~수십분 소요 — Cloud Console에서 진행 상황 확인)")
    return op_name


def main():
    parser = argparse.ArgumentParser(description="Vertex AI Search 데이터스토어 확장")
    parser.add_argument("--transform-only", action="store_true", help="JSONL 변환만 수행")
    parser.add_argument("--import-only", action="store_true", help="기존 JSONL로 임포트만 수행")
    parser.add_argument(
        "--sources", default="articles,precedents,qa",
        help="확장할 소스 (articles,precedents,qa 쉼표 구분, 기본: 전부)",
    )
    args = parser.parse_args()
    sources = [s.strip() for s in args.sources.split(",")]

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if args.import_only:
        if not os.path.exists(MERGED_JSONL):
            print(f"  {MERGED_JSONL} 없음. --transform-only 먼저 실행하세요.")
            sys.exit(1)
        gcs_path = upload_to_gcs()
        import_to_datastore(gcs_path)
        return

    print("=" * 60)
    print("Vertex AI Search 데이터스토어 확장")
    print("=" * 60)

    total = 0

    if "articles" in sources:
        print(f"\n[1/3] 조문 원문 변환...")
        total += transform_articles()

    if "precedents" in sources:
        print(f"\n[2/3] 판례 Q&A 변환...")
        total += transform_precedents()

    if "qa" in sources:
        print(f"\n[3/3] 일반 Q&A 변환...")
        total += transform_qa()

    if total == 0:
        print("\n변환된 문서가 없습니다.")
        sys.exit(1)

    merge_jsonl(sources)

    print(f"\n총 {total}건 문서 변환 완료")

    if args.transform_only:
        return

    gcs_path = upload_to_gcs()
    import_to_datastore(gcs_path)


if __name__ == "__main__":
    main()
