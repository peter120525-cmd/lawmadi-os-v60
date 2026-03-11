"""File upload, document analysis, PDF export, document generation, forms search routes."""
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
                        get_model(),
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
        config=genai_types.GenerateContentConfig(
            thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
        ),
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
            config=genai_types.GenerateContentConfig(
                thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
            ),
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
# PDF Export (Enhanced with templates)
# =============================================================

# Document types and their Korean/English labels
_DOC_TYPES = {
    "complaint": {"ko": "고소장", "en": "Criminal Complaint"},
    "petition": {"ko": "소장", "en": "Civil Petition"},
    "answer": {"ko": "답변서", "en": "Answer Brief"},
    "notice": {"ko": "내용증명", "en": "Certified Notice"},
    "withdrawal": {"ko": "고소취하서", "en": "Complaint Withdrawal"},
    "appeal": {"ko": "탄원서", "en": "Appeal/Petition Letter"},
    "demand": {"ko": "최고서", "en": "Demand Letter"},
    "agreement": {"ko": "합의서", "en": "Settlement Agreement"},
    "opinion": {"ko": "법률의견서", "en": "Legal Opinion"},
    "analysis": {"ko": "법률 분석", "en": "Legal Analysis"},
}


class _LawmadiPDF:
    """Enhanced PDF generator with legal document templates."""

    def __init__(self, lang: str = "ko"):
        from fpdf import FPDF

        self.lang = lang
        self.pdf = FPDF()
        self.pdf.set_auto_page_break(auto=True, margin=25)

        font_path = os.path.join(_PROJECT_ROOT, "fonts", "NanumGothic.ttf")
        if not os.path.exists(font_path):
            raise HTTPException(
                status_code=500,
                detail="PDF 폰트 파일이 없습니다." if lang == "ko"
                else "PDF font file not found.",
            )
        self.pdf.add_font("NotoSansKR", "", font_path)

    def _header_footer(self, title: str, doc_type: str):
        """Register header/footer callbacks."""
        pdf = self.pdf
        lang = self.lang

        def header():
            pdf.set_font("NotoSansKR", "", 8)
            pdf.set_text_color(130, 130, 130)
            label = _DOC_TYPES.get(doc_type, {}).get(lang, doc_type)
            pdf.cell(0, 6, f"Lawmadi OS  |  {label}", align="L")
            pdf.ln(3)
            # Thin line under header
            pdf.set_draw_color(200, 200, 200)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(6)
            pdf.set_text_color(0, 0, 0)

        def footer():
            pdf.set_y(-20)
            pdf.set_font("NotoSansKR", "", 8)
            pdf.set_text_color(150, 150, 150)
            date_str = datetime.datetime.now().strftime("%Y-%m-%d")
            page_text = f"{date_str}  |  {pdf.page_no()}"
            pdf.cell(0, 6, page_text, align="C")
            pdf.set_text_color(0, 0, 0)

        pdf.header = header
        pdf.footer = footer

    def generate(
        self,
        title: str,
        content: str,
        doc_type: str = "analysis",
        sections: list | None = None,
    ) -> str:
        """
        Generate a formatted PDF and return the file path.

        Args:
            title: Document title
            content: Main content text
            doc_type: Document type key (from _DOC_TYPES)
            sections: Optional structured sections
                      [{"heading": "...", "body": "..."}, ...]
        """
        pdf = self.pdf
        self._header_footer(title, doc_type)

        pdf.add_page()

        # === Title ===
        pdf.set_font("NotoSansKR", "", 20)
        pdf.cell(0, 14, title, new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(3)

        # Title underline
        pdf.set_draw_color(60, 60, 60)
        cx = pdf.w / 2
        pdf.line(cx - 40, pdf.get_y(), cx + 40, pdf.get_y())
        pdf.ln(8)

        # === Date line ===
        pdf.set_font("NotoSansKR", "", 10)
        pdf.set_text_color(100, 100, 100)
        date_label = "작성일" if self.lang == "ko" else "Date"
        pdf.cell(
            0, 7,
            f"{date_label}: {datetime.datetime.now().strftime('%Y년 %m월 %d일' if self.lang == 'ko' else '%B %d, %Y')}",
            new_x="LMARGIN", new_y="NEXT", align="R",
        )
        pdf.set_text_color(0, 0, 0)
        pdf.ln(4)

        # === Structured sections (if provided) ===
        if sections:
            for sec in sections:
                heading = sec.get("heading", "")
                body = sec.get("body", "")
                if heading:
                    pdf.set_font("NotoSansKR", "", 13)
                    pdf.set_text_color(30, 30, 30)
                    pdf.cell(0, 10, heading, new_x="LMARGIN", new_y="NEXT")
                    # Section underline
                    pdf.set_draw_color(180, 180, 180)
                    pdf.line(
                        pdf.l_margin, pdf.get_y(),
                        pdf.l_margin + 50, pdf.get_y(),
                    )
                    pdf.ln(4)
                    pdf.set_text_color(0, 0, 0)
                if body:
                    pdf.set_font("NotoSansKR", "", 11)
                    self._render_body(body)
                    pdf.ln(4)
        else:
            # === Plain content ===
            pdf.set_font("NotoSansKR", "", 11)
            self._render_body(content)

        # === Signature area (for formal documents) ===
        formal_types = {"complaint", "petition", "answer", "notice",
                        "withdrawal", "appeal", "demand", "agreement"}
        if doc_type in formal_types:
            self._add_signature_area()

        # === Disclaimer ===
        pdf.ln(10)
        pdf.set_draw_color(200, 200, 200)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(4)
        pdf.set_font("NotoSansKR", "", 8)
        pdf.set_text_color(130, 130, 130)
        if self.lang == "ko":
            disclaimer = (
                "※ 본 문서는 Lawmadi OS가 생성한 참고용 초안이며, 법적 효력을 보장하지 않습니다. "
                "반드시 변호사 등 법률 전문가의 검토를 받으시기 바랍니다."
            )
        else:
            disclaimer = (
                "※ This document is a reference draft generated by Lawmadi OS and does not guarantee legal effect. "
                "Please consult a licensed attorney before use."
            )
        pdf.multi_cell(0, 5, disclaimer)
        pdf.set_text_color(0, 0, 0)

        # === Save ===
        safe_title = re.sub(r'[^\w가-힣\s-]', '', title).strip() or "document"
        filename = f"{safe_title}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join("temp", filename)
        os.makedirs("temp", exist_ok=True)
        pdf.output(filepath)
        return filepath

    def _render_body(self, text: str):
        """Render body text with smart paragraph handling."""
        pdf = self.pdf
        usable_w = pdf.w - pdf.l_margin - pdf.r_margin
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped == "":
                pdf.ln(5)
            elif stripped.startswith("##"):
                # Markdown-style sub-heading
                pdf.set_font("NotoSansKR", "", 12)
                pdf.cell(0, 8, stripped.lstrip("#").strip(), new_x="LMARGIN", new_y="NEXT")
                pdf.ln(2)
                pdf.set_font("NotoSansKR", "", 11)
            elif stripped.startswith("- ") or stripped.startswith("• "):
                # Bullet point
                pdf.cell(6, 7, "•")
                bullet_text = stripped[2:]
                if pdf.get_string_width(bullet_text) <= usable_w - 6:
                    pdf.cell(0, 7, bullet_text, new_x="LMARGIN", new_y="NEXT")
                else:
                    pdf.multi_cell(usable_w - 6, 7, bullet_text)
            else:
                if pdf.get_string_width(line) <= usable_w:
                    pdf.cell(0, 7, line, new_x="LMARGIN", new_y="NEXT")
                else:
                    pdf.multi_cell(0, 7, line.strip())

    def _add_signature_area(self):
        """Add a signature/seal area for formal legal documents."""
        pdf = self.pdf
        pdf.ln(20)
        pdf.set_font("NotoSansKR", "", 11)
        if self.lang == "ko":
            pdf.cell(0, 8, f"{datetime.datetime.now().strftime('%Y년  %m월  %d일')}", new_x="LMARGIN", new_y="NEXT", align="R")
            pdf.ln(12)
            pdf.cell(0, 8, "위  작성자", new_x="LMARGIN", new_y="NEXT", align="R")
            pdf.ln(4)
            pdf.cell(0, 8, "성명:                          (서명 또는 날인)", new_x="LMARGIN", new_y="NEXT", align="R")
        else:
            pdf.cell(0, 8, f"Date: {datetime.datetime.now().strftime('%B %d, %Y')}", new_x="LMARGIN", new_y="NEXT", align="R")
            pdf.ln(12)
            pdf.cell(0, 8, "Name: ________________________", new_x="LMARGIN", new_y="NEXT", align="R")
            pdf.ln(4)
            pdf.cell(0, 8, "Signature: ________________________", new_x="LMARGIN", new_y="NEXT", align="R")


@router.post("/export-pdf")
@limiter.limit("20/hour")
async def export_pdf(request: Request):
    """
    Convert legal document text to downloadable PDF.

    Request body:
        {
            "title": "고소장",
            "content": "고 소 장\\n\\n고소인\\n  성명: 홍길동\\n...",
            "doc_type": "complaint",     // optional (default: "analysis")
            "lang": "ko",               // optional (default: "ko")
            "sections": [               // optional structured sections
                {"heading": "당사자", "body": "고소인: ...\\n피고소인: ..."},
                {"heading": "고소 취지", "body": "..."},
                {"heading": "고소 사실", "body": "..."}
            ]
        }

    Returns:
        PDF file (application/pdf)
    """
    try:
        data = await request.json()
        title = (data.get("title", "") or "법률문서").strip()
        content = (data.get("content", "") or "").strip()
        doc_type = (data.get("doc_type", "") or "analysis").strip()
        lang = (data.get("lang", "") or "ko").strip()
        sections = data.get("sections") or None

        if not content and not sections:
            raise HTTPException(status_code=400, detail="content 또는 sections 필드가 필요합니다.")

        # Content size limit: 100KB
        total_size = len(content)
        if sections:
            total_size += sum(len(s.get("body", "")) for s in sections)
        if total_size > 100 * 1024:
            raise HTTPException(status_code=400, detail="콘텐츠 크기가 너무 큽니다. 최대 100KB까지 허용됩니다.")

        gen = _LawmadiPDF(lang=lang)
        filepath = gen.generate(
            title=title, content=content,
            doc_type=doc_type, sections=sections,
        )

        filename = os.path.basename(filepath)
        logger.info(f"[PDF] Generated: {filename} (type={doc_type})")

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


# =============================================================
# Advanced Document Generation (Gemini-powered)
# =============================================================

# Document generation prompts per type
_DOC_PROMPTS = {
    "complaint": {
        "ko": (
            "다음 정보를 바탕으로 한국 형사소송법에 따른 **고소장** 초안을 작성해 주세요.\n"
            "형식: 고소인/피고소인 인적사항, 고소 취지, 고소 사실(육하원칙), 관련 법조문, 증거방법, 결론.\n"
            "각 섹션은 ##으로 구분해 주세요."
        ),
        "en": (
            "Based on the following information, draft a **Criminal Complaint** under Korean criminal procedure.\n"
            "Format: Complainant/Respondent details, Purpose, Facts (5W1H), Relevant statutes, Evidence, Conclusion.\n"
            "Separate each section with ##."
        ),
    },
    "petition": {
        "ko": (
            "다음 정보를 바탕으로 한국 민사소송법에 따른 **소장** 초안을 작성해 주세요.\n"
            "형식: 원고/피고 인적사항, 청구 취지, 청구 원인(사실관계+법적 근거), 증거방법, 결론.\n"
            "각 섹션은 ##으로 구분해 주세요."
        ),
        "en": (
            "Based on the following information, draft a **Civil Petition** under Korean civil procedure.\n"
            "Format: Plaintiff/Defendant details, Claims, Cause of Action (facts + legal basis), Evidence, Conclusion.\n"
            "Separate each section with ##."
        ),
    },
    "notice": {
        "ko": (
            "다음 정보를 바탕으로 **내용증명** 초안을 작성해 주세요.\n"
            "형식: 발신인/수신인 정보, 제목, 본문(요구사항+법적근거+이행기한+불이행시 조치), 결론.\n"
            "각 섹션은 ##으로 구분해 주세요."
        ),
        "en": (
            "Based on the following information, draft a **Certified Notice (내용증명)** under Korean law.\n"
            "Format: Sender/Recipient, Subject, Body (demand + legal basis + deadline + consequences), Conclusion.\n"
            "Separate each section with ##."
        ),
    },
    "answer": {
        "ko": (
            "다음 정보를 바탕으로 민사 **답변서** 초안을 작성해 주세요.\n"
            "형식: 사건번호, 원고/피고, 청구 취지에 대한 답변, 청구 원인에 대한 답변, 항변사항, 증거방법.\n"
            "각 섹션은 ##으로 구분해 주세요."
        ),
        "en": (
            "Based on the following information, draft an **Answer Brief** under Korean civil procedure.\n"
            "Format: Case number, parties, response to claims, defenses, evidence.\n"
            "Separate each section with ##."
        ),
    },
    "appeal": {
        "ko": (
            "다음 정보를 바탕으로 **탄원서** 초안을 작성해 주세요.\n"
            "형식: 수신(법원/검찰), 사건번호, 탄원인 정보, 탄원 취지, 탄원 사유(구체적 정상참작 사유), 결론.\n"
            "각 섹션은 ##으로 구분해 주세요."
        ),
        "en": (
            "Based on the following information, draft a **Petition/Appeal Letter** under Korean law.\n"
            "Format: Recipient (court/prosecution), Case number, Petitioner, Purpose, Reasons, Conclusion.\n"
            "Separate each section with ##."
        ),
    },
    "demand": {
        "ko": (
            "다음 정보를 바탕으로 **최고서** 초안을 작성해 주세요.\n"
            "형식: 발신인/수신인, 제목, 요구사항, 법적 근거, 이행기한, 불이행시 법적조치 안내.\n"
            "각 섹션은 ##으로 구분해 주세요."
        ),
        "en": (
            "Based on the following information, draft a **Demand Letter** under Korean law.\n"
            "Format: Sender/Recipient, Subject, Demands, Legal basis, Deadline, Consequences.\n"
            "Separate each section with ##."
        ),
    },
    "agreement": {
        "ko": (
            "다음 정보를 바탕으로 **합의서** 초안을 작성해 주세요.\n"
            "형식: 당사자(갑/을), 합의 배경, 합의 조건(항목별), 손해배상/위약금, 비밀유지, 효력발생.\n"
            "각 섹션은 ##으로 구분해 주세요."
        ),
        "en": (
            "Based on the following information, draft a **Settlement Agreement** under Korean law.\n"
            "Format: Parties, Background, Terms (itemized), Damages/Penalties, Confidentiality, Effective date.\n"
            "Separate each section with ##."
        ),
    },
    "opinion": {
        "ko": (
            "다음 정보를 바탕으로 **법률의견서** 초안을 작성해 주세요.\n"
            "형식: 의뢰인/의뢰사항, 사실관계 요약, 관련 법령 검토, 판례 분석, 법적 의견, 결론 및 권고.\n"
            "각 섹션은 ##으로 구분해 주세요."
        ),
        "en": (
            "Based on the following information, draft a **Legal Opinion** under Korean law.\n"
            "Format: Client/Matter, Facts, Legal analysis, Case law, Opinion, Conclusion & Recommendations.\n"
            "Separate each section with ##."
        ),
    },
}


@router.post("/generate-document")
@limiter.limit("10/hour")
async def generate_document(request: Request):
    """
    Generate a structured legal document using Gemini.

    Request body:
        {
            "doc_type": "complaint",     // required — see _DOC_TYPES keys
            "context": "사기 피해...",     // required — user's situation/facts
            "lang": "ko",               // optional (default: "ko")
            "extra_instructions": ""     // optional — additional user instructions
        }

    Returns:
        {
            "doc_type": "complaint",
            "title": "고소장",
            "content": "...",
            "sections": [...],
            "download_ready": true
        }
    """
    try:
        data = await request.json()
        doc_type = (data.get("doc_type", "") or "").strip()
        context = (data.get("context", "") or "").strip()
        lang = (data.get("lang", "") or "ko").strip()
        extra = (data.get("extra_instructions", "") or "").strip()

        if not doc_type or doc_type not in _DOC_TYPES:
            valid = ", ".join(_DOC_TYPES.keys())
            raise HTTPException(
                status_code=400,
                detail=f"유효한 doc_type을 지정하세요: {valid}",
            )
        if not context:
            raise HTTPException(status_code=400, detail="context (상황/사실관계)가 필요합니다.")
        if len(context) > 10000:
            raise HTTPException(status_code=400, detail="context가 너무 깁니다. 최대 10,000자.")

        # Build prompt
        doc_prompt = _DOC_PROMPTS.get(doc_type, {}).get(lang, "")
        if not doc_prompt:
            # Fallback generic prompt
            type_label = _DOC_TYPES[doc_type].get(lang, doc_type)
            doc_prompt = (
                f"다음 정보를 바탕으로 **{type_label}** 초안을 작성해 주세요. "
                f"각 섹션은 ##으로 구분해 주세요."
                if lang == "ko"
                else f"Based on the following, draft a **{type_label}**. "
                     f"Separate each section with ##."
            )

        system_instruction = (
            "당신은 한국법 전문 법률 문서 작성 AI입니다. "
            "실제 법률문서 양식에 맞춰 정확하고 구체적인 초안을 작성합니다. "
            "추측이나 허위 법조문을 절대 사용하지 마세요. "
            "문서 내용만 출력하고, 부가 설명은 하지 마세요."
            if lang == "ko"
            else "You are a Korean law legal document drafting AI. "
                 "Draft accurate, specific documents following proper Korean legal format. "
                 "Never fabricate statutes or case numbers. "
                 "Output only the document content, no additional commentary."
        )

        full_prompt = f"{doc_prompt}\n\n---\n\n{context}"
        if extra:
            additional = "추가 지시" if lang == "ko" else "Additional instructions"
            full_prompt += f"\n\n[{additional}]\n{extra}"

        # 별표서식 자동 참조 — 관련 서식이 있으면 프롬프트에 포함
        drf = _RUNTIME.get("drf")
        if drf:
            try:
                type_label = _DOC_TYPES[doc_type].get("ko", doc_type)
                forms_result = await drf.search_forms_async(
                    query=type_label, search=1, display=5,
                )
                if forms_result:
                    raw_list = forms_result.get("LicBylInfoList", {}).get("licbyl", [])
                    if isinstance(raw_list, dict):
                        raw_list = [raw_list]
                    if raw_list:
                        forms_ref = "\n\n[참고 별표서식 (법령정보센터)]\n"
                        for f in raw_list[:5]:
                            fname = f.get("별표명", "")
                            flaw = f.get("관련법령명", "")
                            flink = f.get("별표서식파일링크", "")
                            if fname:
                                forms_ref += f"- {fname} ({flaw})"
                                if flink:
                                    forms_ref += f" [링크: {flink}]"
                                forms_ref += "\n"
                        full_prompt += forms_ref
                        logger.info(f"[DOC] 별표서식 {len(raw_list)}건 참조 추가")
            except Exception as e:
                logger.warning(f"[DOC] 별표서식 조회 실패 (무시): {e}")

        # Call Gemini
        model = get_model()
        response = await model.generate_content_async(
            contents=full_prompt,
            config=genai_types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.3,
                max_output_tokens=4096,
            ),
        )

        generated = response.text.strip() if response.text else ""
        if not generated:
            raise HTTPException(status_code=500, detail="문서 생성에 실패했습니다.")

        # Parse sections from ## headings
        sections = []
        current_heading = ""
        current_body_lines = []
        for line in generated.split("\n"):
            if line.strip().startswith("##"):
                if current_heading or current_body_lines:
                    sections.append({
                        "heading": current_heading,
                        "body": "\n".join(current_body_lines).strip(),
                    })
                current_heading = line.strip().lstrip("#").strip()
                current_body_lines = []
            else:
                current_body_lines.append(line)
        if current_heading or current_body_lines:
            sections.append({
                "heading": current_heading,
                "body": "\n".join(current_body_lines).strip(),
            })

        title = _DOC_TYPES[doc_type].get(lang, doc_type)

        logger.info(f"[DOC] Generated: {doc_type} ({lang}), {len(sections)} sections")

        return {
            "doc_type": doc_type,
            "title": title,
            "content": generated,
            "sections": sections,
            "lang": lang,
            "download_ready": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[DOC] Generation failed: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="문서 생성 중 오류가 발생했습니다.")


@router.get("/document-types")
async def list_document_types(request: Request):
    """Return available document types for the document generator."""
    return {
        "types": [
            {"key": k, "label_ko": v["ko"], "label_en": v["en"]}
            for k, v in _DOC_TYPES.items()
        ]
    }


# =============================================================
# 별표서식 검색 (DRF target=licbyl)
# =============================================================

@router.get("/api/forms/search")
@limiter.limit("30/minute")
async def search_legal_forms(
    request: Request,
    query: str = "*",
    search: int = 1,
    display: int = 20,
    knd: str = "",
    page: int = 1,
    source: str = "law",
):
    """
    별표서식 목록 검색 (DRF licbyl / admbyl API)

    Query params:
        query: 검색어 (default="*")
        search: 검색범위 (1:별표서식명, 2:해당법령검색, 3:별표본문검색)
        display: 결과 개수 (default=20, max=100)
        knd: 별표종류 (1:별표, 2:서식, 3:별지, 4:별도, 5:부록, "":전체)
        page: 결과 페이지 (default=1)
        source: "law" (법령 별표서식, licbyl) 또는 "admin" (행정규칙 별표서식, admbyl)

    Returns:
        정규화된 items 배열 + 메타데이터
    """
    try:
        drf = _RUNTIME.get("drf")
        if not drf:
            raise HTTPException(status_code=503, detail="DRF 서비스를 사용할 수 없습니다.")

        # Sanitize inputs
        query = query.strip()[:200]
        display = min(max(1, display), 100)
        page = max(1, page)
        if knd and knd not in ("1", "2", "3", "4", "5"):
            knd = ""
        source = source.strip().lower()
        if source not in ("law", "admin"):
            source = "law"

        if source == "admin":
            result = await drf.search_admin_forms_async(
                query=query, search=search, display=display, knd=knd, page=page,
            )
        else:
            result = await drf.search_forms_async(
                query=query, search=search, display=display, knd=knd, page=page,
            )

        if not result:
            return {"items": [], "totalCnt": 0, "page": page, "query": query, "source": source}

        # Normalize response — DRF returns nested structure
        # licbyl → LicBylInfoList, admbyl → same or similar structure
        list_key = "LicBylInfoList" if source == "law" else "AdmBylInfoList"
        item_key = "licbyl" if source == "law" else "admbyl"

        container = result.get(list_key, {})
        if not container:
            # Fallback: try other key patterns
            for k in result:
                if "List" in k or "Info" in k:
                    container = result[k]
                    break

        raw_list = container.get(item_key, []) if isinstance(container, dict) else []
        if isinstance(raw_list, dict):
            raw_list = [raw_list]

        items = []
        for entry in raw_list:
            items.append({
                "id": entry.get("별표일련번호", ""),
                "name": entry.get("별표명", ""),
                "law_name": entry.get("관련법령명", entry.get("관련행정규칙명", "")),
                "law_id": entry.get("관련법령ID", entry.get("관련행정규칙ID", "")),
                "number": entry.get("별표번호", ""),
                "kind": entry.get("별표종류", ""),
                "ministry": entry.get("소관부처명", ""),
                "promulgation_date": entry.get("공포일자", ""),
                "revision_type": entry.get("제개정구분명", ""),
                "law_type": entry.get("법령종류", entry.get("행정규칙종류", "")),
                "file_link": entry.get("별표서식파일링크", ""),
                "pdf_link": entry.get("별표서식PDF파일링크", ""),
                "detail_link": entry.get("별표법령상세링크", entry.get("별표행정규칙상세링크", "")),
            })

        total = container.get("totalCnt", len(items)) if isinstance(container, dict) else len(items)

        return {
            "items": items,
            "totalCnt": int(total) if total else len(items),
            "page": page,
            "query": query,
            "source": source,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Forms] Search failed: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="별표서식 검색 중 오류가 발생했습니다.")
