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

app = FastAPI(title="Lawmadi OS", version="v50.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

RUNTIME = {}

@app.on_event("startup")
async def startup():
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    sec_cfg = config.get("security_layer", {})
    guard = SafetyGuard(True, [], sec_cfg.get("safety", {}))
    cb_cfg = config.get("network_security", {}).get("circuit_breaker", {}).get("per_provider", {}).get("LAW_GO_KR_DRF", {})
    drf_conn = DRFConnector(api_key=os.getenv("LAWGO_DRF_OC"), cb=CircuitBreaker("DRF", cb_cfg))
    genai.configure(api_key=os.getenv("GEMINI_KEY"))
    RUNTIME.update({"guard": guard, "drf": drf_conn, "config": config})
    logger.info("✅ Lawmadi OS v50.0.0 Online")

@app.post("/ask")
async def ask(req: Request):
    data = await req.json()
    query = data.get("query", "")
    config = RUNTIME["config"]
    fmt = config["OUTPUT_FORMAT_POLICY"]["LEGAL_SECTION"]
    if not RUNTIME["guard"].check(query): return {"response": "🚫 보안 정책 위반으로 차단되었습니다."}
    law_res = RUNTIME["drf"].fetch_verified_law(query)
    context = f"[DRF]: {law_res.get('content')}" if law_res.get("status") == "VERIFIED" else fmt["on_unavailable"]
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        inst = f"너는 Lawmadi OS v50.0.0이다. 다음 원칙을 준수하라: 1. SSOT 2. ZERO_INFERENCE 3. TEMPORAL. \n\n{fmt['header']}\n{context}\n{fmt['disclaimer']}"
        resp = model.generate_content(f"{inst}\n\n질문: {query}")
        return {"response": resp.text}
    except Exception as e:
        return {"response": f"커널 오류: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
