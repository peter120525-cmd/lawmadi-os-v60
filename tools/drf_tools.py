"""
Lawmadi OS v60 — DRF(법제처) 검색 도구 함수.
Gemini Function Calling에 노출되는 9개 DRF 검색 함수.
main.py에서 분리됨 (Item 7).

사용법:
    from tools.drf_tools import set_runtime, search_law_drf, ...
    set_runtime(RUNTIME)   # startup 시 호출
"""
import logging
from typing import Any, Dict, List

from utils.helpers import _extract_best_dict_list, _collect_texts_by_keys, _dedup_keep_order

logger = logging.getLogger("LawmadiOS.DRFTools")

# RUNTIME 참조 (setter 패턴으로 주입)
_RUNTIME: Dict[str, Any] = {}


def set_runtime(runtime: Dict[str, Any]) -> None:
    """main.py startup에서 RUNTIME 딕셔너리를 주입"""
    global _RUNTIME
    _RUNTIME = runtime


# ---------------------------------------------------------------------------
# DRF 검색 함수들
# ---------------------------------------------------------------------------

def search_law_drf(query: str) -> Dict[str, Any]:
    logger.info(f"🛠️ [L3 Strike] 법령 검색 호출: '{query}'")
    try:
        svc = _RUNTIME.get("search_service")
        if not svc:
            return {"result": "ERROR", "message": "SearchService 미초기화."}
        raw = svc.search_law(query)
        if not raw:
            return {"result": "NO_DATA", "message": "해당 키워드와 일치하는 법령이 없습니다."}
        return {"result": "FOUND", "content": raw, "source": "국가법령정보센터(법령)"}
    except Exception as e:
        return {"result": "ERROR", "message": str(e)}


def search_precedents_drf(query: str) -> Dict[str, Any]:
    logger.info(f"🛠️ [L3 Strike] 판례 검색 호출: '{query}'")
    try:
        drf_inst = _RUNTIME.get("drf")
        if not drf_inst:
            return {"result": "ERROR", "message": "DRF 커넥터 미초기화."}
        raw_result = drf_inst.search_precedents(query)
        items = _extract_best_dict_list(raw_result)
        if not items:
            return {"result": "NO_DATA", "message": "해당 키워드와 일치하는 판례가 없습니다."}
        summary_list = []
        for it in items[:3]:
            title = it.get("사건명", "제목 없음")
            case_no = it.get("사건번호", "번호 없음")
            content_keys = ["판시사항", "판결요지", "이유"]
            texts = _collect_texts_by_keys(it, content_keys)
            summary = "\n".join(_dedup_keep_order(texts))[:1000]
            summary_list.append(f"【사건명: {title} ({case_no})】\n{summary}")
        combined_content = "\n\n".join(summary_list)
        return {"result": "FOUND", "content": combined_content, "source": "국가법령정보센터(판례)"}
    except Exception as e:
        logger.error(f"🛠️ 판례 검색 실패: {e}")
        return {"result": "ERROR", "message": str(e)}


def search_admrul_drf(query: str) -> Dict[str, Any]:
    """행정규칙 검색 (SSOT #2)"""
    logger.info(f"🛠️ [L3 Strike] 행정규칙 검색 호출: '{query}'")
    try:
        svc = _RUNTIME.get("search_service")
        if not svc:
            return {"result": "ERROR", "message": "SearchService 미초기화."}
        raw = svc.search_admrul(query)
        if not raw:
            return {"result": "NO_DATA", "message": "해당 키워드와 일치하는 행정규칙이 없습니다."}
        return {"result": "FOUND", "content": raw, "source": "국가법령정보센터(행정규칙)"}
    except Exception as e:
        logger.error(f"🛠️ 행정규칙 검색 실패: {e}")
        return {"result": "ERROR", "message": str(e)}


def search_expc_drf(query: str) -> Dict[str, Any]:
    """법령해석례 검색 (SSOT #7)"""
    logger.info(f"🛠️ [L3 Strike] 법령해석례 검색 호출: '{query}'")
    try:
        svc = _RUNTIME.get("search_service")
        if not svc:
            return {"result": "ERROR", "message": "SearchService 미초기화."}
        raw = svc.search_expc(query)
        if not raw:
            return {"result": "NO_DATA", "message": "해당 키워드와 일치하는 법령해석례가 없습니다."}
        return {"result": "FOUND", "content": raw, "source": "국가법령정보센터(법령해석례)"}
    except Exception as e:
        logger.error(f"🛠️ 법령해석례 검색 실패: {e}")
        return {"result": "ERROR", "message": str(e)}


def search_constitutional_drf(query: str) -> Dict[str, Any]:
    """헌재결정례 검색 (SSOT #6)"""
    logger.info(f"🛠️ [L3 Strike] 헌재결정례 검색 호출: '{query}'")
    try:
        svc = _RUNTIME.get("search_service")
        if not svc:
            return {"result": "ERROR", "message": "SearchService 미초기화."}
        raw = svc.search_constitutional(query)
        if not raw:
            return {"result": "NO_DATA", "message": "해당 키워드와 일치하는 헌재결정례가 없습니다."}
        items = _extract_best_dict_list(raw)
        if not items:
            return {"result": "NO_DATA", "message": "헌재결정례를 찾을 수 없습니다."}
        summary_list = []
        for it in items[:3]:
            title = it.get("사건명", "제목 없음")
            case_no = it.get("사건번호", "번호 없음")
            content_keys = ["판시사항", "결정요지", "이유"]
            texts = _collect_texts_by_keys(it, content_keys)
            summary = "\n".join(_dedup_keep_order(texts))[:1000]
            summary_list.append(f"【사건명: {title} ({case_no})】\n{summary}")
        combined_content = "\n\n".join(summary_list)
        return {"result": "FOUND", "content": combined_content, "source": "국가법령정보센터(헌재결정례)"}
    except Exception as e:
        logger.error(f"🛠️ 헌재결정례 검색 실패: {e}")
        return {"result": "ERROR", "message": str(e)}


def search_ordinance_drf(query: str) -> Dict[str, Any]:
    """자치법규 검색 (SSOT #4)"""
    logger.info(f"🛠️ [L3 Strike] 자치법규 검색 호출: '{query}'")
    try:
        svc = _RUNTIME.get("search_service")
        if not svc:
            return {"result": "ERROR", "message": "SearchService 미초기화."}
        raw = svc.search_ordinance(query)
        if not raw:
            return {"result": "NO_DATA", "message": "해당 키워드와 일치하는 자치법규가 없습니다."}
        return {"result": "FOUND", "content": raw, "source": "국가법령정보센터(자치법규)"}
    except Exception as e:
        logger.error(f"🛠️ 자치법규 검색 실패: {e}")
        return {"result": "ERROR", "message": str(e)}


def search_legal_term_drf(query: str) -> Dict[str, Any]:
    """법령용어 검색 (SSOT #10)"""
    logger.info(f"🛠️ [L3 Strike] 법령용어 검색 호출: '{query}'")
    try:
        svc = _RUNTIME.get("search_service")
        if not svc:
            return {"result": "ERROR", "message": "SearchService 미초기화."}
        raw = svc.search_legal_term(query)
        if not raw:
            return {"result": "NO_DATA", "message": "해당 키워드와 일치하는 법령용어가 없습니다."}
        if isinstance(raw, dict) and "LsTrmService" in raw:
            term_data = raw["LsTrmService"]
            term_name_ko = term_data.get("법령용어명_한글", "")
            term_name_cn = term_data.get("법령용어명_한자", "")
            term_def = term_data.get("법령용어정의", "")
            term_source = term_data.get("출처", "")
            formatted = f"【{term_name_ko}】"
            if term_name_cn:
                formatted += f" ({term_name_cn})"
            formatted += f"\n\n정의: {term_def}"
            if term_source:
                formatted += f"\n출처: {term_source}"
            return {"result": "FOUND", "content": formatted, "source": "국가법령정보센터(법령용어)", "raw": raw}
        return {"result": "FOUND", "content": raw, "source": "국가법령정보센터(법령용어)"}
    except Exception as e:
        logger.error(f"🛠️ 법령용어 검색 실패: {e}")
        return {"result": "ERROR", "message": str(e)}


def search_admin_appeals_drf(doc_id: str) -> Dict[str, Any]:
    """행정심판례 검색 (SSOT #8) — 키워드 검색 미지원, 정확한 ID 필수"""
    logger.info(f"🛠️ [L3 Strike] 행정심판례 검색 호출: ID={doc_id}")
    try:
        svc = _RUNTIME.get("search_service")
        if not svc:
            return {"result": "ERROR", "message": "SearchService 미초기화."}
        raw = svc.search_admin_appeals(doc_id)
        if not raw:
            return {"result": "NO_DATA", "message": f"ID {doc_id}에 해당하는 행정심판례를 찾을 수 없습니다."}
        if isinstance(raw, dict) and "PrecService" in raw:
            prec_data = raw["PrecService"]
            case_name = prec_data.get("사건명", "제목 없음")
            case_no = prec_data.get("사건번호", "")
            decision_date = prec_data.get("선고일자", "")
            content = prec_data.get("사건개요", "") or prec_data.get("결정요지", "") or str(prec_data)[:500]
            formatted = f"【{case_name}】\n"
            if case_no:
                formatted += f"사건번호: {case_no}\n"
            if decision_date:
                formatted += f"결정일자: {decision_date}\n"
            formatted += f"\n{content[:1000]}"
            return {"result": "FOUND", "content": formatted, "source": "국가법령정보센터(행정심판례)", "raw": raw}
        return {"result": "FOUND", "content": raw, "source": "국가법령정보센터(행정심판례)"}
    except Exception as e:
        logger.error(f"🛠️ 행정심판례 검색 실패: {e}")
        return {"result": "ERROR", "message": str(e)}


def search_treaty_drf(doc_id: str) -> Dict[str, Any]:
    """조약 검색 (SSOT #9) — 키워드 검색 미지원, 정확한 ID 필수"""
    logger.info(f"🛠️ [L3 Strike] 조약 검색 호출: ID={doc_id}")
    try:
        svc = _RUNTIME.get("search_service")
        if not svc:
            return {"result": "ERROR", "message": "SearchService 미초기화."}
        raw = svc.search_treaty(doc_id)
        if not raw:
            return {"result": "NO_DATA", "message": f"ID {doc_id}에 해당하는 조약을 찾을 수 없습니다."}
        treaty_data = None
        if isinstance(raw, dict):
            if "BothTrtyService" in raw:
                treaty_data = raw["BothTrtyService"]
            elif "MultTrtyService" in raw:
                treaty_data = raw["MultTrtyService"]
        if treaty_data:
            treaty_name_ko = treaty_data.get("조약한글명", "") or treaty_data.get("조약명", "")
            treaty_name_en = treaty_data.get("조약영문명", "")
            treaty_no = treaty_data.get("조약번호", "")
            sign_date = treaty_data.get("서명일자", "")
            effect_date = treaty_data.get("발효일자", "")
            formatted = f"【{treaty_name_ko}】\n"
            if treaty_name_en:
                formatted += f"영문명: {treaty_name_en}\n"
            if treaty_no:
                formatted += f"조약번호: {treaty_no}\n"
            if sign_date:
                formatted += f"서명일자: {sign_date}\n"
            if effect_date:
                formatted += f"발효일자: {effect_date}\n"
            return {"result": "FOUND", "content": formatted, "source": "국가법령정보센터(조약)", "raw": raw}
        return {"result": "FOUND", "content": raw, "source": "국가법령정보센터(조약)"}
    except Exception as e:
        logger.error(f"🛠️ 조약 검색 실패: {e}")
        return {"result": "ERROR", "message": str(e)}
