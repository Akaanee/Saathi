from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from enum import Enum

Base = declarative_base()

class SessionStatus(str, Enum):
    PENDING = "pending"
    TRANSCRIBING = "transcribing"
    PROCESSING_EVIDENCE = "processing_evidence"
    AGENTS_RUNNING = "agents_running"
    GENERATING_DOCUMENTS = "generating_documents"
    COMPLETE = "complete"
    ERROR = "error"

class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = Column(SQLEnum(SessionStatus), default=SessionStatus.PENDING)
    language = Column(String, nullable=True)
    transcription = Column(Text, nullable=True)
    structured_complaint = Column(Text, nullable=True)
    evidence_texts = Column(Text, nullable=True)
    draft_notice = Column(Text, nullable=True)
    case_summary = Column(Text, nullable=True)
    session_metadata = Column(Text, nullable=True)

    processing_logs = relationship("ProcessingLog", back_populates="session", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "status": self.status.value if self.status else None,
            "language": self.language,
            "transcription": self.transcription,
            "structured_complaint": self.structured_complaint,
            "evidence_texts": self.evidence_texts,
            "draft_notice": self.draft_notice,
            "case_summary": self.case_summary,
            "metadata": self.session_metadata
        }

class ProcessingLog(Base):
    __tablename__ = "processing_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"))
    agent = Column(String, nullable=False)
    status = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    output = Column(Text, nullable=True)
    error = Column(Text, nullable=True)

    session = relationship("Session", back_populates="processing_logs")

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "agent": self.agent,
            "status": self.status,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "output": self.output,
            "error": self.error
        }
