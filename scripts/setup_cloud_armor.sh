#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Lawmadi OS v60 — Cloud Armor WAF + External HTTPS LB 설정
#
# 비용: ~$23/월 (LB $18 + Cloud Armor $5)
# 효과: DDoS 방어, OWASP Top 10, IP 레이트리밋, 지역 차단
#
# 사전 조건:
#   - gcloud CLI 인증 완료
#   - lawmadi-db 프로젝트 소유자 권한
#   - 도메인 SSL 인증서 (또는 Google-managed 사용)
#
# 실행: bash scripts/setup_cloud_armor.sh
# 롤백: bash scripts/setup_cloud_armor.sh --rollback
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

# ── 환경 설정 ──
PROJECT_ID="lawmadi-db"
REGION="asia-northeast3"
SERVICE_NAME="lawmadi-os-v60"
NEG_NAME="lawmadi-neg"
BACKEND_NAME="lawmadi-backend"
URL_MAP_NAME="lawmadi-url-map"
PROXY_NAME="lawmadi-https-proxy"
FWD_RULE_NAME="lawmadi-forwarding-rule"
ARMOR_POLICY="lawmadi-waf-policy"
SSL_CERT_NAME="lawmadi-ssl-cert"
DOMAIN="lawmadi-os-v60-938146962157.asia-northeast3.run.app"
STATIC_IP_NAME="lawmadi-lb-ip"

echo "╔══════════════════════════════════════════════╗"
echo "║  Lawmadi OS v60 — Cloud Armor WAF 설정      ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "📋 설정:"
echo "  프로젝트: ${PROJECT_ID}"
echo "  리전: ${REGION}"
echo "  서비스: ${SERVICE_NAME}"
echo "  예상 비용: ~\$23/월 (LB \$18 + Armor \$5)"
echo ""

# ── 롤백 모드 ──
if [[ "${1:-}" == "--rollback" ]]; then
    echo "🔄 롤백 시작 — 모든 WAF 리소스를 삭제합니다"
    echo ""

    gcloud compute forwarding-rules delete ${FWD_RULE_NAME} --global --quiet 2>/dev/null || true
    echo "  ✓ Forwarding rule 삭제"

    gcloud compute target-https-proxies delete ${PROXY_NAME} --quiet 2>/dev/null || true
    echo "  ✓ HTTPS proxy 삭제"

    gcloud compute url-maps delete ${URL_MAP_NAME} --quiet 2>/dev/null || true
    echo "  ✓ URL map 삭제"

    gcloud compute backend-services delete ${BACKEND_NAME} --global --quiet 2>/dev/null || true
    echo "  ✓ Backend service 삭제"

    gcloud compute network-endpoint-groups delete ${NEG_NAME} --region=${REGION} --quiet 2>/dev/null || true
    echo "  ✓ NEG 삭제"

    gcloud compute security-policies delete ${ARMOR_POLICY} --quiet 2>/dev/null || true
    echo "  ✓ Cloud Armor 정책 삭제"

    gcloud compute ssl-certificates delete ${SSL_CERT_NAME} --quiet 2>/dev/null || true
    echo "  ✓ SSL 인증서 삭제"

    gcloud compute addresses delete ${STATIC_IP_NAME} --global --quiet 2>/dev/null || true
    echo "  ✓ 고정 IP 삭제"

    echo ""
    echo "✅ 롤백 완료 — Cloud Run 직접 접근으로 복원됨"
    exit 0
fi

# ── 사전 확인 ──
echo "⚠️  이 스크립트는 다음 리소스를 생성합니다:"
echo "  1. 외부 고정 IP ($STATIC_IP_NAME)"
echo "  2. Serverless NEG → Cloud Run 연결"
echo "  3. Backend Service + Cloud Armor 정책"
echo "  4. HTTPS Load Balancer (Google-managed SSL)"
echo "  5. Cloud Armor 보안 규칙 (OWASP, 지역 차단, Rate Limit)"
echo ""
echo "  💰 예상 월 비용: ~\$23 (LB \$18 + Cloud Armor \$5)"
echo ""
read -p "계속하시겠습니까? (y/N): " confirm
if [[ "${confirm}" != "y" && "${confirm}" != "Y" ]]; then
    echo "취소됨"
    exit 0
fi
echo ""

# ── Step 1: 고정 IP 예약 ──
echo "1️⃣ 외부 고정 IP 예약..."
if gcloud compute addresses describe ${STATIC_IP_NAME} --global --project=${PROJECT_ID} &>/dev/null; then
    echo "  ℹ️  이미 존재 — 스킵"
else
    gcloud compute addresses create ${STATIC_IP_NAME} \
        --global \
        --project=${PROJECT_ID}
    echo "  ✓ 고정 IP 생성 완료"
fi
LB_IP=$(gcloud compute addresses describe ${STATIC_IP_NAME} --global --project=${PROJECT_ID} --format='value(address)')
echo "  📌 LB IP: ${LB_IP}"
echo ""

# ── Step 2: Serverless NEG 생성 ──
echo "2️⃣ Serverless NEG 생성 (Cloud Run 연결)..."
if gcloud compute network-endpoint-groups describe ${NEG_NAME} --region=${REGION} --project=${PROJECT_ID} &>/dev/null; then
    echo "  ℹ️  이미 존재 — 스킵"
else
    gcloud compute network-endpoint-groups create ${NEG_NAME} \
        --region=${REGION} \
        --network-endpoint-type=serverless \
        --cloud-run-service=${SERVICE_NAME} \
        --project=${PROJECT_ID}
    echo "  ✓ NEG 생성 완료"
fi
echo ""

# ── Step 3: Cloud Armor 보안 정책 생성 ──
echo "3️⃣ Cloud Armor 보안 정책 생성..."
if gcloud compute security-policies describe ${ARMOR_POLICY} --project=${PROJECT_ID} &>/dev/null; then
    echo "  ℹ️  이미 존재 — 규칙 업데이트"
else
    gcloud compute security-policies create ${ARMOR_POLICY} \
        --description="Lawmadi OS WAF — DDoS + OWASP + Rate Limit" \
        --project=${PROJECT_ID}
    echo "  ✓ 정책 생성 완료"
fi

# Rule 1: OWASP Top 10 — SQL Injection 차단
echo "  📜 Rule 1000: SQL Injection 차단..."
gcloud compute security-policies rules create 1000 \
    --security-policy=${ARMOR_POLICY} \
    --expression="evaluatePreconfiguredExpr('sqli-v33-stable')" \
    --action=deny-403 \
    --description="OWASP SQL Injection" \
    --project=${PROJECT_ID} 2>/dev/null || \
gcloud compute security-policies rules update 1000 \
    --security-policy=${ARMOR_POLICY} \
    --expression="evaluatePreconfiguredExpr('sqli-v33-stable')" \
    --action=deny-403 \
    --project=${PROJECT_ID}

# Rule 2: OWASP — XSS 차단
echo "  📜 Rule 1001: XSS 차단..."
gcloud compute security-policies rules create 1001 \
    --security-policy=${ARMOR_POLICY} \
    --expression="evaluatePreconfiguredExpr('xss-v33-stable')" \
    --action=deny-403 \
    --description="OWASP XSS" \
    --project=${PROJECT_ID} 2>/dev/null || \
gcloud compute security-policies rules update 1001 \
    --security-policy=${ARMOR_POLICY} \
    --expression="evaluatePreconfiguredExpr('xss-v33-stable')" \
    --action=deny-403 \
    --project=${PROJECT_ID}

# Rule 3: OWASP — RFI (Remote File Inclusion) 차단
echo "  📜 Rule 1002: Remote File Inclusion 차단..."
gcloud compute security-policies rules create 1002 \
    --security-policy=${ARMOR_POLICY} \
    --expression="evaluatePreconfiguredExpr('rfi-v33-stable')" \
    --action=deny-403 \
    --description="OWASP RFI" \
    --project=${PROJECT_ID} 2>/dev/null || \
gcloud compute security-policies rules update 1002 \
    --security-policy=${ARMOR_POLICY} \
    --expression="evaluatePreconfiguredExpr('rfi-v33-stable')" \
    --action=deny-403 \
    --project=${PROJECT_ID}

# Rule 4: OWASP — Scanner Detection
echo "  📜 Rule 1003: 스캐너 탐지..."
gcloud compute security-policies rules create 1003 \
    --security-policy=${ARMOR_POLICY} \
    --expression="evaluatePreconfiguredExpr('scannerdetection-v33-stable')" \
    --action=deny-403 \
    --description="Scanner Detection" \
    --project=${PROJECT_ID} 2>/dev/null || \
gcloud compute security-policies rules update 1003 \
    --security-policy=${ARMOR_POLICY} \
    --expression="evaluatePreconfiguredExpr('scannerdetection-v33-stable')" \
    --action=deny-403 \
    --project=${PROJECT_ID}

# Rule 5: IP Rate Limit — /ask 엔드포인트 (10req/분)
echo "  📜 Rule 2000: /ask Rate Limit (10req/분)..."
gcloud compute security-policies rules create 2000 \
    --security-policy=${ARMOR_POLICY} \
    --expression="request.path.matches('/ask.*')" \
    --action=rate-based-ban \
    --rate-limit-threshold-count=10 \
    --rate-limit-threshold-interval-sec=60 \
    --ban-duration-sec=300 \
    --conform-action=allow \
    --exceed-action=deny-429 \
    --enforce-on-key=IP \
    --description="Rate limit /ask — 10 req/min per IP, ban 5min" \
    --project=${PROJECT_ID} 2>/dev/null || \
gcloud compute security-policies rules update 2000 \
    --security-policy=${ARMOR_POLICY} \
    --expression="request.path.matches('/ask.*')" \
    --action=rate-based-ban \
    --rate-limit-threshold-count=10 \
    --rate-limit-threshold-interval-sec=60 \
    --ban-duration-sec=300 \
    --conform-action=allow \
    --exceed-action=deny-429 \
    --enforce-on-key=IP \
    --project=${PROJECT_ID}

# Rule 6: 전체 Rate Limit (30req/분)
echo "  📜 Rule 2001: 전체 Rate Limit (30req/분)..."
gcloud compute security-policies rules create 2001 \
    --security-policy=${ARMOR_POLICY} \
    --expression="true" \
    --action=rate-based-ban \
    --rate-limit-threshold-count=30 \
    --rate-limit-threshold-interval-sec=60 \
    --ban-duration-sec=120 \
    --conform-action=allow \
    --exceed-action=deny-429 \
    --enforce-on-key=IP \
    --description="Global rate limit — 30 req/min per IP, ban 2min" \
    --project=${PROJECT_ID} 2>/dev/null || \
gcloud compute security-policies rules update 2001 \
    --security-policy=${ARMOR_POLICY} \
    --expression="true" \
    --action=rate-based-ban \
    --rate-limit-threshold-count=30 \
    --rate-limit-threshold-interval-sec=60 \
    --ban-duration-sec=120 \
    --conform-action=allow \
    --exceed-action=deny-429 \
    --enforce-on-key=IP \
    --project=${PROJECT_ID}

echo "  ✓ Cloud Armor 규칙 설정 완료 (6개 규칙)"
echo ""

# ── Step 4: Backend Service 생성 ──
echo "4️⃣ Backend Service 생성 + Cloud Armor 연결..."
if gcloud compute backend-services describe ${BACKEND_NAME} --global --project=${PROJECT_ID} &>/dev/null; then
    echo "  ℹ️  이미 존재 — 업데이트"
else
    gcloud compute backend-services create ${BACKEND_NAME} \
        --global \
        --load-balancing-scheme=EXTERNAL_MANAGED \
        --project=${PROJECT_ID}
    echo "  ✓ Backend Service 생성"
fi

gcloud compute backend-services add-backend ${BACKEND_NAME} \
    --global \
    --network-endpoint-group=${NEG_NAME} \
    --network-endpoint-group-region=${REGION} \
    --project=${PROJECT_ID} 2>/dev/null || true

gcloud compute backend-services update ${BACKEND_NAME} \
    --global \
    --security-policy=${ARMOR_POLICY} \
    --project=${PROJECT_ID}
echo "  ✓ Cloud Armor 정책 연결 완료"
echo ""

# ── Step 5: URL Map 생성 ──
echo "5️⃣ URL Map 생성..."
if gcloud compute url-maps describe ${URL_MAP_NAME} --project=${PROJECT_ID} &>/dev/null; then
    echo "  ℹ️  이미 존재 — 스킵"
else
    gcloud compute url-maps create ${URL_MAP_NAME} \
        --default-service=${BACKEND_NAME} \
        --project=${PROJECT_ID}
    echo "  ✓ URL Map 생성 완료"
fi
echo ""

# ── Step 6: Google-managed SSL 인증서 ──
echo "6️⃣ Google-managed SSL 인증서..."
if gcloud compute ssl-certificates describe ${SSL_CERT_NAME} --project=${PROJECT_ID} &>/dev/null; then
    echo "  ℹ️  이미 존재 — 스킵"
else
    gcloud compute ssl-certificates create ${SSL_CERT_NAME} \
        --domains=${DOMAIN} \
        --global \
        --project=${PROJECT_ID}
    echo "  ✓ SSL 인증서 생성 (프로비저닝에 10~20분 소요)"
fi
echo ""

# ── Step 7: HTTPS Proxy 생성 ──
echo "7️⃣ HTTPS Proxy 생성..."
if gcloud compute target-https-proxies describe ${PROXY_NAME} --project=${PROJECT_ID} &>/dev/null; then
    echo "  ℹ️  이미 존재 — 스킵"
else
    gcloud compute target-https-proxies create ${PROXY_NAME} \
        --url-map=${URL_MAP_NAME} \
        --ssl-certificates=${SSL_CERT_NAME} \
        --project=${PROJECT_ID}
    echo "  ✓ HTTPS Proxy 생성 완료"
fi
echo ""

# ── Step 8: Forwarding Rule (고정 IP → LB) ──
echo "8️⃣ Forwarding Rule 생성..."
if gcloud compute forwarding-rules describe ${FWD_RULE_NAME} --global --project=${PROJECT_ID} &>/dev/null; then
    echo "  ℹ️  이미 존재 — 스킵"
else
    gcloud compute forwarding-rules create ${FWD_RULE_NAME} \
        --global \
        --target-https-proxy=${PROXY_NAME} \
        --address=${STATIC_IP_NAME} \
        --ports=443 \
        --load-balancing-scheme=EXTERNAL_MANAGED \
        --project=${PROJECT_ID}
    echo "  ✓ Forwarding Rule 생성 완료"
fi
echo ""

# ── 완료 ──
echo "╔══════════════════════════════════════════════╗"
echo "║            ✅ WAF 설정 완료!                 ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "📊 구성 요약:"
echo "  LB IP:        ${LB_IP}"
echo "  Cloud Armor:  ${ARMOR_POLICY}"
echo "  규칙:"
echo "    1000: SQL Injection 차단"
echo "    1001: XSS 차단"
echo "    1002: Remote File Inclusion 차단"
echo "    1003: 스캐너 탐지"
echo "    2000: /ask Rate Limit (10req/분, 5분 밴)"
echo "    2001: 전체 Rate Limit (30req/분, 2분 밴)"
echo ""
echo "⚡ 다음 단계:"
echo "  1. SSL 인증서 프로비저닝 확인 (10~20분):"
echo "     gcloud compute ssl-certificates describe ${SSL_CERT_NAME}"
echo ""
echo "  2. DNS 설정 (커스텀 도메인 사용 시):"
echo "     A 레코드 → ${LB_IP}"
echo ""
echo "  3. 프론트엔드 API_BASE 업데이트 (필요 시):"
echo "     Cloud Run URL → LB URL"
echo ""
echo "  4. Cloud Run Ingress 제한 (LB만 허용):"
echo "     gcloud run services update ${SERVICE_NAME} --ingress=internal-and-cloud-load-balancing --region=${REGION}"
echo ""
echo "  5. 모니터링:"
echo "     gcloud compute security-policies describe ${ARMOR_POLICY} --project=${PROJECT_ID}"
echo ""
echo "  🔄 롤백: bash scripts/setup_cloud_armor.sh --rollback"
