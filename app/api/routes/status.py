from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import logging
import threading
import time
import re

from app.models.schemas import StatusResponse, SessionStatus
from app.utils.session_manager import session_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/status", tags=["Status"])

def _parse_json_object(text: str):
    import json
    if not text:
        return None
    json_start = text.find('{')
    json_end = text.rfind('}') + 1
    if json_start == -1 or json_end <= json_start:
        return None
    candidate = text[json_start:json_end]
    try:
        return json.loads(candidate)
    except Exception:
        return None

def _infer_known_fields(text: str) -> dict:
    combined = (text or "")
    lower = combined.lower()
    known: dict = {}

    mgr = re.search(r"(reporting manager|manager)\s*(is|:)\s*(mr\.?|ms\.?|mrs\.?)?\s*([a-z][a-z\s\.]{2,60})", lower)
    if mgr:
        known["reporting_manager_name"] = mgr.group(4).strip().strip(".")

    comp = re.search(r"(company|worked at|work at)\s*(is|:|,)?\s*([a-z0-9][a-z0-9\s&\.-]{2,80})", lower)
    if comp:
        known["company_name"] = comp.group(3).strip().strip(".")

    month = r"(january|february|march|april|may|june|july|august|september|october|november|december)"
    last_salary = re.search(r"(last\s+(salary|pay)\s+(received|got)\s*(on)?\s*[:,-]?\s*)(" + month + r"(?:\s+\d{4})?)", lower)
    if last_salary:
        known["last_salary_received_date"] = last_salary.group(4).strip()

    date1 = re.search(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", lower)
    if date1:
        known["incident_date"] = date1.group(0)

    date2 = re.search(r"\b" + month + r"\s+\d{1,2}(?:st|nd|rd|th)?(?:,\s*\d{4})?\b", lower)
    if date2:
        known.setdefault("incident_date", date2.group(0))

    loc = re.search(r"(incident|happened|occurred)\s*(in|at)\s+([a-z][a-z\s,.-]{2,80})", lower)
    if loc:
        known["incident_location"] = loc.group(3).strip().strip(".")
    else:
        loc2 = re.search(r"\b(in|at)\s+([a-z][a-z\s]{2,40})\b", lower)
        if loc2 and "incident_location" not in known:
            known["incident_location"] = loc2.group(2).strip()

    amt = re.search(r"((rs\.?|₹)\s*[\d,]+)\s*(remains|pending|due|unpaid)?", lower)
    if amt:
        known["unpaid_amount"] = amt.group(1).strip()

    addr = re.search(r"(address|located at|workplace)\s*(is|:)\s*([a-z0-9][a-z0-9\s,/-]{5,120})", lower)
    if addr:
        known["employee_address"] = addr.group(3).strip()

    emp_id = re.search(r"(employee id|emp id)\s*(is|:)\s*([a-z0-9-]{3,})", lower)
    if emp_id:
        known["employee_id"] = emp_id.group(3).strip()

    return {k: v for k, v in known.items() if v}

def _filter_questions(result: dict, known_fields: dict) -> dict:
    if not isinstance(result, dict):
        return {"missing_fields": [], "questions": []}

    missing_fields = result.get("missing_fields", [])
    questions = result.get("questions", [])

    if not isinstance(missing_fields, list):
        missing_fields = []
    if not isinstance(questions, list):
        questions = []

    known_keys = set([str(k).strip() for k in known_fields.keys()])

    filtered_missing = []
    for f in missing_fields:
        key = str(f).strip()
        if key and key not in known_keys:
            filtered_missing.append(key)

    filtered_questions = []
    for q in questions:
        if not isinstance(q, dict):
            continue
        field = str(q.get("field", "")).strip()
        if field and field in known_keys:
            continue
        filtered_questions.append(q)

    return {"missing_fields": filtered_missing, "questions": filtered_questions}

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
        error=session.get('error'),
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

@router.post("/{session_id}/transcription")
async def update_transcription(session_id: str, payload: dict):
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    transcription = str(payload.get("transcription", "")).strip()
    if not transcription:
        raise HTTPException(status_code=400, detail="Transcription is empty")

    session_manager.update_transcription(session_id, transcription)
    return {"session_id": session_id, "message": "Transcription updated"}

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

@router.post("/{session_id}/notes")
async def add_notes(session_id: str, payload: dict):
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    notes = str(payload.get("notes", "")).strip()
    if not notes:
        raise HTTPException(status_code=400, detail="Notes are empty")

    session_manager.add_user_notes(session_id, notes)
    return {"session_id": session_id, "message": "Notes saved"}

@router.post("/{session_id}/questions")
async def generate_missing_info_questions(session_id: str):
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    metadata = session.get("metadata") or {}
    existing_status = metadata.get("questions_status", "idle")

    if existing_status == "running":
        return {"status": "running"}

    metadata["questions_status"] = "running"
    metadata["questions_error"] = None
    metadata["questions_result"] = None
    metadata["questions_updated_at"] = time.time()
    session_manager.update_session(session_id, metadata=metadata)

    def run():
        try:
            current = session_manager.get_session(session_id) or {}
            transcription = current.get("transcription") or ""
            evidence_results = current.get("evidence_results") or []
            evidence_text = "\n\n".join([str(e.get("text", "")) for e in evidence_results if e.get("text")])
            current_metadata = current.get("metadata") or {}
            user_notes = current_metadata.get("user_notes", "")
            structured = current.get("structured_complaint") or ""
            known_fields = _infer_known_fields(f"{transcription}\n{user_notes}\n{evidence_text}\n{structured}")
            try:
                import json
                structured_obj = json.loads(structured) if structured else None
                if isinstance(structured_obj, dict):
                    if structured_obj.get("incident_date"):
                        known_fields.setdefault("incident_date", structured_obj.get("incident_date"))
                    if structured_obj.get("incident_location"):
                        known_fields.setdefault("incident_location", structured_obj.get("incident_location"))
                    if structured_obj.get("respondent_name"):
                        known_fields.setdefault("respondent_name", structured_obj.get("respondent_name"))
                    if structured_obj.get("complainant_name"):
                        known_fields.setdefault("complainant_name", structured_obj.get("complainant_name"))
            except Exception:
                pass

            required_fields = [
                "incident_date",
                "incident_location",
                "company_name",
                "reporting_manager_name",
                "employee_address",
                "employee_id",
            ]
            missing_fields = [f for f in required_fields if not known_fields.get(f)]
            if not missing_fields:
                parsed = {"missing_fields": [], "questions": []}
                latest = session_manager.get_session(session_id) or {}
                latest_metadata = latest.get("metadata") or {}
                latest_metadata["questions_status"] = "done"
                latest_metadata["questions_result"] = parsed
                latest_metadata["questions_error"] = None
                latest_metadata["questions_updated_at"] = time.time()
                session_manager.update_session(session_id, metadata=latest_metadata)
                return

            from app.services.llm_service import llm_service

            prompt = f"""
You are helping a user complete a legal aid case intake. Ask ONLY for information that is NOT already present.
If the user already mentions something in transcription, evidence, or notes, do NOT ask for it again.

You MUST ask questions ONLY for the fields in MISSING FIELDS LIST. Do NOT ask about any other field.

KNOWN INFO (already mentioned; do NOT ask again for these):
{known_fields}

MISSING FIELDS LIST (ask for these only):
{missing_fields}

TRANSCRIPTION:
{transcription}

EVIDENCE (OCR or manual):
{evidence_text}

USER NOTES:
{user_notes}

Return ONLY valid JSON:
{{
  "missing_fields": ["string", "..."],
  "questions": [
    {{"field": "string", "question": "string", "example_answer": "string"}}
  ]
}}
"""

            response = llm_service.generate_with_retry(
                prompt=prompt,
                system_prompt="Return ONLY valid JSON. No markdown, no explanation.",
                temperature=0.2
            )
            parsed = _parse_json_object(response.get("response", ""))
            if not isinstance(parsed, dict):
                parsed = {"missing_fields": [], "questions": []}
            parsed = _filter_questions(parsed, known_fields)
            parsed["missing_fields"] = list(missing_fields)
            if isinstance(parsed.get("questions"), list):
                parsed["questions"] = [
                    q for q in parsed["questions"]
                    if isinstance(q, dict) and q.get("field") in set(missing_fields)
                ]

            latest = session_manager.get_session(session_id) or {}
            latest_metadata = latest.get("metadata") or {}
            latest_metadata["questions_status"] = "done"
            latest_metadata["questions_result"] = parsed
            latest_metadata["questions_error"] = None
            latest_metadata["questions_updated_at"] = time.time()
            session_manager.update_session(session_id, metadata=latest_metadata)
        except Exception as e:
            latest = session_manager.get_session(session_id) or {}
            latest_metadata = latest.get("metadata") or {}
            latest_metadata["questions_status"] = "error"
            latest_metadata["questions_result"] = None
            latest_metadata["questions_error"] = str(e)
            latest_metadata["questions_updated_at"] = time.time()
            session_manager.update_session(session_id, metadata=latest_metadata)

    threading.Thread(target=run, daemon=True).start()

    return {"status": "running"}

@router.get("/{session_id}/questions")
async def get_missing_info_questions(session_id: str):
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    metadata = session.get("metadata") or {}
    status = metadata.get("questions_status", "idle")
    if status == "done":
        return {"status": "done", "result": metadata.get("questions_result") or {"missing_fields": [], "questions": []}}
    if status == "error":
        return {"status": "error", "error": metadata.get("questions_error") or "Unknown error"}
    return {"status": "running" if status == "running" else "idle"}

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
