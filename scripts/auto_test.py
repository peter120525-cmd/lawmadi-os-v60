#!/usr/bin/env python3
"""
Lawmadi OS — 자동 품질 테스트 (30분 주기)
한글 1건 + 영문 1건 랜덤 테스트, 결과 자동 로그

Usage:
  python3 scripts/auto_test.py              # 단발 실행
  TEST_ADMIN_KEY=xxx python3 scripts/auto_test.py  # 관리자 키로 제한 우회
"""
import json
import os
import random
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

API_URL = "https://lawmadi-db.web.app/ask"
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
LOG_FILE = os.path.join(LOG_DIR, "auto_test.log")
TIMEOUT = 120
ADMIN_KEY = os.getenv("TEST_ADMIN_KEY", "")

KST = timezone(timedelta(hours=9))

# ── 한글 테스트 쿼리 풀 ──
KO_QUERIES = [
    "교통사고로 입원 중인데 상대방 보험사에서 합의금이 너무 적습니다. 어떻게 대응해야 하나요?",
    "회사에서 갑자기 해고 통보를 받았습니다. 부당해고 구제신청 절차와 비용을 알려주세요.",
    "이혼 소송 시 양육권과 재산분할은 어떻게 결정되나요? 절차와 비용이 궁금합니다.",
    "인터넷 쇼핑몰에서 사기를 당했습니다. 100만원 결제했는데 물건이 안 옵니다.",
    "임대인이 보증금을 돌려주지 않습니다. 내용증명 발송 후 소송까지의 절차를 알려주세요.",
    "명예훼손으로 고소하려 합니다. 온라인에서 허위사실을 유포당했는데 절차와 비용은?",
    "아파트 층간소음 문제로 이웃과 갈등 중입니다. 법적으로 어떤 조치가 가능한가요?",
    "개인회생 신청 조건과 절차가 궁금합니다. 빚이 5천만원 정도 있습니다.",
    "상속 포기와 한정승인의 차이점과 절차를 알려주세요. 아버지가 돌아가셨습니다.",
    "직장에서 성희롱을 당했습니다. 신고 절차와 법적 보호 방법을 알려주세요.",
]

# ── 영문 테스트 쿼리 풀 ──
EN_QUERIES = [
    "I got into a car accident in Seoul and the other driver was at fault. How do I claim compensation under Korean law?",
    "My employer has not paid my salary for 3 months. What legal actions can I take in Korea?",
    "I want to start a business in Korea as a foreigner. What are the visa and registration requirements?",
    "Someone is spreading false information about me online. Can I file a defamation lawsuit in Korea?",
    "I signed a lease contract but the landlord wants to evict me before the term ends. What are my rights?",
    "My Korean spouse and I are getting divorced. How is child custody decided under Korean law?",
    "I purchased a defective product from a Korean online store. What consumer protection laws apply?",
    "I received an unfair traffic ticket in Korea. How can I contest it?",
    "I want to apply for Korean permanent residency. What are the eligibility criteria and process?",
    "A business partner breached our contract. What are my legal options for damages in Korea?",
]


def call_api(query: str, lang: str = "") -> dict:
    """API 호출 + 응답시간 측정."""
    payload = {"query": query}
    if lang:
        payload["lang"] = lang

    headers = {"Content-Type": "application/json"}
    if ADMIN_KEY:
        headers["X-Admin-Key"] = ADMIN_KEY

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(API_URL, data=data, headers=headers, method="POST")

    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            elapsed_ms = int((time.time() - start) * 1000)
            return {"data": body, "ms": elapsed_ms, "error": None}
    except urllib.error.HTTPError as e:
        elapsed_ms = int((time.time() - start) * 1000)
        try:
            body = json.loads(e.read().decode("utf-8"))
        except Exception:
            body = {}
        return {"data": body, "ms": elapsed_ms, "error": f"HTTP {e.code}"}
    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        return {"data": {}, "ms": elapsed_ms, "error": str(e)}


def parse_result(result: dict) -> dict:
    """API 응답에서 주요 메트릭 추출."""
    d = result.get("data", {})
    meta = d.get("meta", {})
    return {
        "status": d.get("status", result.get("error", "ERROR")),
        "leader": d.get("leader", "?"),
        "specialty": d.get("leader_specialty", "?"),
        "length": len(d.get("response", "")),
        "quality": meta.get("quality_score", "?"),
        "has_law": meta.get("has_law_name", False),
        "has_article": meta.get("has_article", False),
        "ssot": meta.get("ssot_verified", False),
        "ms": result.get("ms", 0),
    }


def log(msg: str):
    """로그 파일 + 콘솔 동시 출력."""
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def run():
    os.makedirs(LOG_DIR, exist_ok=True)

    ko_query = random.choice(KO_QUERIES)
    en_query = random.choice(EN_QUERIES)
    ts = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")

    log("")
    log("═" * 65)
    log(f"[{ts}] Auto Test Run" + (" (admin)" if ADMIN_KEY else ""))
    log("═" * 65)

    # ── 한글 테스트 ──
    log(f"[KO] {ko_query}")
    ko_result = call_api(ko_query)
    ko = parse_result(ko_result)
    log(f"  → {ko['status']} | {ko['leader']} ({ko['specialty']}) | {ko['ms']}ms")
    log(f"    {ko['length']}자 | Q:{ko['quality']} | Law:{ko['has_law']} Art:{ko['has_article']} SSOT:{ko['ssot']}")

    # ── 영문 테스트 ──
    log(f"[EN] {en_query}")
    en_result = call_api(en_query, lang="en")
    en = parse_result(en_result)
    log(f"  → {en['status']} | {en['leader']} ({en['specialty']}) | {en['ms']}ms")
    log(f"    {en['length']}자 | Q:{en['quality']} | Law:{en['has_law']} Art:{en['has_article']} SSOT:{en['ssot']}")

    # ── 요약 ──
    passed = sum(1 for r in [ko, en] if r["status"] == "SUCCESS")
    failed = 2 - passed
    icon = "✅" if failed == 0 else "❌"
    summary = f"{icon} {passed}/2 PASS | KO:{ko['ms']}ms EN:{en['ms']}ms"
    log("─" * 65)
    log(f"  {summary}")

    # 콘솔 출력
    print(f"[{ts}] {summary}")
    print(f"  KO: {ko['status']} {ko['ms']}ms ({ko['leader']}) | EN: {en['status']} {en['ms']}ms ({en['leader']})")
    print(f"  Log: {LOG_FILE}")


if __name__ == "__main__":
    run()
