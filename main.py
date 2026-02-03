import json
import os
import signal
import asyncio
import psutil
from typing import Optional, Tuple

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from anthropic import Anthropic

from core.security import CircuitBreaker, SafetyGuard

from core.case_summarizer import summarize
from core.drf_query_builder import build_queries
from core.evidence_explainer import explain
from core.action_router import route_action

from agents.swarm_manager import SwarmManager
from connectors.drf_client import DRFConnector

# ⚠️ db_client는 import 자체가 깨질 수 있으므로 지연 import
db_client = None  # type: ignore

app = FastAPI()

# 🔌 Claude LLM Client (Explain-only Role)
claude = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


# 전역 런타임 핸들
RUNTIME = {
    "config": None,
    "guard": None,
    "circuit_breakers": None,
    "drf": None,
    "swarm": None,
    "boot_error": None,
}


# =========================
# UX 전용: 사람 오프닝
# =========================
def human_opening_message() -> dict:
    import uuid
    request_id = str(uuid.uuid4())
    return {
        "request_id": request_id,
        "response": (
            "안녕하세요.\n"
            "상황부터 편하게 말씀해 주세요.\n\n"
            "예를 들면,\n"
            "“전세보증금을 못 돌려받고 있어요”처럼 한 줄이면 충분합니다."
        )
    }


# ✅ [Golden Path] 안전하고 명확한 환경변수 검증
def _validate_env(config: dict):
    required = config.get("required_env_vars", [])
    missing = []

    for var in required:
        value = os.getenv(var)
        if not value or value.strip() == "":
            missing.append(var)

    if missing:
        # 누락된 변수들을 한 번에 알려주어 디버깅 효율성 증대
        raise RuntimeError(
            f"[HALT_BOOTSTRAP] 필수 환경변수 누락: {', '.join(missing)}"
        )

    print(f"✅ [ENV] 필수 환경변수 {len(required)}개 검증 완료")


def _get_health_status() -> dict:
    mem = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0.1)
    import uuid
    request_id = str(uuid.uuid4())
    return {
        "request_id": request_id,
        "memory_percent": mem.percent,
        "cpu_percent": cpu,
        "status": "Healthy" if mem.percent < 75 and cpu < 90 else "Warning"
    }


def _shutdown_handler(signum, frame):
    print("\n🔄 [Shutdown] 연결 정리 중...")
    try:
        if db_client is not None:
            db_client.close_all()
    except Exception as e:
        print(f"⚠️ [Shutdown] DB 정리 중 오류: {e}")
    print("✅ [Shutdown] 완료")


def bootstrap_system() -> Tuple[dict, SafetyGuard, dict, DRFConnector, SwarmManager]:
    global db_client

    signal.signal(signal.SIGINT, _shutdown_handler)
    signal.signal(signal.SIGTERM, _shutdown_handler)

    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    version = config.get("system_metadata", {}).get("os_version", "unknown")
    print(f"--- Lawmadi OS {version} Booting ---")

    _validate_env(config)

    # DB 초기화 (Fail-soft)
    try:
        from connectors import db_client as _db_client
        db_client = _db_client
        print("🔄 [DB] Cloud SQL 연결 및 테이블 초기화...")
        db_client.init_tables()
        print("✅ [DB] init_tables 완료")
    except Exception as e:
        print(f"⚠️ [DB] 초기화 실패(Fail-soft): {e}")
        db_client = None

    security_cfg = config["security_layer"]
    guard = SafetyGuard(
        policy=security_cfg["anti_leak_policy"],
        restricted_keywords=security_cfg["restricted_keywords"],
        safety_config=security_cfg["safety"]
    )

    cb_configs = config["network_security"]["circuit_breaker"]["per_provider"]
    circuit_breakers = {
        provider: CircuitBreaker(provider_name=provider, config=cb_configs[provider])
        for provider in cb_configs
    }

    drf_cfg = config["data_sync_connectors"]
    # ✅ [Security] 코드에 값을 박지 않고 OS 환경변수(Secret)에서 로드
    drf = DRFConnector(
        api_key=os.getenv("LAWGO_DRF_OC"),
        timeout_ms=drf_cfg["request_timeout_ms"],
        endpoints=drf_cfg["drf_endpoints"],
        cb=circuit_breakers.get("LAW_GO_KR_DRF"),
        api_failure_policy=drf_cfg["api_failure_policy"]
    )

    swarm = SwarmManager(config=config["swarm_engine_config"])

    return config, guard, circuit_breakers, drf, swarm


async def _init_db_background(timeout_sec: float = 3.0):
    global db_client
    try:
        from connectors import db_client as _db_client
        db_client = _db_client
        print("🔄 [DB] init_tables(background)...")
        await asyncio.wait_for(
            asyncio.to_thread(db_client.init_tables),
            timeout=timeout_sec
        )
        print("✅ [DB] init_tables 완료")
    except Exception as e:
        print(f"⚠️ [DB] background init 실패(Fail-soft): {e}")
        db_client = None


@app.on_event("startup")
async def on_startup():
    try:
        config, guard, cbs, drf, swarm = bootstrap_system()
        RUNTIME["config"] = config
        RUNTIME["guard"] = guard
        RUNTIME["circuit_breakers"] = cbs
        RUNTIME["drf"] = drf
        RUNTIME["swarm"] = swarm
        RUNTIME["boot_error"] = None

        asyncio.create_task(_init_db_background())

        health = _get_health_status()
        print(f"✅ System Health: {health['status']} "
              f"(Memory: {health['memory_percent']}%, CPU: {health['cpu_percent']}%)")
    except Exception as e:
        RUNTIME["boot_error"] = str(e)
        print(f"❌ [BOOT] 부팅 실패(서버는 유지): {e}")


@app.get("/health")
def health():
    import uuid
    request_id = str(uuid.uuid4())
    return {
        "request_id": request_id,
        "ok": True,
        "boot_ok": RUNTIME["boot_error"] is None,
        "boot_error": RUNTIME["boot_error"],
        "resource": _get_health_status()
    }


SOFT_MODE = os.getenv("SOFT_MODE", "true").lower() == "true"


@app.post("/ask")
async def ask(req: Request):
    body = await req.json()
    user_input = (body.get("query") or "").strip()

    if not user_input:
        return human_opening_message()

    # ① LLM 사건 요약 (법 판단 없음)
    summary = summarize(user_input)

    # 🧭 A/B/C 재진입 처리 (Soft Mode Fallback 추가 + Exception Safety)
    if user_input.strip().upper()[:1] in ["A", "B", "C"]:
        drf = RUNTIME["drf"]
        routed = None
        
        # 1. 정석대로 Action Router 시도 (안전망 확보)
        try:
            routed = route_action(user_input, summary, drf)
        except Exception as e:
            print(f"⚠️ [Routing Error] route_action 실패: {e}")
            routed = None
            
        # 2. Router가 성공적이고, fail_closed가 아니면 반환
        if routed and not routed.get("fail_closed", False):
            return routed
            
        # 3. ⚠️ Router 실패/에러 시 Soft Mode 강제 진입 (Fail-Over)
        # DRF가 죽어도 A/B/C에 대한 응답은 나가야 함
        import uuid
        choice = user_input.strip().upper()[:1]
        
        fallback_responses = {
            "A": (
                "## [A. 내용증명 발송 가이드]\n\n"
                "법적 효력을 위해 우체국을 통해 '내용증명'을 발송해야 합니다.\n\n"
                "**1. 필수 포함 내용**\n"
                "- 수신인/발신인 주소 및 성명\n"
                "- 임대차 계약 사실 (계약일, 만기일, 보증금액)\n"
                "- 계약 해지 의사 표시 ('만기에 맞춰 이사하겠다')\n"
                "- 보증금 반환 계좌번호\n\n"
                "**2. 작성 팁**\n"
                "총 3부를 작성하여 우체국 창구에 가져가시면 됩니다. (본인/우체국/수신인 보관용)"
            ),
            "B": (
                "## [B. 경찰 신고/고소 가이드]\n\n"
                "전세사기가 의심될 경우 관할 경찰서 경제팀을 방문하세요.\n\n"
                "**준비물:**\n"
                "- 신분증, 임대차계약서 원본\n"
                "- 이체 내역서 (은행 발급)\n"
                "- 집주인과 나눈 문자/통화 녹음 등 증거\n\n"
                "※ 단순 미반환은 민사 문제일 수 있으나, '기망 행위'가 있었다면 사기죄 성립이 가능합니다."
            ),
            "C": (
                "## [C. 보증금 반환 소송 가이드]\n\n"
                "법원을 통해 강제 집행 권한을 얻는 절차입니다.\n\n"
                "1. **임차권등기명령:** 이사 가기 전 필수 신청 (대항력 유지)\n"
                "2. **지급명령:** 집주인이 이의 제기 안 하면 1~2달 내 확정 (빠름)\n"
                "3. **본안소송:** 다툼이 있을 경우 진행 (6개월 이상 소요)\n\n"
                "※ 소송 비용은 승소 시 상대방에게 청구 가능합니다."
            )
        }

        request_id = str(uuid.uuid4())
        return {
            "request_id": request_id,
            "case_summary": summary,
            "law_domains": summary.get("law_domains", []),
            "recipe_id": f"SOFT_MODE_FALLBACK_{choice}",
            "response": fallback_responses.get(choice, "해당 선택지에 대한 정보를 불러올 수 없습니다.")
        }

    # ② DRF 커넥터
    drf: DRFConnector = RUNTIME["drf"]

    # ③ 요약 기반 DRF 검색
    queries = " ".join(build_queries(summary))
    context = drf.fetch_verified_law(queries)

    laws = context.get("content") if isinstance(context, dict) else None

    # ④ DRF 실패 → SOFT_MODE 행동 가이드
    if not laws:
        import uuid
        request_id = str(uuid.uuid4())
        return {
            "request_id": request_id,
            "case_summary": summary,
            "law_domains": summary.get("law_domains", []),
            "leaders": ["L01", "L08", "L22"],
            "recipe_id": "SOFT_MODE_ACTION_FLOW",
            "response": (
                "전세사기 가능성이 상당히 높은 유형으로 판단됩니다.\n\n"
                "[현재 상황 핵심]\n"
                "- 임대차 계약 체결\n"
                "- 보증금 지급 완료\n"
                "- 보증금 미반환 또는 반환 거부 가능성\n\n"
                "[지금 바로 해야 할 순서]\n"
                "1. 등기부등본 확인 (소유자·근저당·가압류)\n"
                "2. 보증금 이체 내역 확보\n"
                "3. 임대인 실소유자 동일성 확인\n\n"
                "[다음 단계 선택]\n"
                "A. 내용증명 발송\n"
                "B. 형사 고소 또는 경찰 신고\n"
                "C. 보증금 반환 소송\n\n"
                "👉 A / B / C 중 하나를 입력해 주세요."
            )
        }

    # ⑤ DRF 성공 → 근거 기반 설명만
    # ⑤-1 Claude에게 설명 위임 (근거 제한)
    system_prompt = (
        "You are Lawmadi OS. "
        "Explain ONLY based on the provided legal evidence. "
        "Do NOT create new statutes or precedents. "
        "Do NOT guess. "
        "Explain clearly in Korean for non-lawyers."
    )

    evidence_text = context.get("content", "")

    try:
        # ⚠️ 동기 호출 유지 (추후 Async 변환 필요)
        claude_resp = claude.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            temperature=0.2,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": (
                    f"[사건 요약]\n{summary}\n\n"
                    f"[법률 근거]\n{evidence_text}\n\n"
                    "위 근거만 사용하여 현재 상황을 설명해 주세요."
                )
            }]
        )
        explanation = claude_resp.content[0].text
        explanation += "\n\n(AI Lawmadi가 판례 데이터를 기반으로 분석한 내용입니다.)"

    except Exception as e:
        print(f"⚠️ [LLM Error] Claude 호출 실패: {e}")
        explanation = explain(context, summary)
        explanation += "\n\n※ AI 연결 지연으로 인해 표준 법령 정보를 표시합니다."

    # 🔐 공통 후처리 (DRF 근거 명시)
    explanation += "\n\n※ 위 내용은 국가법령정보센터 근거에 기반한 설명입니다."

    import uuid
    request_id = str(uuid.uuid4())

    return {
        "request_id": request_id,
        "case_summary": summary,
        "law_domains": summary.get("law_domains", []),
        "response": explanation
    }
