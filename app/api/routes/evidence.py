from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import List, Optional
import logging
import time

from app.models.schemas import EvidenceResponse
from app.utils.session_manager import session_manager
from app.services.ocr_service import ocr_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/evidence", tags=["Evidence"])

@router.post("", response_model=EvidenceResponse)
async def upload_evidence(
    files: List[UploadFile] = File(..., description="Image files (JPG, PNG, WEBP)"),
    session_id: str = Form(..., description="Session ID")
):
    start_time = time.time()
    
    try:
        logger.info(f"Received {len(files)} evidence files for session {session_id}")
        
        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found"
            )
        
        if not ocr_service.is_ready():
            engine = ocr_service.get_engine_info()
            raise HTTPException(
                status_code=503,
                detail=f"OCR engine not available. Details: {engine}"
            )

        extracted_texts = []
        
        for i, file in enumerate(files):
            try:
                file_size_mb = file.size / (1024 * 1024) if file.size else 0
                
                if file_size_mb > 10:
                    logger.warning(f"File {file.filename} too large, skipping")
                    continue
                
                image_data = await file.read()
                
                language_hint = session.get('language', 'en')
                if not language_hint or language_hint == "auto":
                    language_hint = "en"
                
                logger.info(f"Processing evidence {i+1}/{len(files)}: {file.filename}")
                
                ocr_result = ocr_service.extract_text_from_image(
                    image_data=image_data,
                    language_hint=language_hint
                )
                
                evidence_item = {
                    "filename": file.filename,
                    "text": ocr_result.get('text', ''),
                    "confidence": ocr_result.get('confidence', 0.0),
                    "detected_language": ocr_result.get('detected_language', language_hint),
                    "word_count": ocr_result.get('word_count', 0),
                    "line_count": ocr_result.get('line_count', 0),
                    "bboxes": ocr_result.get('bboxes', [])
                }
                
                extracted_texts.append(evidence_item)
                session_manager.add_evidence(session_id, evidence_item)
                
                logger.info(f"Evidence {i+1} extracted: {len(ocr_result.get('text', ''))} chars")
                
            except Exception as e:
                logger.error(f"Failed to process evidence {file.filename}: {e}")
                extracted_texts.append({
                    "filename": file.filename,
                    "error": str(e),
                    "text": "",
                    "confidence": 0.0
                })
        
        processing_time = time.time() - start_time
        
        if not extracted_texts:
            raise HTTPException(
                status_code=400,
                detail="No evidence could be processed. Please upload clear image files."
            )
        
        successful_extractions = sum(1 for e in extracted_texts if e.get('text'))
        if successful_extractions == 0:
            engine = ocr_service.get_engine_info()
            hint = ""
            if engine.get("primary_engine") == "tesseract" and not engine.get("tesseract_available"):
                hint = "Tesseract OCR is not installed or not on PATH. Install Tesseract and restart the backend."
            raise HTTPException(
                status_code=400,
                detail=f"No text could be extracted from the uploaded images. {hint} OCR engine info: {engine}"
            )
        logger.info(f"Evidence processing complete: {successful_extractions}/{len(files)} successful in {processing_time:.1f}s")
        
        return EvidenceResponse(
            session_id=session_id,
            extracted_texts=extracted_texts,
            processing_time=processing_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Evidence upload error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Evidence processing failed: {str(e)}"
        )

@router.get("/supported-formats")
async def get_supported_formats():
    return {
        "formats": ["jpg", "jpeg", "png", "webp", "bmp"],
        "max_files": 10,
        "max_file_size_mb": 10,
        "recommended": ["jpg", "png"]
    }

@router.post("/manual", response_model=EvidenceResponse)
async def add_manual_evidence(
    session_id: str = Form(..., description="Session ID"),
    text: str = Form(..., description="Manually provided evidence text"),
    filename: str = Form("manual.txt", description="Display filename")
):
    start_time = time.time()

    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    content = (text or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Manual evidence text is empty")

    evidence_item = {
        "filename": filename,
        "text": content,
        "confidence": 1.0,
        "detected_language": session.get("language") or "unknown",
        "word_count": len(content.split()),
        "line_count": len(content.splitlines()),
        "bboxes": []
    }

    session_manager.add_evidence(session_id, evidence_item)
    processing_time = time.time() - start_time

    return EvidenceResponse(
        session_id=session_id,
        extracted_texts=[evidence_item],
        processing_time=processing_time
    )
