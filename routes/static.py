"""Static page routes — no RUNTIME dependency."""
import os
from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from core.constants import OS_VERSION

router = APIRouter()

# Project root: routes/ is a subdirectory, so go up one level
_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))


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
async def serve_llms_txt():
    """llms.txt — machine-readable AI system specification"""
    for candidate in [
        os.path.join(_PROJECT_ROOT, "llms.txt"),
        os.path.join(_PROJECT_ROOT, "frontend", "public", "llms.txt"),
    ]:
        if os.path.exists(candidate):
            return FileResponse(candidate, media_type="text/plain; charset=utf-8")
    return JSONResponse(status_code=404, content={"error": "llms.txt not found"})


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


@router.get("/clevel-en")
async def serve_clevel_en():
    """C-Level page (English)"""
    frontend_path = os.path.join(_PROJECT_ROOT, "frontend", "public", "clevel-en.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "C-Level page not found", "version": OS_VERSION}


@router.get("/terms")
async def serve_terms():
    """Terms of service page"""
    frontend_path = os.path.join(_PROJECT_ROOT, "frontend", "public", "terms.html")
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
    "/clevel-en.html": "/clevel-en",
    "/index-en.html": "/en",
}

for _src, _dst in _HTML_REDIRECTS.items():
    def _make_redirect(dst=_dst):
        async def _redirect():
            return RedirectResponse(url=dst, status_code=301)
        return _redirect
    router.add_api_route(_src, _make_redirect(), methods=["GET"])
