from fastapi import APIRouter, HTTPException
import logging
import json
import threading
import time
from datetime import datetime

from app.models.schemas import GenerateResponse, GenerateRequest
from app.models.database import SessionStatus
from app.utils.session_manager import session_manager
from app.agents.crew import legal_aid_crew
from app.services.document_service import document_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/generate", tags=["Generate"])

def _format_notice_preview(legal_notice_data: dict) -> str:
    header = legal_notice_data.get("header", "LEGAL NOTICE")
    addressee = legal_notice_data.get("addressee", "")
    subject = legal_notice_data.get("subject", "")
    body = legal_notice_data.get("body", "")
    legal_grounds = legal_notice_data.get("legal_grounds", [])
    relief = legal_notice_data.get("relief_sought_section", "")
    ultimatum = legal_notice_data.get("notice_ultimatum", "")
    signature = legal_notice_data.get("signature_block", "")

    parts = [
        str(header).strip(),
        "",
        str(addressee).strip(),
        "",
        str(subject).strip(),
        "",
        str(body).strip(),
        "",
    ]

    if isinstance(legal_grounds, list) and legal_grounds:
        parts.append("LEGAL GROUNDS:")
        parts.extend([f"- {g}" for g in legal_grounds])
        parts.append("")

    if relief:
        parts.append("RELIEF SOUGHT:")
        parts.append(str(relief).strip())
        parts.append("")

    if ultimatum:
        parts.append("NOTICE:")
        parts.append(str(ultimatum).strip())
        parts.append("")

    if signature:
        parts.append(str(signature).strip())

    return "\n".join([p for p in parts if p is not None]).strip()

@router.post("", response_model=GenerateResponse)
async def generate_documents(request: GenerateRequest):
    session_id = request.session_id
    
    try:
        session = session_manager.get_session(session_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found"
            )
        
        if not session.get('transcription'):
            raise HTTPException(
                status_code=400,
                detail="No transcription available. Please upload voice first."
            )
        
        if session['status'] == SessionStatus.COMPLETE:
            return GenerateResponse(
                session_id=session_id,
                status=SessionStatus.COMPLETE,
                message="Documents already generated"
            )
        
        session_manager.update_session(session_id, status=SessionStatus.GENERATING_DOCUMENTS)
        
        def process_in_background():
            try:
                logger.info(f"Starting document generation for session {session_id}")
                
                transcription = session['transcription']
                language = session.get('language', 'hi')
                ocr_results = session.get('evidence_results', [])
                metadata = session.get('metadata') or {}
                user_notes = metadata.get("user_notes", "")
                if user_notes:
                    transcription = f"{transcription}\n\nUSER NOTES (additional facts/corrections):\n{user_notes}"
                
                def progress_callback(agent: str, progress: int, message: str):
                    logger.info(f"[{agent}] {progress}%: {message}")
                    if agent == "voice_intake":
                        session_manager.update_session(session_id, status=SessionStatus.AGENTS_RUNNING)
                    elif agent == "evidence":
                        session_manager.update_session(session_id, status=SessionStatus.PROCESSING_EVIDENCE)
                
                result = legal_aid_crew.process_complaint(
                    transcription=transcription,
                    language=language,
                    ocr_results=ocr_results,
                    progress_callback=progress_callback
                )
                
                if result.get('success'):
                    complaint_data = result.get('complaint_data', {})
                    structured_complaint = json.dumps(complaint_data, indent=2)
                    
                    session_manager.set_structured_complaint(session_id, complaint_data)
                    
                    evidence_analysis = result.get('evidence_analysis', {})
                    session_manager.set_evidence_analysis(session_id, evidence_analysis)
                    
                    legal_notice_data = result.get('legal_notice', {})
                    case_summary_data = result.get('case_summary', {})
                    
                    notice_data = {
                        'complainant_name': complaint_data.get('complainant_name', 'Unknown'),
                        'complainant_address': complaint_data.get('complainant_address', ''),
                        'complainant_occupation': complaint_data.get('complainant_occupation', 'Worker'),
                        'respondent': {
                            'name': complaint_data.get('respondent_name', 'Unknown'),
                            'address': complaint_data.get('respondent_address', '')
                        },
                        'incident_date': complaint_data.get('incident_date', ''),
                        'incident_location': complaint_data.get('incident_location', ''),
                        'factual_matrix': complaint_data.get('incident_description') or complaint_data.get('_raw_transcription', '') or transcription,
                        'legal_grounds': legal_notice_data.get('legal_grounds', complaint_data.get('applicable_laws', [])),
                        'relief_sought': complaint_data.get('relief_sought', [])
                    }
                    
                    if isinstance(legal_notice_data, dict) and legal_notice_data:
                        docx_content = document_service.generate_legal_notice(legal_notice_data, "docx")
                    else:
                        docx_content = document_service.generate_legal_notice(notice_data, "docx")
                    summary_input = dict(notice_data)
                    if isinstance(case_summary_data, dict):
                        if case_summary_data.get("case_id"):
                            summary_input["case_id"] = case_summary_data.get("case_id")
                        if case_summary_data.get("summary_type"):
                            summary_input["summary_type"] = case_summary_data.get("summary_type")
                        if case_summary_data.get("legal_framework"):
                            summary_input["applicable_laws"] = case_summary_data.get("legal_framework")
                    txt_content = document_service.generate_case_summary(summary_input, "txt")
                    
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    docx_filename = f"legal_notice_{session_id[:8]}_{timestamp}.docx"
                    txt_filename = f"case_summary_{session_id[:8]}_{timestamp}.txt"
                    
                    docx_path = document_service.save_document(docx_content, docx_filename)
                    txt_bytes = txt_content if isinstance(txt_content, (bytes, bytearray)) else str(txt_content).encode('utf-8')
                    txt_path = document_service.save_document(txt_bytes, txt_filename)
                    
                    logger.info(f"Documents saved: {docx_path}, {txt_path}")

                    try:
                        latest = session_manager.get_session(session_id) or {}
                        latest_metadata = latest.get("metadata") or {}
                        generated_files = latest_metadata.get("generated_files") or {}
                        generated_files.update(
                            {
                                "legal_notice_docx": docx_filename,
                                "case_summary_txt": txt_filename,
                                "updated_at": time.time(),
                            }
                        )
                        latest_metadata["generated_files"] = generated_files
                        session_manager.update_session(session_id, metadata=latest_metadata)
                    except Exception as e:
                        logger.warning(f"Failed to store generated file references for {session_id}: {e}")
                    
                    draft_notice = _format_notice_preview(legal_notice_data) if isinstance(legal_notice_data, dict) else ""
                    if not draft_notice:
                        draft_notice = f"Legal Notice generated: {docx_filename}"

                    case_summary = txt_content.decode('utf-8') if isinstance(txt_content, (bytes, bytearray)) else str(txt_content)
                    
                    session_manager.set_documents(session_id, draft_notice, case_summary)
                    
                    logger.info(f"Document generation complete for session {session_id}")
                    
                else:
                    error = result.get('error', 'Unknown error')
                    session_manager.set_error(session_id, error)
                    logger.error(f"Document generation failed: {error}")
                    
            except Exception as e:
                logger.error(f"Background processing error: {e}", exc_info=True)
                session_manager.set_error(session_id, str(e))
        
        thread = threading.Thread(target=process_in_background, daemon=True)
        thread.start()
        
        return GenerateResponse(
            session_id=session_id,
            status=SessionStatus.GENERATING_DOCUMENTS,
            message="Document generation started"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generate error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start document generation: {str(e)}"
        )

@router.get("/{session_id}/download/{format}")
async def download_document(session_id: str, format: str):
    session = session_manager.get_session(session_id)
    
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found"
        )
    
    if session['status'] != SessionStatus.COMPLETE:
        raise HTTPException(
            status_code=400,
            detail=f"Documents not ready. Status: {session['status'].value}"
        )
    
    if format == "docx":
        from pathlib import Path
        from fastapi.responses import Response

        output_dir = Path(document_service.output_dir)
        metadata = session.get("metadata") or {}
        generated_files = metadata.get("generated_files") or {}
        docx_name = generated_files.get("legal_notice_docx")

        docx_path: Path | None = None
        if isinstance(docx_name, str) and docx_name.strip():
            candidate = (output_dir / docx_name).resolve()
            if str(candidate).startswith(str(output_dir.resolve())) and candidate.exists():
                docx_path = candidate

        if docx_path is None:
            prefix = f"legal_notice_{session_id[:8]}_"
            candidates = sorted(
                output_dir.glob(f"{prefix}*.docx"),
                key=lambda p: p.stat().st_mtime if p.exists() else 0,
                reverse=True
            )
            if candidates:
                docx_path = candidates[0]

        if docx_path is not None and docx_path.exists():
            content = docx_path.read_bytes()
            return Response(
                content=content,
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                headers={
                    "Content-Disposition": f"attachment; filename={docx_path.name}"
                }
            )

        if not session.get("draft_notice"):
            raise HTTPException(status_code=404, detail="DOCX not available")

        docx_content = document_service.generate_legal_notice(
            {"header": "LEGAL NOTICE", "body": str(session.get("draft_notice") or "")},
            "docx"
        )
        return Response(
            content=docx_content,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename=legal_notice_{session_id[:8]}.docx"},
        )
    
    elif format == "txt":
        if not session.get('case_summary'):
            raise HTTPException(status_code=404, detail="Summary not available")
        
        content = session['case_summary']
        if isinstance(content, str):
            content = content.encode('utf-8')
        
        from fastapi.responses import Response
        return Response(
            content=content,
            media_type="text/plain",
            headers={
                "Content-Disposition": f"attachment; filename=case_summary_{session_id[:8]}.txt"
            }
        )
    
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format: {format}. Use 'docx' or 'txt'"
        )
