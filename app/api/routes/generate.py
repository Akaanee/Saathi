from fastapi import APIRouter, HTTPException
import logging
import json
import threading
from datetime import datetime

from app.models.schemas import GenerateResponse, GenerateRequest
from app.models.database import SessionStatus
from app.utils.session_manager import session_manager
from app.agents.crew import legal_aid_crew
from app.services.document_service import document_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/generate", tags=["Generate"])

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
                        'factual_matrix': complaint_data.get('incident_description', ''),
                        'legal_grounds': legal_notice_data.get('legal_grounds', []),
                        'relief_sought': legal_notice_data.get('relief_sought', [])
                    }
                    
                    docx_content = document_service.generate_legal_notice(notice_data, "docx")
                    txt_content = document_service.generate_case_summary(notice_data, "txt")
                    
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    docx_filename = f"legal_notice_{session_id[:8]}_{timestamp}.docx"
                    txt_filename = f"case_summary_{session_id[:8]}_{timestamp}.txt"
                    
                    docx_path = document_service.save_document(docx_content, docx_filename)
                    txt_path = document_service.save_document(txt_content.encode('utf-8'), txt_filename)
                    
                    logger.info(f"Documents saved: {docx_path}, {txt_path}")
                    
                    draft_notice = f"Legal Notice generated and saved to: {docx_filename}"
                    case_summary = txt_content.decode('utf-8') if isinstance(txt_content, bytes) else txt_content
                    
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
        if not session.get('draft_notice'):
            raise HTTPException(status_code=404, detail="DOCX not available")
        
        notice_data = {
            'complainant_name': 'Generated',
            'complainant_address': '',
            'complainant_occupation': 'Worker',
            'respondent': {'name': 'Generated', 'address': ''},
            'incident_date': '',
            'incident_location': '',
            'factual_matrix': 'See generated notice',
            'legal_grounds': [],
            'relief_sought': []
        }
        
        docx_content = document_service.generate_legal_notice(notice_data, "docx")
        
        from fastapi.responses import Response
        return Response(
            content=docx_content,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f"attachment; filename=legal_notice_{session_id[:8]}.docx"
            }
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
