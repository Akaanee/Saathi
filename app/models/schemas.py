from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class SessionStatus(str, Enum):
    PENDING = "pending"
    TRANSCRIBING = "transcribing"
    PROCESSING_EVIDENCE = "processing_evidence"
    AGENTS_RUNNING = "agents_running"
    GENERATING_DOCUMENTS = "generating_documents"
    COMPLETE = "complete"
    ERROR = "error"

class TranscriptionResult(BaseModel):
    text: str
    language: str
    confidence: float

class EvidenceExtractionResult(BaseModel):
    texts: List[Dict[str, Any]]
    processing_time: float

class StructuredComplaint(BaseModel):
    complainant_name: Optional[str] = None
    complainant_address: Optional[str] = None
    complainant_occupation: Optional[str] = None
    respondent_name: Optional[str] = None
    respondent_address: Optional[str] = None
    incident_date: Optional[str] = None
    incident_location: Optional[str] = None
    incident_description: Optional[str] = None
    witnesses: Optional[List[str]] = None
    relief_sought: Optional[List[str]] = None
    applicable_laws: Optional[List[str]] = None

class LegalNoticeData(BaseModel):
    header: str
    parties: str
    factual_matrix: str
    legal_grounds: str
    relief_sought: str
    signature_block: str

class CaseSummaryData(BaseModel):
    case_id: str
    parties: str
    key_facts: str
    applicable_laws: str
    summary_assessment: str

class VoiceInput(BaseModel):
    language: Optional[str] = Field(None, description="Language code: hi, bn, or ta")
    session_id: Optional[str] = Field(None, description="Session ID for continuing a session")

class VoiceResponse(BaseModel):
    session_id: str
    transcription: str
    language: str
    confidence: float

class EvidenceInput(BaseModel):
    session_id: str
    filenames: List[str]

class EvidenceResponse(BaseModel):
    session_id: str
    extracted_texts: List[Dict[str, Any]]
    processing_time: float

class StatusResponse(BaseModel):
    session_id: str
    status: SessionStatus
    progress: int = Field(ge=0, le=100)
    current_agent: Optional[str] = None
    output_preview: Optional[str] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class GenerateRequest(BaseModel):
    session_id: str

class GenerateResponse(BaseModel):
    session_id: str
    status: SessionStatus
    message: str

class SessionResponse(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    status: SessionStatus
    language: Optional[str]
    transcription: Optional[str]
    structured_complaint: Optional[str]
    evidence_texts: Optional[str]
    draft_notice: Optional[str]
    case_summary: Optional[str]

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    session_id: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    ollama_connected: bool
    whisper_loaded: bool
    chromadb_ready: bool
