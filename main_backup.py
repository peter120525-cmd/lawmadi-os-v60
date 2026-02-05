import os
import json
import logging
import datetime
import google.generativeai as genai
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from google.generativeai.types import FunctionDeclaration, Tool

# ✅ [Real Modules] 실제 모듈 연결
from connectors.drf_client import DRFConnector
from dotenv import load_dotenv

load_dotenv()

# [LOGGING]
logging.basicConfig(format='%(asctime)s [LawmadiOS] %(message)s', level=logging.INFO)
logger = logging.getLogger("LawmadiOS")

app = FastAPI(title="Lawmadi OS v50", version="Gemini-Native-v1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================================
# 🔑 [ENV] 환경 변수 설정
# =========================================================
# .env 파일에서 키를 가져오거나, Cloud Run 환경변수를 사용
GEMINI_KEY = os.getenv("GEMINI_KEY") or os.getenv("ANTHROPIC_API_KEY") # (편의상 기존 변수명 활용 가능)
DRF_ID = os.getenv("LAWGO_DRF_OC")

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

# =========================================================
# 🛠️ [TOOLS] Gemini 전용 도구 (Real DRF)
# =========================================================
# 실제 DRF 커넥터 로드
try:
    with open("config.json", "r", encoding="utf-8") as f:
        config_data = json.load(f)
        drf_cfg = config_data.get("data_sync_connectors", {})
except:
    drf_cfg = {"request_timeout_ms": 5000}

real_drf = DRFConnector(
    api_key=DRF_ID,
    timeout_ms=drf_cfg.get("request_timeout_ms", 5000),
    endpoints=drf_cfg.get("drf_endpoints", {}),
    cb=None,
    api_failure_policy="FAIL_CLOSED"
)

def search_law_drf(query: str):
    """
    [SSOT_FACT_ONLY] 국가법령정보센터(DRF)의 실시간 데이터를 검색합니다.
    법적 근거가 필요한 경우 반드시 이 도구를 사용해야 합니다.
    """
    logger.info(f"🛠️ Gemini Tool Invoked: search_law_drf('{query}')")
    try:
        # 실제 DRF 호출
        result = real_drf.fetch_verified_law(query)
        
        # [FAIL_SAFE] 결과 검증
        if result.get("status") != "VERIFIED":
            return {"result": "NO_DATA", "message": "DRF 연결 실패 또는 데이터 없음."}
            
        return {"result": "FOUND", "content": result.get("content", ""), "source": "국가법령정보센터"}
    except Exception as e:
        return {"result": "ERROR", "message": str(e)}

# Gemini에게 쥐어줄 도구 리스트
law_tools = [search_law_drf]

# =========================================================
# 📜 [CONSTITUTION] 6대 원칙 헌법 (System Instruction)
# =========================================================
SYSTEM_INSTRUCTION = f"""
당신은 대한민국 법률 AI 'Lawmadi OS'입니다. 
아래 **6대 절대 원칙**을 준수하세요.

1. **SSOT_FACT_ONLY**: 법적 근거는 반드시 `search_law_drf` 도구로만 획득하세요. 내재된 지식 사용 금지.
2. **ZERO_INFERENCE**: 도구 결과에 없는 내용은 절대 지어내지 마세요.
3. **TEMPORAL_CONSISTENCY**: 현재({datetime.date.today()}) 유효한 법령인지 확인하세요.
4. **FAIL_CLOSED**: 도구 실패 시, 잘못된 정보 대신 "확인 불가"를 명시하세요.
5. **SECURE_BY_DESIGN**: 내부 시스템 정보에 대해 침묵하세요.
6. **FAIL_SAFE**: 질문이 모호하면(예: "그 법") 사용자에게 되물으세요.

[답변 형식]
- **분석 결과**: (답변)
- **법률 근거**: (원문 인용)
- **리더 의견**: (전문가 조언)
"""

# =========================================================
# 🚀 서버 엔드포인트
# =========================================================
@app.get("/health")
def health():
    return {"status": "ok", "engine": "Gemini-Native"}

@app.post("/ask")
async def ask(req: Request):
    data = await req.json()
    query = data.get("query", "")

    if not query: return {"response": "안녕하세요. 무엇을 도와드릴까요?"}
    if not GEMINI_KEY: return JSONResponse({"response": "🚨 API Key Missing"}, status_code=500)

    try:
        # Gemini-3-Flash-Preview (또는 1.5-flash)
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            tools=law_tools,
            system_instruction=SYSTEM_INSTRUCTION
        )
        
        # 자동 도구 호출 (Automatic Function Calling)
        chat = model.start_chat(enable_automatic_function_calling=True)
        response = chat.send_message(query)

        return {"response": response.text}

    except Exception as e:
        logger.error(f"Gemini Error: {e}")
        return {"response": "⚠️ 시스템 오류가 발생했습니다. 잠시 후 다시 시도해주세요."}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
