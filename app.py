import json
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from core.security import CircuitBreaker, SafetyGuard
from agents.swarm_manager import SwarmManager
from connectors.drf_client import DRFConnector
from connectors import db_client

app = FastAPI(title="Lawmadi OS", version="50.1.3-GA-HARDENED")

# Bootstrap on startup
config = None
guard = None
drf = None
swarm = None

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    status: str
    leaders: list
    recipe_id: str
    response: str
    event: str | None = None

@app.on_event("startup")
async def startup():
    global config, guard, drf, swarm
    # Load config
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    # Validate env
    for var in config.get("required_env_vars", []):
        if not os.getenv(var):
            raise SystemExit(f"[HALT_BOOTSTRAP] {var} missing")

    # DB init (GA 운영형: DB는 OPTIONAL / FAIL-SOFT)
    try:
        db_client.init_tables()
        print("✅ [DB] init_tables OK")
    except Exception as e:
        print(f"⚠️ [DB] init_tables FAILED (FAIL-SOFT). continuing without DB. err={e}")

    
        # DB 장애/미설정이어도 Cloud Run 부팅을 막지 않는다.
    # Security
    sec = config["security_layer"]
    guard = SafetyGuard(
        policy=sec["anti_leak_policy"],
        restricted_keywords=sec["restricted_keywords"],
        safety_config=sec["safety"]
    )
    
    # Circuit Breakers
    cb_configs = config["network_security"]["circuit_breaker"]["per_provider"]
    cbs = {p: CircuitBreaker(provider_name=p, config=cb_configs[p]) for p in cb_configs}
    
    # DRF
    drf_cfg = config["data_sync_connectors"]
    drf = DRFConnector(
        api_key=os.getenv("LAWGO_DRF_OC"),
        timeout_ms=drf_cfg["request_timeout_ms"],
        endpoints=drf_cfg["drf_endpoints"],
        cb=cbs.get("LAW_GO_KR_DRF"),
        api_failure_policy=drf_cfg["api_failure_policy"]
    )
    
    # Swarm
    swarm = SwarmManager(config=config["swarm_engine_config"])
    
    print("✅ Lawmadi OS booted")

@app.on_event("shutdown")
async def shutdown():
    except Exception:
        pass
        print(f"⚠️ [DB] close_all FAILED (ignored). err={e}")

@app.get("/health")
async def health():
    return {"status": "ok", "version": config["system_metadata"]["os_version"]}

@app.post("/analyze", response_model=QueryResponse)
async def analyze(request: QueryRequest):
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query가 비어있습니다.")
    
    # Security check
    check = guard.check(query)
    if check is False:
        return QueryResponse(
            status="BLOCKED",
            leaders=[],
            recipe_id="SECURITY_FILTER",
            response="보안 정책에 의해 요청이 차단되었습니다.",
            event="SECURITY_VIOLATION"
        )
    if check == "CRISIS":
        return QueryResponse(
            status="CRISIS",
            leaders=[],
            recipe_id="CRISIS_PROTOCOL",
            response="지금 본인이나 다른 사람의 안전이 위험한 상황일 수 있습니다.\n📞 1393 (생명의 전화)\n📞 1577-0199 (정신건강상담전화)\n📞 112 (경찰), 119 (소방/응급)",
            event="CRISIS_DETECTED"
        )
    
    # Leader selection
    leaders, recipe_id = swarm.select_leaders(query)
    
    # DRF
    context = drf.fetch_verified_law(query)
    if context.get("status") == "FAIL_CLOSED":
        return QueryResponse(
            status="FAIL_CLOSED",
            leaders=leaders,
            recipe_id=recipe_id,
            response=context.get("message", "DRF 검증 실패"),
            event=context.get("event")
        )
    
    # Generate
    response = swarm.generate_legal_advice(query, context, leaders)
    
    return QueryResponse(
        status="OK",
        leaders=leaders,
        recipe_id=recipe_id,
        response=response,
        event=None
    )