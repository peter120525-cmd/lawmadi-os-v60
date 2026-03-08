#!/bin/bash
# Lawmadi OS — 자동 품질 테스트 (30분 주기)
# 한글 1건 + 영문 1건 테스트, 결과 자동 로그
# Usage: bash scripts/auto_test.sh  (단발) 또는 cron으로 30분 주기

set -euo pipefail

API_URL="https://lawmadi-db.web.app/ask"
LOG_DIR="/data/data/com.termux/files/home/lawmadi-os-v60/logs"
LOG_FILE="$LOG_DIR/auto_test.log"
TIMEOUT=120
ADMIN_KEY="${TEST_ADMIN_KEY:-}"

mkdir -p "$LOG_DIR"

# ── 한글 테스트 쿼리 풀 (랜덤 선택) ──
KO_QUERIES=(
  "교통사고로 입원 중인데 상대방 보험사에서 합의금이 너무 적습니다. 어떻게 대응해야 하나요?"
  "회사에서 갑자기 해고 통보를 받았습니다. 부당해고 구제신청 절차와 비용을 알려주세요."
  "이혼 소송 시 양육권과 재산분할은 어떻게 결정되나요? 절차와 비용이 궁금합니다."
  "인터넷 쇼핑몰에서 사기를 당했습니다. 100만원 결제했는데 물건이 안 옵니다."
  "임대인이 보증금을 돌려주지 않습니다. 내용증명 발송 후 소송까지의 절차를 알려주세요."
  "명예훼손으로 고소하려 합니다. 온라인에서 허위사실을 유포당했는데 절차와 비용은?"
  "아파트 층간소음 문제로 이웃과 갈등 중입니다. 법적으로 어떤 조치가 가능한가요?"
  "개인회생 신청 조건과 절차가 궁금합니다. 빚이 5천만원 정도 있습니다."
  "상속 포기와 한정승인의 차이점과 절차를 알려주세요. 아버지가 돌아가셨습니다."
  "직장에서 성희롱을 당했습니다. 신고 절차와 법적 보호 방법을 알려주세요."
)

# ── 영문 테스트 쿼리 풀 (랜덤 선택) ──
EN_QUERIES=(
  "I got into a car accident in Seoul and the other driver was at fault. How do I claim compensation under Korean law?"
  "My employer has not paid my salary for 3 months. What legal actions can I take in Korea?"
  "I want to start a business in Korea as a foreigner. What are the visa and registration requirements?"
  "Someone is spreading false information about me online. Can I file a defamation lawsuit in Korea?"
  "I signed a lease contract but the landlord wants to evict me before the term ends. What are my rights?"
  "My Korean spouse and I are getting divorced. How is child custody decided under Korean law?"
  "I purchased a defective product from a Korean online store. What consumer protection laws apply?"
  "I received an unfair traffic ticket in Korea. How can I contest it?"
  "I want to apply for Korean permanent residency. What are the eligibility criteria and process?"
  "A business partner breached our contract. What are my legal options for damages in Korea?"
)

# ── 랜덤 쿼리 선택 ──
KO_IDX=$((RANDOM % ${#KO_QUERIES[@]}))
EN_IDX=$((RANDOM % ${#EN_QUERIES[@]}))
KO_QUERY="${KO_QUERIES[$KO_IDX]}"
EN_QUERY="${EN_QUERIES[$EN_IDX]}"

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S KST')
echo "" >> "$LOG_FILE"
echo "═══════════════════════════════════════════════════════════════" >> "$LOG_FILE"
echo "[$TIMESTAMP] Auto Test Run" >> "$LOG_FILE"
echo "═══════════════════════════════════════════════════════════════" >> "$LOG_FILE"

# ── 한글 테스트 ──
echo "[$TIMESTAMP] [KO] Query: $KO_QUERY" >> "$LOG_FILE"
KO_START=$(date +%s%N)

AUTH_HEADER=""
[[ -n "$ADMIN_KEY" ]] && AUTH_HEADER="-H \"X-Admin-Key: $ADMIN_KEY\""

KO_RESP=$(eval curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  $AUTH_HEADER \
  -d "'$(echo "{\"query\": \"$KO_QUERY\"}" | sed "s/'/\\\\'/g")'" \
  --max-time $TIMEOUT 2>&1) || KO_RESP='{"error":"TIMEOUT_OR_NETWORK_ERROR"}'

KO_END=$(date +%s%N)
KO_MS=$(( (KO_END - KO_START) / 1000000 ))

# 결과 파싱
KO_STATUS=$(echo "$KO_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','ERROR'))" 2>/dev/null || echo "PARSE_ERROR")
KO_LEADER=$(echo "$KO_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('leader','?'))" 2>/dev/null || echo "?")
KO_SPECIALTY=$(echo "$KO_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('leader_specialty','?'))" 2>/dev/null || echo "?")
KO_RESP_LEN=$(echo "$KO_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('response','')))" 2>/dev/null || echo "0")
KO_QUALITY=$(echo "$KO_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('meta',{}).get('quality_score','?'))" 2>/dev/null || echo "?")
KO_HAS_LAW=$(echo "$KO_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('meta',{}).get('has_law_name',False))" 2>/dev/null || echo "?")
KO_HAS_ART=$(echo "$KO_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('meta',{}).get('has_article',False))" 2>/dev/null || echo "?")
KO_SSOT=$(echo "$KO_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('meta',{}).get('ssot_verified',False))" 2>/dev/null || echo "?")

echo "  Status: $KO_STATUS | Leader: $KO_LEADER ($KO_SPECIALTY) | ${KO_MS}ms" >> "$LOG_FILE"
echo "  Length: ${KO_RESP_LEN}자 | Quality: $KO_QUALITY | Law: $KO_HAS_LAW | Article: $KO_HAS_ART | SSOT: $KO_SSOT" >> "$LOG_FILE"

# ── 영문 테스트 ──
echo "[$TIMESTAMP] [EN] Query: $EN_QUERY" >> "$LOG_FILE"
EN_START=$(date +%s%N)

EN_RESP=$(curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"$(echo "$EN_QUERY" | sed "s/'/\\\\u0027/g")\", \"lang\": \"en\"}" \
  --max-time $TIMEOUT 2>&1) || EN_RESP='{"error":"TIMEOUT_OR_NETWORK_ERROR"}'

EN_END=$(date +%s%N)
EN_MS=$(( (EN_END - EN_START) / 1000000 ))

EN_STATUS=$(echo "$EN_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','ERROR'))" 2>/dev/null || echo "PARSE_ERROR")
EN_LEADER=$(echo "$EN_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('leader','?'))" 2>/dev/null || echo "?")
EN_SPECIALTY=$(echo "$EN_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('leader_specialty','?'))" 2>/dev/null || echo "?")
EN_RESP_LEN=$(echo "$EN_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('response','')))" 2>/dev/null || echo "0")
EN_QUALITY=$(echo "$EN_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('meta',{}).get('quality_score','?'))" 2>/dev/null || echo "?")
EN_HAS_LAW=$(echo "$EN_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('meta',{}).get('has_law_name',False))" 2>/dev/null || echo "?")
EN_HAS_ART=$(echo "$EN_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('meta',{}).get('has_article',False))" 2>/dev/null || echo "?")
EN_SSOT=$(echo "$EN_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('meta',{}).get('ssot_verified',False))" 2>/dev/null || echo "?")

echo "  Status: $EN_STATUS | Leader: $EN_LEADER ($EN_SPECIALTY) | ${EN_MS}ms" >> "$LOG_FILE"
echo "  Length: ${EN_RESP_LEN}자 | Quality: $EN_QUALITY | Law: $EN_HAS_LAW | Article: $EN_HAS_ART | SSOT: $EN_SSOT" >> "$LOG_FILE"

# ── 요약 ──
PASS_COUNT=0
FAIL_COUNT=0
[[ "$KO_STATUS" == "SUCCESS" ]] && PASS_COUNT=$((PASS_COUNT+1)) || FAIL_COUNT=$((FAIL_COUNT+1))
[[ "$EN_STATUS" == "SUCCESS" ]] && PASS_COUNT=$((PASS_COUNT+1)) || FAIL_COUNT=$((FAIL_COUNT+1))

SUMMARY="✅ ${PASS_COUNT}/2 PASS"
[[ $FAIL_COUNT -gt 0 ]] && SUMMARY="❌ ${FAIL_COUNT}/2 FAIL"

echo "───────────────────────────────────────────────────────────────" >> "$LOG_FILE"
echo "  RESULT: $SUMMARY | KO: ${KO_MS}ms | EN: ${EN_MS}ms" >> "$LOG_FILE"

# 콘솔 출력 (cron이 아닌 수동 실행 시)
echo "[$TIMESTAMP] $SUMMARY | KO: ${KO_STATUS} ${KO_MS}ms ($KO_LEADER) | EN: ${EN_STATUS} ${EN_MS}ms ($EN_LEADER)"
echo "Log: $LOG_FILE"
