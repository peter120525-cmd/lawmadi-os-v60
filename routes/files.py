"""File upload, document analysis, PDF export routes."""
import os
import re
import json
import uuid
import hashlib
import logging
import datetime
import traceback
import mimetypes
from typing import Any, Dict
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Request, HTTPException, File, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from google.genai import types as genai_types
from slowapi import Limiter
from slowapi.util import get_remote_address

from core.constants import OS_VERSION, GEMINI_MODEL
from core.model_fallback import get_model

router = APIRouter()
logger = logging.getLogger("LawmadiOS.Files")

# Project root for font paths etc.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))

_RUNTIME: Dict[str, Any] = {}
limiter = Limiter(key_func=get_remote_address)


def set_dependencies(runtime, rate_limiter=None):
    """Inject shared runtime objects from main.py at startup."""
    global _RUNTIME, limiter
    _RUNTIME = runtime
    if rate_limiter:
        limiter = rate_limiter


def _optional_import(module_path, attr=None):
    """Fail-soft optional import — returns None on failure."""
    try:
        from importlib import import_module
        module = import_module(module_path)
        return getattr(module, attr) if attr else module
    except Exception:
        return None


# =============================================================
# Upload
# =============================================================

@router.post("/upload")
@limiter.limit("10/hour")
async def upload_document(request: Request, file: UploadFile = File(...)):
    """
    Upload user document/image for legal analysis.

    Supported files:
    - Images: jpg, jpeg, png, webp
    - Documents: pdf

    Returns:
        {
            "ok": true,
            "file_id": "abc123",
            "filename": "contract.pdf",
            "file_size": 1234567,
            "analysis_url": "/analyze-document/abc123"
        }
    """
    trace = str(uuid.uuid4())[:8]
    logger.info(f"[Upload] trace={trace}, filename={file.filename}")

    try:
        # 1. File validation
        if not file.filename:
            raise HTTPException(status_code=400, detail="파일명이 없습니다.")

        # Allowed file types (extension + MIME cross-validation)
        _ext_to_mime = {
            '.jpg': {'image/jpeg'},
            '.jpeg': {'image/jpeg'},
            '.png': {'image/png'},
            '.webp': {'image/webp'},
            '.pdf': {'application/pdf'},
        }
        allowed_mimes = {'image/jpeg', 'image/png', 'image/webp', 'application/pdf'}
        file_ext = Path(file.filename).suffix.lower()

        if file_ext not in _ext_to_mime:
            raise HTTPException(
                status_code=400,
                detail=f"지원하지 않는 파일 형식입니다. 허용: {', '.join(_ext_to_mime.keys())}"
            )

        # MIME type validation + extension-MIME cross-check
        if file.content_type and file.content_type not in allowed_mimes:
            raise HTTPException(
                status_code=400,
                detail=f"지원하지 않는 MIME 타입입니다: {file.content_type}"
            )
        if file.content_type and file.content_type not in _ext_to_mime[file_ext]:
            raise HTTPException(
                status_code=400,
                detail="파일 확장자와 실제 파일 형식이 일치하지 않습니다."
            )

        # 2. Read file and generate hash
        file_content = await file.read()
        file_size = len(file_content)

        # File size limit (10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        if file_size > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"파일 크기가 너무 큽니다. 최대: {max_size / 1024 / 1024:.1f}MB"
            )

        # SHA-256 hash (duplicate prevention)
        file_hash = hashlib.sha256(file_content).hexdigest()

        # 3. Save file
        uploads_dir = Path("uploads")
        uploads_dir.mkdir(exist_ok=True)

        # Filename: {hash[:8]}_{sanitized_original}
        _orig = Path(file.filename).name  # strip directory separators
        _orig = re.sub(r'[\x00/\\:*?"<>|]', '_', _orig)[:100]  # remove dangerous chars, limit length
        safe_filename = f"{file_hash[:8]}_{_orig}"
        file_path = uploads_dir / safe_filename

        async with aiofiles.open(file_path, "wb") as f:
            await f.write(file_content)

        logger.info(f"[Upload] File saved: {file_path} ({file_size} bytes)")

        # 4. Save metadata to DB (optional)
        file_id = file_hash[:16]  # 16-char ID
        _raw_ip = request.client.host if request else "unknown"
        user_ip = hashlib.sha256(_raw_ip.encode()).hexdigest() if _raw_ip != "unknown" else "unknown"

        db_client_v2 = _optional_import("connectors.db_client_v2")
        if db_client_v2 and hasattr(db_client_v2, "execute"):
            try:
                # Expiry: 7 days
                expires_at = datetime.datetime.now() + datetime.timedelta(days=7)

                db_result = db_client_v2.execute(
                    """
                    INSERT INTO uploaded_documents
                    (filename, file_path, file_type, file_size, file_hash, user_ip, status, expires_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (file_hash) DO UPDATE SET uploaded_at = CURRENT_TIMESTAMP
                    RETURNING id
                    """,
                    (
                        file.filename,
                        str(file_path),
                        file.content_type or mimetypes.guess_type(file.filename)[0],
                        file_size,
                        file_hash,
                        user_ip,
                        'pending',
                        expires_at
                    ),
                    fetch="one"
                )

                if db_result.get("ok") and db_result.get("data"):
                    db_file_id = db_result["data"][0]
                    logger.info(f"[Upload] DB saved: ID={db_file_id}")
            except Exception as db_error:
                logger.warning(f"[Upload] DB save failed (ignored): {db_error}")

        # 5. Response
        return {
            "ok": True,
            "file_id": file_id,
            "filename": file.filename,
            "file_size": file_size,
            "file_hash": file_hash,
            "analysis_url": f"/analyze-document/{file_id}",
            "trace_id": trace
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Upload] Upload failed: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="파일 업로드 처리 중 오류가 발생했습니다.")


# =============================================================
# Analyze Document
# =============================================================

@router.post("/analyze-document/{file_id}")
@limiter.limit("10/hour")
async def analyze_document(request: Request, file_id: str, analysis_type: str = "general"):
    """
    Analyze uploaded document (legal analysis).

    Args:
        file_id: File ID from upload response
        analysis_type: Analysis type (general, contract, risk_assessment)

    Returns:
        {
            "ok": true,
            "file_id": "abc123",
            "analysis": {
                "summary": "...",
                "legal_issues": [...],
                "recommendations": [...],
                "risk_level": "medium"
            }
        }
    """
    trace = str(uuid.uuid4())[:8]
    logger.info(f"[Analyze] trace={trace}, file_id={file_id}, type={analysis_type}")

    try:
        # 1. Find file (path traversal prevention: alphanumeric only, exact match)
        safe_id = re.sub(r'[^a-fA-F0-9]', '', file_id[:64])
        if len(safe_id) < 8:
            raise HTTPException(status_code=400, detail="유효하지 않은 파일 ID입니다.")
        uploads_dir = Path("uploads").resolve()
        matching_files = [
            f for f in uploads_dir.iterdir()
            if f.is_file() and (f.name.startswith(safe_id + "_") or f.name == safe_id)
        ]

        if not matching_files:
            raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
        if len(matching_files) > 1:
            logger.warning(f"[Analyze] Multiple file match: {safe_id}, {len(matching_files)} files — 첫 번째 파일 사용")

        file_path = matching_files[0].resolve()
        # Path traversal prevention: verify inside uploads directory (symlink defense)
        if not file_path.is_relative_to(uploads_dir):
            raise HTTPException(status_code=403, detail="접근이 거부되었습니다.")
        logger.info(f"[Analyze] File found: {file_path}")

        # 2. Gemini client check
        gc = _RUNTIME.get("genai_client")
        if not gc:
            raise HTTPException(status_code=503, detail="AI 분석 서비스가 현재 이용 불가합니다.")

        # 3. Process by file type
        file_ext = file_path.suffix.lower()

        if file_ext in ['.jpg', '.jpeg', '.png', '.webp']:
            # Image analysis (Gemini Vision)
            analysis_result = await _analyze_image_document(file_path, analysis_type)
        elif file_ext == '.pdf':
            # PDF analysis
            analysis_result = await _analyze_pdf_document(file_path, analysis_type)
        else:
            raise HTTPException(status_code=400, detail="지원하지 않는 파일 형식입니다.")

        # 4. DB update (save analysis result)
        db_client_v2 = _optional_import("connectors.db_client_v2")
        if db_client_v2 and hasattr(db_client_v2, "execute"):
            try:
                db_client_v2.execute(
                    """
                    UPDATE uploaded_documents
                    SET
                        status = 'completed',
                        analysis_result = %s,
                        analysis_summary = %s,
                        legal_category = %s,
                        risk_level = %s,
                        analyzed_at = CURRENT_TIMESTAMP,
                        gemini_model = %s
                    WHERE file_hash LIKE %s
                    """,
                    (
                        json.dumps(analysis_result, ensure_ascii=False),
                        analysis_result.get("summary", "")[:500],
                        analysis_result.get("legal_category", "일반"),
                        analysis_result.get("risk_level", "medium"),
                        GEMINI_MODEL,
                        f"{safe_id}%"
                    ),
                    fetch="none"
                )
                logger.info("[Analyze] DB update complete")
            except Exception as db_error:
                logger.warning(f"[Analyze] DB update failed (ignored): {db_error}")

        # 5. Response
        return {
            "ok": True,
            "file_id": file_id,
            "filename": file_path.name,
            "analysis": analysis_result,
            "trace_id": trace
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Analyze] Analysis failed: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="문서 분석 처리 중 오류가 발생했습니다.")


# =============================================================
# Image Document Analysis (Gemini Vision)
# =============================================================

async def _analyze_image_document(file_path: Path, analysis_type: str) -> Dict[str, Any]:
    """Analyze image document via Gemini Vision."""
    logger.info(f"[Analyze] Image analysis started: {file_path.name}")

    gc = _RUNTIME.get("genai_client")

    # Read image file
    with open(file_path, "rb") as f:
        image_data = f.read()

    # Build prompt
    if analysis_type == "contract":
        prompt = """
이 이미지에 있는 계약서를 분석해주세요.

다음 형식으로 JSON 응답을 제공해주세요:
{
    "summary": "계약서 요약 (3-5문장)",
    "contract_type": "계약서 종류 (예: 임대차계약, 근로계약, 매매계약 등)",
    "parties": ["당사자1", "당사자2"],
    "key_terms": [
        {"term": "조항명", "content": "내용", "issue": "문제점 또는 확인 필요 사항"}
    ],
    "legal_issues": [
        "법률적 문제점 1",
        "법률적 문제점 2"
    ],
    "risk_level": "low/medium/high/critical",
    "recommendations": [
        "권고사항 1",
        "권고사항 2"
    ],
    "legal_category": "민사/형사/행정/노동 등"
}
"""
    elif analysis_type == "risk_assessment":
        prompt = """
이 문서의 법률적 위험도를 평가해주세요.

다음 형식으로 JSON 응답을 제공해주세요:
{
    "summary": "문서 요약",
    "risk_level": "low/medium/high/critical",
    "risk_factors": [
        {"factor": "위험 요소", "severity": "심각도", "description": "설명"}
    ],
    "legal_issues": ["법률적 쟁점"],
    "recommendations": ["권고사항"],
    "legal_category": "법률 분야"
}
"""
    else:  # general
        prompt = """
이 문서를 법률적 관점에서 분석해주세요.

다음 형식으로 JSON 응답을 제공해주세요:
{
    "summary": "문서 요약 (3-5문장)",
    "document_type": "문서 종류",
    "legal_issues": ["법률적 쟁점 1", "법률적 쟁점 2"],
    "risk_level": "low/medium/high/critical",
    "recommendations": ["권고사항 1", "권고사항 2"],
    "legal_category": "민사/형사/행정/노동 등",
    "key_points": ["핵심 내용 1", "핵심 내용 2"]
}
"""

    # Gemini Vision call (이벤트 루프 블로킹 방지)
    image_part = genai_types.Part.from_bytes(data=image_data, mime_type=f"image/{file_path.suffix[1:]}")
    import asyncio
    _model = get_model()
    response = await asyncio.to_thread(
        gc.models.generate_content,
        model=_model,
        contents=[prompt, image_part],
    )

    # Parse response
    result_text = response.text.strip()

    # Extract JSON (strip ```json ... ```)
    if "```json" in result_text:
        result_text = result_text.split("```json")[1].split("```")[0].strip()
    elif "```" in result_text:
        result_text = result_text.split("```")[1].split("```")[0].strip()

    try:
        analysis_result = json.loads(result_text)
    except json.JSONDecodeError:
        # JSON parse failure — return raw text
        analysis_result = {
            "summary": result_text[:500],
            "legal_issues": ["분석 결과를 구조화하지 못했습니다."],
            "risk_level": "medium",
            "recommendations": ["전문가 확인이 필요합니다."],
            "legal_category": "일반",
            "raw_response": result_text
        }

    logger.info("[Analyze] Image analysis complete")
    return analysis_result


# =============================================================
# PDF Document Analysis
# =============================================================

async def _analyze_pdf_document(file_path: Path, analysis_type: str) -> Dict[str, Any]:
    """
    Analyze PDF document.
    Uses PyPDF2 for text extraction, then Gemini for analysis.
    """
    logger.info(f"[Analyze] PDF analysis: {file_path.name}")

    # Check if PyPDF2 is installed
    try:
        import PyPDF2

        # Extract PDF text
        with open(file_path, "rb") as f:
            pdf_reader = PyPDF2.PdfReader(f)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"

        logger.info(f"[Analyze] PDF text extracted: {len(text)} chars")

        # Gemini text analysis
        gc = _RUNTIME.get("genai_client")

        prompt = f"""
다음 PDF 문서를 법률적 관점에서 분석해주세요.

문서 내용:
{text[:10000]}

다음 형식으로 JSON 응답을 제공해주세요:
{{
    "summary": "문서 요약",
    "document_type": "문서 종류",
    "legal_issues": ["법률적 쟁점"],
    "risk_level": "low/medium/high/critical",
    "recommendations": ["권고사항"],
    "legal_category": "법률 분야",
    "key_points": ["핵심 내용"]
}}
"""

        import asyncio
        _model = get_model()
        response = await asyncio.to_thread(
            gc.models.generate_content,
            model=_model,
            contents=prompt,
        )
        result_text = response.text.strip()

        # Extract JSON
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()

        try:
            analysis_result = json.loads(result_text)
        except json.JSONDecodeError:
            analysis_result = {
                "summary": result_text[:500],
                "legal_issues": ["분석 결과를 구조화하지 못했습니다."],
                "risk_level": "medium",
                "recommendations": ["전문가 확인이 필요합니다."],
                "legal_category": "일반"
            }

        return analysis_result

    except ImportError:
        logger.warning("[Analyze] PyPDF2 not installed")
        return {
            "summary": "PDF 분석 기능은 PyPDF2 패키지가 필요합니다.",
            "legal_issues": ["PDF 텍스트 추출 불가"],
            "risk_level": "medium",
            "recommendations": ["이미지 형식으로 변환하여 업로드하시거나, 관리자에게 문의하세요."],
            "legal_category": "일반"
        }


# =============================================================
# PDF Export
# =============================================================

@router.post("/export-pdf")
@limiter.limit("20/hour")
async def export_pdf(request: Request):
    """
    Convert legal document text to downloadable PDF.

    Request body:
        {
            "title": "고소장",
            "content": "고 소 장\\n\\n고소인\\n  성명: 홍길동\\n..."
        }

    Returns:
        PDF file (application/pdf)
    """
    try:
        data = await request.json()
        title = (data.get("title", "") or "법률문서").strip()
        content = (data.get("content", "") or "").strip()

        if not content:
            raise HTTPException(status_code=400, detail="content 필드가 비어 있습니다.")

        # Content size limit: 100KB
        if len(content) > 100 * 1024:
            raise HTTPException(status_code=400, detail="콘텐츠 크기가 너무 큽니다. 최대 100KB까지 허용됩니다.")

        from fpdf import FPDF

        FONT_PATH = os.path.join(_PROJECT_ROOT, "fonts", "NanumGothic.ttf")
        if not os.path.exists(FONT_PATH):
            raise HTTPException(status_code=500, detail="PDF 폰트 파일이 없습니다. 관리자에게 문의하세요.")

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_page()
        pdf.add_font("NotoSansKR", "", FONT_PATH)

        # Title
        pdf.set_font("NotoSansKR", "", 18)
        pdf.cell(0, 15, title, new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(5)

        # Body
        pdf.set_font("NotoSansKR", "", 11)
        for line in content.split("\n"):
            if line.strip() == "":
                pdf.ln(7)
            else:
                line_width = pdf.get_string_width(line)
                usable_width = pdf.w - pdf.l_margin - pdf.r_margin
                if line_width <= usable_width:
                    pdf.cell(0, 7, line, new_x="LMARGIN", new_y="NEXT")
                else:
                    pdf.multi_cell(0, 7, line.strip())

        # Disclaimer
        pdf.ln(10)
        pdf.set_font("NotoSansKR", "", 9)
        disclaimer = (
            "※ 본 문서는 Lawmadi OS가 생성한 참고용 초안이며, 법적 효력을 보장하지 않습니다. "
            "반드시 변호사 등 법률 전문가의 검토를 받으시기 바랍니다."
        )
        pdf.multi_cell(0, 6, disclaimer)

        # Save and return file
        safe_title = re.sub(r'[^\w가-힣\s-]', '', title).strip() or "document"
        filename = f"{safe_title}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join("temp", filename)

        # Ensure temp directory exists
        os.makedirs("temp", exist_ok=True)

        pdf.output(filepath)

        logger.info(f"[PDF] Generated: {filename}")

        return FileResponse(
            path=filepath,
            filename=filename,
            media_type="application/pdf",
            background=BackgroundTask(lambda: os.remove(filepath) if os.path.exists(filepath) else None),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PDF] Generation failed: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="PDF 생성 중 오류가 발생했습니다.")
