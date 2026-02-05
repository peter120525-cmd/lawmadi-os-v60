import os
import json
import logging
import datetime
import google.generativeai as genai
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from core.security import SafetyGuard, CircuitBreaker
from connectors.drf_client import DRFConnector

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LawmadiOS")

# 사장님 지정 버전 v50.0.0 고정
app = FastAPI(title="Lawmadi OS", version="v50.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

RUNTIME = {}

def load_integrated_config():
    """L0 KERNEL: 시스템 설정과 리더 데이터를 메모리 상에서 통합합니다."""
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            sys_cfg = json.load(f)
        with open("leaders.json", "r", encoding="utf-8") as f:
            leader_cfg = json.load(f)
        
        # 두 데이터를 하나로 병합 (leaders.json 내용이 sys_cfg에 추가됨)
        sys_cfg.update(leader_config_data := leader_cfg)
        return sys_cfg
    except Exception as e:
        logger.error(f"🚨 설정 로드 실패: {e}")
        return {}

@app.on_event("startup")
async def startup():
    # 병합된 설정 로드
    config = load_integrated_config()
    
    sec_cfg = config.get("security_layer", {})
    guard = SafetyGuard(True, [], sec_cfg.get("safety", {}))
    
    cb_cfg = config.get("network_security", {}).get("circuit_breaker", {}).get("per_provider", {}).get("LAW_GO_KR_DRF", {})
    drf_conn = DRFConnector(api_key=os.getenv("LAWGO_DRF_OC"), cb=CircuitBreaker("DRF", cb_cfg))
    
    genai.configure(api_key=os.getenv("GEMINI_KEY"))
    
    RUNTIME.update({"guard": guard, "drf": drf_conn, "config": config})
    logger.info("✅ Lawmadi OS v50.0.0 Integrated Kernel Online")

@app.post("/ask")
async def ask(req: Request):
    data = await req.json()
    query = data.get("query", "")
    config = RUNTIME["config"]
    
    # [L0] 보안 검사
    if not RUNTIME["guard"].check(query): return {"response": "🚫 보안 차단되었습니다."}
    
    # [L3] DRF 데이터 조회
    fmt = config.get("OUTPUT_FORMAT_POLICY", {}).get("LEGAL_SECTION", {})
    law_res = RUNTIME["drf"].fetch_verified_law(query)
    context = f"[DRF]: {law_res.get('content')}" if law_res.get("status") == "VERIFIED" else fmt.get("on_unavailable", "데이터 없음")

    # [L2] Swarm Persona 주입 (leaders.json 데이터 참조)
    # 60인의 리더 정보(LEADER_REGISTRY)를 Gemini에게 알려주어 전문성을 높입니다.
    leader_data = json.dumps(config.get("LEADER_REGISTRY", {}), ensure_ascii=False)

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        inst = f"""
        당신은 'Lawmadi OS v50.0.0'입니다. 6대 원칙을 엄수하세요.
        
        [전문가 군단(Legion) 정보]
        {leader_data}
        
        [출력 지침]
        - {fmt.get('header', '법률 근거')}
        - {context}
        - {fmt.get('disclaimer', '')}
        """
        resp = model.generate_content(f"{inst}\n\n사용자 질문: {query}")
        return {"response": resp.text}
    except Exception as e:
        return {"response": f"커널 오류: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
