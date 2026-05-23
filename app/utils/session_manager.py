import uuid
import threading
import time
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
from app.models.database import Session, ProcessingLog, SessionStatus, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session as DBSession
from pathlib import Path

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self, db_path: str = "saathi.db"):
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._locks: Dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()
        self._db_engine = None
        self._db_session = None
        self._auto_save_interval = 30
        self._last_save_time = time.time()
        self._db_path = db_path
        self._initialize_db()

    def _initialize_db(self):
        try:
            db_file = Path(self._db_path)
            db_file.parent.mkdir(parents=True, exist_ok=True)
            
            db_url = f"sqlite:///{self._db_path}"
            self._db_engine = create_engine(db_url, echo=False)
            Base.metadata.create_all(self._db_engine)
            
            SessionLocal = sessionmaker(bind=self._db_engine)
            self._db_session = SessionLocal()
            
            logger.info(f"Database initialized at {self._db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            self._db_session = None

    def create_session(self, language: Optional[str] = None) -> str:
        session_id = str(uuid.uuid4())
        
        with self._global_lock:
            self._sessions[session_id] = {
                'id': session_id,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
                'status': SessionStatus.PENDING,
                'language': language,
                'transcription': None,
                'structured_complaint': None,
                'evidence_texts': None,
                'evidence_results': [],
                'draft_notice': None,
                'case_summary': None,
                'processing_logs': [],
                'error': None,
                'metadata': {}
            }
            self._locks[session_id] = threading.Lock()
        
        self._save_to_db(session_id)
        
        logger.info(f"Created session: {session_id}")
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._global_lock:
            return self._sessions.get(session_id)

    def update_session(self, session_id: str, **kwargs):
        with self._locks.get(session_id, self._global_lock):
            if session_id in self._sessions:
                for key, value in kwargs.items():
                    if key not in ['id', 'created_at']:
                        self._sessions[session_id][key] = value
                self._sessions[session_id]['updated_at'] = datetime.utcnow()
                
                if time.time() - self._last_save_time > self._auto_save_interval:
                    self._save_to_db(session_id)
                    self._last_save_time = time.time()

    def add_transcription(self, session_id: str, transcription: str, language: str):
        self.update_session(
            session_id,
            transcription=transcription,
            language=language,
            status=SessionStatus.TRANSCRIBING
        )
        self._add_log(session_id, "STT", "completed", f"Transcribed in {language}")

    def update_transcription(self, session_id: str, transcription: str):
        self.update_session(session_id, transcription=transcription)
        self._add_log(session_id, "STT", "updated", "Transcription edited by user")

    def add_evidence(self, session_id: str, evidence_result: Dict[str, Any]):
        with self._locks.get(session_id, self._global_lock):
            if session_id in self._sessions:
                self._sessions[session_id]['evidence_results'].append(evidence_result)
                self._sessions[session_id]['updated_at'] = datetime.utcnow()

    def add_user_notes(self, session_id: str, notes: str):
        notes_text = (notes or "").strip()
        if not notes_text:
            return

        with self._locks.get(session_id, self._global_lock):
            if session_id not in self._sessions:
                return

            metadata = self._sessions[session_id].get('metadata') or {}
            existing = metadata.get("user_notes", "")
            if existing:
                metadata["user_notes"] = f"{existing}\n\n{notes_text}"
            else:
                metadata["user_notes"] = notes_text
            self._sessions[session_id]['metadata'] = metadata
            self._sessions[session_id]['updated_at'] = datetime.utcnow()

    def set_structured_complaint(self, session_id: str, complaint_data: Dict[str, Any]):
        self.update_session(
            session_id,
            structured_complaint=json.dumps(complaint_data),
            status=SessionStatus.AGENTS_RUNNING
        )
        self._add_log(session_id, "Voice Intake Agent", "completed", "Complaint structured")

    def set_evidence_analysis(self, session_id: str, analysis_data: Dict[str, Any]):
        self.update_session(
            session_id,
            evidence_texts=json.dumps(analysis_data),
            status=SessionStatus.AGENTS_RUNNING
        )
        self._add_log(session_id, "Evidence Processor Agent", "completed", "Evidence analyzed")

    def set_documents(self, session_id: str, draft_notice: str, case_summary: str):
        self.update_session(
            session_id,
            draft_notice=draft_notice,
            case_summary=case_summary,
            status=SessionStatus.COMPLETE
        )
        self._add_log(session_id, "Document Generator", "completed", "Documents generated")

    def set_error(self, session_id: str, error: str):
        self.update_session(
            session_id,
            error=error,
            status=SessionStatus.ERROR
        )
        self._add_log(session_id, "System", "error", error)

    def get_status(self, session_id: str) -> str:
        session = self.get_session(session_id)
        return session['status'].value if session else None

    def get_progress(self, session_id: str) -> int:
        status = self.get_status(session_id)
        progress_map = {
            SessionStatus.PENDING.value: 0,
            SessionStatus.TRANSCRIBING.value: 25,
            SessionStatus.PROCESSING_EVIDENCE.value: 40,
            SessionStatus.AGENTS_RUNNING.value: 60,
            SessionStatus.GENERATING_DOCUMENTS.value: 80,
            SessionStatus.COMPLETE.value: 100,
            SessionStatus.ERROR.value: 0
        }
        return progress_map.get(status, 0)

    def get_current_agent(self, session_id: str) -> Optional[str]:
        session = self.get_session(session_id)
        if not session:
            return None
        
        status = session['status']
        agent_map = {
            SessionStatus.TRANSCRIBING: "Speech-to-Text (Whisper)",
            SessionStatus.PROCESSING_EVIDENCE: "Evidence Processor",
            SessionStatus.AGENTS_RUNNING: "Legal Draft Agent",
            SessionStatus.GENERATING_DOCUMENTS: "Document Generator"
        }
        return agent_map.get(status)

    def get_output_preview(self, session_id: str) -> Optional[str]:
        session = self.get_session(session_id)
        if not session:
            return None
        
        if session['draft_notice']:
            return session['draft_notice'][:200] + "..." if len(session['draft_notice']) > 200 else session['draft_notice']
        elif session['structured_complaint']:
            try:
                complaint = json.loads(session['structured_complaint'])
                return complaint.get('incident_description', '')[:200]
            except:
                return None
        elif session['transcription']:
            return session['transcription'][:200] + "..."
        
        return None

    def _add_log(self, session_id: str, agent: str, status: str, output: str = None, error: str = None):
        if self._db_session:
            try:
                log = ProcessingLog(
                    session_id=session_id,
                    agent=agent,
                    status=status,
                    output=output,
                    error=error
                )
                self._db_session.add(log)
                self._db_session.commit()
            except Exception as e:
                logger.error(f"Failed to save log: {e}")

    def _save_to_db(self, session_id: str):
        if not self._db_session:
            return
        
        try:
            session_data = self._sessions.get(session_id)
            if not session_data:
                return
            
            existing = self._db_session.query(Session).filter_by(id=session_id).first()
            
            if existing:
                existing.updated_at = session_data['updated_at']
                existing.status = session_data['status']
                existing.language = session_data['language']
                existing.transcription = session_data['transcription']
                existing.structured_complaint = session_data['structured_complaint']
                existing.evidence_texts = session_data['evidence_texts']
                existing.draft_notice = session_data['draft_notice']
                existing.case_summary = session_data['case_summary']
                existing.session_metadata = json.dumps(session_data.get('metadata', {}))
            else:
                db_session = Session(
                    id=session_data['id'],
                    created_at=session_data['created_at'],
                    updated_at=session_data['updated_at'],
                    status=session_data['status'],
                    language=session_data['language'],
                    transcription=session_data['transcription'],
                    structured_complaint=session_data['structured_complaint'],
                    evidence_texts=session_data['evidence_texts'],
                    draft_notice=session_data['draft_notice'],
                    case_summary=session_data['case_summary'],
                    session_metadata=json.dumps(session_data.get('metadata', {}))
                )
                self._db_session.add(db_session)
            
            self._db_session.commit()
            logger.debug(f"Saved session {session_id} to database")
            
        except Exception as e:
            logger.error(f"Failed to save session to DB: {e}")
            self._db_session.rollback()

    def delete_session(self, session_id: str):
        with self._global_lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
            if session_id in self._locks:
                del self._locks[session_id]
        
        if self._db_session:
            try:
                self._db_session.query(Session).filter_by(id=session_id).delete()
                self._db_session.query(ProcessingLog).filter_by(session_id=session_id).delete()
                self._db_session.commit()
            except Exception as e:
                logger.error(f"Failed to delete session from DB: {e}")

    def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._global_lock:
            sessions = list(self._sessions.values())
            sessions.sort(key=lambda x: x['created_at'], reverse=True)
            return sessions[:limit]

    def close(self):
        if self._db_session:
            try:
                self._db_session.close()
            except Exception as e:
                logger.error(f"Error closing DB session: {e}")


session_manager = SessionManager()
