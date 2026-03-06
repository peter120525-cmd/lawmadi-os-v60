"""
Lawmadi OS v60 — 접근 권한 + 스트리밍 검증 테스트
1. /ask-expert 무료 사용자 차단 확인
2. /ask-expert 관리자 키 허용 확인
3. /ask-stream 기본 응답 품질 확인
"""
import json
import os
import time
import requests

BASE = "https://lawmadi-os-v60-938146962157.asia-northeast3.run.app"
ADMIN_KEY = os.getenv("TEST_ADMIN_KEY", "")

print("=" * 60)
print("접근 권한 + 스트리밍 검증 테스트")
print("=" * 60)

results = []

# ─── Test 1: /ask-expert WITHOUT admin key (should be FORBIDDEN) ───
print("\n--- Test 1: /ask-expert 무료 사용자 차단 ---")
try:
    r = requests.post(
        f"{BASE}/ask-expert",
        json={"query": "전세 보증금 반환 소송 절차를 알려주세요"},
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    data = r.json()
    status = data.get("status", "")
    if status == "FORBIDDEN":
        print(f"  [PASS] 무료 사용자 차단됨: {data.get('response', '')[:60]}")
        results.append(("expert_no_key", "PASS"))
    else:
        print(f"  [FAIL] 차단 안 됨! status={status}")
        results.append(("expert_no_key", "FAIL"))
except Exception as e:
    print(f"  [ERROR] {e}")
    results.append(("expert_no_key", "ERROR"))

# ─── Test 2: /ask-expert WITH admin key (should work) ───
print("\n--- Test 2: /ask-expert 관리자 키 허용 ---")
try:
    r = requests.post(
        f"{BASE}/ask-expert",
        json={"query": "전세 보증금 반환 소송 절차를 알려주세요"},
        headers={
            "Content-Type": "application/json",
            "X-Admin-Key": ADMIN_KEY,
        },
        timeout=120,
    )
    data = r.json()
    status = data.get("status", "")
    resp_len = len(data.get("response", ""))
    if status == "SUCCESS" and resp_len >= 1000:
        print(f"  [PASS] 관리자 접근 허용: status={status}, {resp_len}자")
        results.append(("expert_admin_key", "PASS"))
    else:
        print(f"  [FAIL] status={status}, {resp_len}자")
        results.append(("expert_admin_key", "FAIL"))
except Exception as e:
    print(f"  [ERROR] {e}")
    results.append(("expert_admin_key", "ERROR"))

# ─── Test 3: /ask-stream 응답 품질 (SSE 파싱) ───
print("\n--- Test 3: /ask-stream 법률 질문 응답 ---")
try:
    start = time.time()
    r = requests.post(
        f"{BASE}/ask-stream",
        json={"query": "임대차보증금을 돌려받지 못하고 있는데 어떻게 해야 하나요?"},
        headers={
            "Content-Type": "application/json",
            "X-Admin-Key": ADMIN_KEY,
        },
        stream=True,
        timeout=120,
    )
    full_text = ""
    done_data = None
    for line in r.iter_lines(decode_unicode=True):
        if not line:
            continue
        if line.startswith("data: "):
            try:
                payload = json.loads(line[6:])
                if "text" in payload:
                    full_text += payload["text"]
            except:
                pass
        elif line.startswith("event: done"):
            pass  # next line will have data
        elif line.startswith("event: "):
            pass

    # Parse last SSE done event
    elapsed = time.time() - start
    text_len = len(full_text)

    # Check for law references
    import re
    law_refs = re.findall(r'제\d+조', full_text)

    if text_len >= 1000 and len(law_refs) >= 1:
        print(f"  [PASS] stream 응답: {text_len}자, 법조문:{len(law_refs)}개, {elapsed:.1f}s")
        results.append(("stream_quality", "PASS"))
    elif text_len >= 500:
        print(f"  [WARN] stream 응답 짧음: {text_len}자, 법조문:{len(law_refs)}개, {elapsed:.1f}s")
        results.append(("stream_quality", "WARN"))
    else:
        print(f"  [FAIL] stream 응답: {text_len}자, {elapsed:.1f}s")
        if full_text:
            print(f"    내용: {full_text[:200]}")
        results.append(("stream_quality", "FAIL"))
except Exception as e:
    print(f"  [ERROR] {e}")
    results.append(("stream_quality", "ERROR"))

# ─── Test 4: /ask-stream FAIL_CLOSED 안 나는지 확인 ───
print("\n--- Test 4: /ask-stream 복합 법률질문 ---")
try:
    start = time.time()
    r = requests.post(
        f"{BASE}/ask-stream",
        json={"query": "직장에서 부당해고를 당했는데 퇴직금과 미지급 임금도 받지 못했습니다. 어떤 법적 절차를 밟아야 하나요?"},
        headers={
            "Content-Type": "application/json",
            "X-Admin-Key": ADMIN_KEY,
        },
        stream=True,
        timeout=120,
    )
    full_text = ""
    status = "UNKNOWN"
    for line in r.iter_lines(decode_unicode=True):
        if not line:
            continue
        if line.startswith("data: "):
            try:
                payload = json.loads(line[6:])
                if "text" in payload:
                    full_text += payload["text"]
                if "status" in payload:
                    status = payload["status"]
            except:
                pass

    elapsed = time.time() - start
    text_len = len(full_text)
    law_refs = re.findall(r'제\d+조', full_text)
    is_fail_closed = "실시간 법률 검증(SSOT) 시스템에 의해 차단" in full_text

    if not is_fail_closed and text_len >= 1000:
        print(f"  [PASS] stream 복합질문: {text_len}자, 법조문:{len(law_refs)}개, {elapsed:.1f}s")
        results.append(("stream_complex", "PASS"))
    elif is_fail_closed:
        print(f"  [FAIL] FAIL_CLOSED 발생!")
        results.append(("stream_complex", "FAIL_CLOSED"))
    else:
        print(f"  [FAIL] stream 응답: {text_len}자, {elapsed:.1f}s")
        results.append(("stream_complex", "FAIL"))
except Exception as e:
    print(f"  [ERROR] {e}")
    results.append(("stream_complex", "ERROR"))

# ─── 결과 요약 ───
print("\n" + "=" * 60)
print("결과 요약")
print("=" * 60)
pass_count = sum(1 for _, s in results if s == "PASS")
total = len(results)
for name, status in results:
    icon = "✅" if status == "PASS" else "⚠️" if status == "WARN" else "❌"
    print(f"  {icon} {name}: {status}")
print(f"\n  통과: {pass_count}/{total}")
