from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import logging

from app.models.schemas import StatusResponse, SessionStatus
from app.utils.session_manager import session_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/status", tags=["Status"])

@router.get("/{session_id}", response_model=StatusResponse)
async def get_session_status(session_id: str):
    session = session_manager.get_session(session_id)
    
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found"
        )
    
    return StatusResponse(
        session_id=session_id,
        status=session['status'],
        progress=session_manager.get_progress(session_id),
        current_agent=session_manager.get_current_agent(session_id),
        output_preview=session_manager.get_output_preview(session_id),
        created_at=session['created_at'],
        updated_at=session['updated_at']
    )

@router.get("/{session_id}/transcription")
async def get_transcription(session_id: str):
    session = session_manager.get_session(session_id)
    
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found"
        )
    
    if not session.get('transcription'):
        raise HTTPException(
            status_code=404,
            detail="Transcription not yet available"
        )
    
    return {
        "session_id": session_id,
        "transcription": session['transcription'],
        "language": session.get('language'),
        "word_count": len(session['transcription'].split())
    }

@router.get("/{session_id}/evidence")
async def get_evidence(session_id: str):
    session = session_manager.get_session(session_id)
    
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found"
        )
    
    evidence_results = session.get('evidence_results', [])
    
    return {
        "session_id": session_id,
        "evidence_count": len(evidence_results),
        "evidence": evidence_results
    }

@router.get("/{session_id}/documents")
async def get_documents(session_id: str):
    session = session_manager.get_session(session_id)
    
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found"
        )
    
    if session['status'] != SessionStatus.COMPLETE:
        raise HTTPException(
            status_code=400,
            detail=f"Documents not ready. Current status: {session['status'].value}"
        )
    
    return {
        "session_id": session_id,
        "draft_notice": session.get('draft_notice'),
        "case_summary": session.get('case_summary'),
        "status": session['status'].value
    }

@router.delete("/{session_id}")
async def delete_session(session_id: str):
    session = session_manager.get_session(session_id)
    
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found"
        )
    
    session_manager.delete_session(session_id)
    
    return {
        "message": f"Session {session_id} deleted",
        "session_id": session_id
    }

@router.get("")
async def list_sessions(limit: int = Query(50, ge=1, le=100)):
    sessions = session_manager.list_sessions(limit=limit)
    
    return {
        "count": len(sessions),
        "sessions": [
            {
                "id": s['id'],
                "status": s['status'].value,
                "language": s.get('language'),
                "created_at": s['created_at'].isoformat() if s['created_at'] else None,
                "has_transcription": bool(s.get('transcription')),
                "evidence_count": len(s.get('evidence_results', []))
            }
            for s in sessions
        ]
    }
