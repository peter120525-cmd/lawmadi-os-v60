"""Static page routes — no RUNTIME dependency."""
import os
import logging
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from core.constants import OS_VERSION

logger = logging.getLogger("lawmadi.static")

router = APIRouter()

# Project root: routes/ is a subdirectory, so go up one level
_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))


def _log_ai_access(request: Request, file_name: str):
    """Log AI crawler access to llms.txt / llms-full.txt for analytics."""
    ua = request.headers.get("user-agent", "unknown")
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
    referer = request.headers.get("referer", "-")
    logger.info(
        "AI_DISCOVERY_ACCESS | file=%s | ip=%s | ua=%s | referer=%s",
        file_name, ip, ua, referer,
    )


@router.get("/")
async def serve_homepage():
    """Root route - serve homepage"""
    frontend_path = os.path.join(_PROJECT_ROOT, "frontend", "public", "index.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "Lawmadi OS v60 API", "version": OS_VERSION, "frontend": "https://lawmadi-db.web.app"}


@router.get("/en")
async def serve_homepage_en():
    """English homepage"""
    frontend_path = os.path.join(_PROJECT_ROOT, "frontend", "public", "index-en.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "Lawmadi OS v60 API (English)", "version": OS_VERSION}


# =============================================================
# LLM-readable reference files (no homepage link)
# lawmadi.com/llms.txt | /README.md | /license
# =============================================================

@router.get("/llms.txt")
async def serve_llms_txt(request: Request):
    """llms.txt — machine-readable AI system specification"""
    _log_ai_access(request, "llms.txt")
    for candidate in [
        os.path.join(_PROJECT_ROOT, "llms.txt"),
        os.path.join(_PROJECT_ROOT, "frontend", "public", "llms.txt"),
    ]:
        if os.path.exists(candidate):
            return FileResponse(candidate, media_type="text/plain; charset=utf-8")
    return JSONResponse(status_code=404, content={"error": "llms.txt not found"})


@router.get("/llms-full.txt")
async def serve_llms_full_txt(request: Request):
    """llms-full.txt — detailed AI system specification"""
    _log_ai_access(request, "llms-full.txt")
    for candidate in [
        os.path.join(_PROJECT_ROOT, "llms-full.txt"),
        os.path.join(_PROJECT_ROOT, "frontend", "public", "llms-full.txt"),
    ]:
        if os.path.exists(candidate):
            return FileResponse(candidate, media_type="text/plain; charset=utf-8")
    return JSONResponse(status_code=404, content={"error": "llms-full.txt not found"})


@router.get("/README.md")
async def serve_readme():
    """README.md — public system documentation"""
    for candidate in [
        os.path.join(_PROJECT_ROOT, "README.md"),
        os.path.join(_PROJECT_ROOT, "frontend", "public", "README.md"),
    ]:
        if os.path.exists(candidate):
            return FileResponse(candidate, media_type="text/plain; charset=utf-8")
    return JSONResponse(status_code=404, content={"error": "README.md not found"})


@router.get("/license")
async def serve_license():
    """license — proprietary license terms"""
    for candidate in [
        os.path.join(_PROJECT_ROOT, "license"),
        os.path.join(_PROJECT_ROOT, "frontend", "public", "license"),
    ]:
        if os.path.exists(candidate):
            return FileResponse(candidate, media_type="text/plain; charset=utf-8")
    return JSONResponse(status_code=404, content={"error": "license not found"})


@router.get("/leaders")
async def serve_leaders():
    """60 Leaders page"""
    leaders_path = os.path.join(_PROJECT_ROOT, "frontend", "public", "leaders.html")
    if os.path.exists(leaders_path):
        return FileResponse(leaders_path)
    return {"message": "Leaders page not found", "version": OS_VERSION}


@router.get("/about")
async def serve_about():
    """About page"""
    frontend_path = os.path.join(_PROJECT_ROOT, "frontend", "public", "about.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "Lawmadi OS About", "version": OS_VERSION}


@router.get("/about-en")
async def serve_about_en():
    """About page (English)"""
    frontend_path = os.path.join(_PROJECT_ROOT, "frontend", "public", "about-en.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "Lawmadi OS About", "version": OS_VERSION}


@router.get("/leaders-en")
async def serve_leaders_en():
    """60 Leaders page (English)"""
    frontend_path = os.path.join(_PROJECT_ROOT, "frontend", "public", "leaders-en.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "Leaders page not found", "version": OS_VERSION}


@router.get("/clevel")
async def serve_clevel():
    """C-Level page (Korean)"""
    frontend_path = os.path.join(_PROJECT_ROOT, "frontend", "public", "clevel.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "C-Level page not found", "version": OS_VERSION}


@router.get("/clevel-en")
async def serve_clevel_en():
    """C-Level page (English)"""
    frontend_path = os.path.join(_PROJECT_ROOT, "frontend", "public", "clevel-en.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "C-Level page not found", "version": OS_VERSION}


@router.get("/leader-profile.html")
async def serve_leader_profile():
    """Leader profile detail page (Korean)"""
    frontend_path = os.path.join(_PROJECT_ROOT, "frontend", "public", "leader-profile.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "Leader profile page not found", "version": OS_VERSION}


@router.get("/leader-profile-en.html")
async def serve_leader_profile_en():
    """Leader profile detail page (English)"""
    frontend_path = os.path.join(_PROJECT_ROOT, "frontend", "public", "leader-profile-en.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "Leader profile page not found", "version": OS_VERSION}


@router.get("/terms")
async def serve_terms():
    """Terms of service page"""
    frontend_path = os.path.join(_PROJECT_ROOT, "frontend", "public", "terms.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "Terms page not found", "version": OS_VERSION}


@router.get("/terms-en")
async def serve_terms_en():
    """Terms of service page (English)"""
    frontend_path = os.path.join(_PROJECT_ROOT, "frontend", "public", "terms-en.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "Terms page not found", "version": OS_VERSION}


@router.get("/privacy")
async def serve_privacy():
    """Privacy policy page"""
    frontend_path = os.path.join(_PROJECT_ROOT, "frontend", "public", "privacy.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "Privacy page not found", "version": OS_VERSION}


@router.get("/privacy-en")
async def serve_privacy_en():
    """Privacy policy page (English)"""
    frontend_path = os.path.join(_PROJECT_ROOT, "frontend", "public", "privacy-en.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "Privacy page not found", "version": OS_VERSION}


# =============================================================
# .html 확장자 경로 → 확장자 없는 경로로 리다이렉트
# 모바일/인앱 브라우저에서 .html 링크 호환성 보장
# =============================================================

_HTML_REDIRECTS = {
    "/terms.html": "/terms",
    "/privacy.html": "/privacy",
    "/about.html": "/about",
    "/about-en.html": "/about-en",
    "/leaders.html": "/leaders",
    "/leaders-en.html": "/leaders-en",
    "/clevel.html": "/clevel",
    "/clevel-en.html": "/clevel-en",
    "/terms-en.html": "/terms-en",
    "/privacy-en.html": "/privacy-en",
    "/index-en.html": "/en",
}

for _src, _dst in _HTML_REDIRECTS.items():
    def _make_redirect(dst=_dst):
        async def _redirect():
            return RedirectResponse(url=dst, status_code=301)
        return _redirect
    router.add_api_route(_src, _make_redirect(), methods=["GET"])
