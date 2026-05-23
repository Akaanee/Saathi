# SAATHI: Voice-First Legal Aid Agent - Architecture Design Document

## Project Overview
Saathi is a demo showcasing an agentic legal-aid workflow for India's informal workers. A user can provide a complaint via microphone, audio upload, or typed text, upload evidence images, and receive a case-specific draft legal notice (DOCX/PDF) plus a case summary—powered by local, open-source AI.

---

## 1. System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SAATHI ARCHITECTURE                                 │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           STREAMLIT FRONTEND                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ Complaint    │  │ Image Upload │  │ Notice View  │  │ Case Summary │   │
│  │ Input        │  │  Component   │  │  Component   │  │  Component   │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
│         │                 │                 │                 │            │
│         └─────────────────┼─────────────────┼─────────────────┘            │
│                           │                  │                                │
│                           ▼                  ▼                                │
│                    ┌─────────────────────────────────┐                      │
│                    │       FastAPI Backend (8080)    │                      │
│                    │  ┌─────────────────────────────┐│                      │
│                    │  │      Session State Manager   ││                      │
│                    │  │   (In-memory + SQLite)        ││                      │
│                    │  └──────────────┬──────────────┘│                      │
│                    └────────────────┼────────────────┘                      │
└─────────────────────────────────────┼───────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                 │
                    ▼                 ▼                 ▼
         ┌──────────────────┐ ┌──────────────────┐ ┌─────────────────────────┐
         │   Whisper STT    │ │   OCR Engine     │ │   Agent Pipeline        │
         │ (faster-whisper) │ │ (Surya/Tesseract)│ │ (Python agents)         │
         └────────┬─────────┘ └────────┬─────────┘ └──────────┬──────────────┘
                  │                    │                       │
                  │ Transcribed Text   │ Extracted Text        │ Structured data + drafts
                  │                    │                       │
                  ▼                    ▼                       ▼
         ┌─────────────────────────────────────────────────────────────┐
         │                    OLLAMA (LLM Engine)                      │
         │  ┌─────────────────────────────────────────────────────┐   │
         │  │  llama3.1:8b-instruct-q4_K_M (4.9GB, 8-bit quantized)│   │
         │  │  - Parallel inference for 3 agents max               │   │
         │  │  - 4GB RAM per agent, ~2GB VRAM or system RAM        │   │
         │  └─────────────────────────────────────────────────────┘   │
         └─────────────────────────────────────────────────────────────┘
                                      │
                                      │ Structured Output
                                      ▼
         ┌─────────────────────────────────────────────────────────────┐
         │                 Local Vector Store (JSONL)                  │
         │  Vector retrieval for legal knowledge base                  │
         │  - IPC sections + labor law snippets (seeded)               │
         └─────────────────────────────────────────────────────────────┘
                                      │
                                      │ Retrieved Context
                                      ▼
         ┌─────────────────────────────────────────────────────────────┐
         │                    AGENT PIPELINE                            │
         │  1) Voice intake agent (structures complaint JSON)           │
         │  2) Evidence agent (analyzes OCR text)                       │
         │  3) Legal draft agent (retrieves legal context + drafts)     │
         │                                                             │
         │  Document generator: python-docx + FPDF                      │
         └───────────────────────────┼─────────────────────────────────┘
                                     │
                                     ▼
         ┌─────────────────────────────────────────────────────────────┐
         │                     OUTPUT FILES                            │
         │  📄 draft_legal_notice.docx  📄 case_summary.txt           │
         └─────────────────────────────────────────────────────────────┘
```

---

## 2. Data Flow

```
┌────────────────────────────────────────────────────────────────────────┐
│                         DATA FLOW SEQUENCE                             │
└────────────────────────────────────────────────────────────────────────┘

Step 1: VOICE CAPTURE
┌────────────────────────────────────────────────────────────────────────┐
│ User provides complaint via:                                          │
│ - Microphone (browser permission + device selection)                  │
│ - Upload audio file                                                   │
│ - Type complaint                                                      │
│                                                                       │
│ Microphone/upload: POST /api/voice                                    │
│ Typed: POST /api/voice/text                                           │
│                                                                         │
│ Optimization: 16kHz mono, 30-second max (keeps RAM < 500MB)            │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
Step 2: SPEECH-TO-TEXT
┌────────────────────────────────────────────────────────────────────────┐
│ FastAPI receives audio bytes → faster-whisper (or fallback whisper)   │
│ → Transcription + optional language detection                          │
│                                                                         │
│ Model: tiny (default)                                                   │
│ Language detection: Built-in Whisper language detection               │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
Step 3: EVIDENCE OCR (Parallel)
┌────────────────────────────────────────────────────────────────────────┐
│ Judge uploads image (JPG/PNG) → POST /api/evidence                     │
│ → OCR engine (Surya if installed, otherwise Tesseract)                │
│ → Returns extracted text + confidence scores                           │
│                                                                         │
│ Tesseract requires a local tesseract.exe (PATH or TESSERACT_CMD)       │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
Step 4: AGENT PIPELINE (Python)
┌────────────────────────────────────────────────────────────────────────┐
│ Transcribed text + OCR text → Voice Intake Agent                      │
│ → Structures complaint: parties, incident, relief sought               │
│                                                                         │
│ Structured data → Evidence Processor Agent                              │
│ → Validates evidence relevance, flags gaps                             │
│                                                                         │
│ Structured complaint + Evidence → Legal Draft Agent                    │
│ → Uses local vector retrieval to find applicable legal context         │
│ → Generates: (1) Draft Legal Notice, (2) Case Summary                 │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
Step 5: DOCUMENT GENERATION
┌────────────────────────────────────────────────────────────────────────┐
│ Agent pipeline outputs structured JSON → Document Generator           │
│ → python-docx creates formatted DOCX                                  │
│ → fpdf2 creates PDF (optional)                                        │
│ → case_summary.txt for quick reference                                │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
Step 6: OUTPUT DELIVERY
┌────────────────────────────────────────────────────────────────────────┐
│ Streamlit polls /api/status/{session_id} every 2 seconds               │
│ → Returns generation progress                                          │
│ → On completion: download links displayed                              │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Agent Workflow & State Management

### Session State Flow
```
Session Created
      │
      ├─→ [status: pending] Voice Recording
      │
      ├─→ [status: transcribing] Whisper Processing
      │
      ├─→ [status: processing_evidence] Evidence OCR (Surya or Tesseract)
      │
      ├─→ [status: agents_running] Agent Pipeline
      │         │
      │         ├─→ Voice Intake Agent (Task 1)
      │         ├─→ Evidence Processor (Task 2)
      │         └─→ Legal Draft Agent (Task 3)
      │
      ├─→ [status: generating_documents] DOCX/PDF Creation
      │
      └─→ [status: complete] Download Ready
```

### Shared Context (Session State)
Session state is stored in memory and periodically persisted to SQLite (`saathi.db`). Key fields include:

```json
{
  "transcription": "raw or user-edited complaint text",
  "structured_complaint": "{...JSON string...}",
  "evidence_results": [{"filename": "...", "text": "...", "confidence": 0.0}],
  "metadata": {
    "user_notes": "additional corrections / missing details",
    "questions_status": "idle|running|done|error",
    "questions_result": {"missing_fields": [], "questions": []}
  },
  "draft_notice": "preview text used for UI preview",
  "case_summary": "preview text used for UI preview"
}
```

---

## 4. Open-Source Libraries & Versions

### Core Framework
```yaml
# requirements.txt
fastapi==0.109.0
uvicorn[standard]==0.27.0
streamlit==1.31.0
python-multipart==0.0.6
aiofiles==23.2.1
```

### AI/ML Stack
```yaml
ollama==0.1.35
faster-whisper==1.0.3
```

### Speech & Vision
```yaml
# Surya OCR (optional, if installed)
surya-ocr==0.4.0

# Fallback: Tesseract wrapper
pytesseract==0.3.10
Pillow==10.2.0
```

### Document Generation
```yaml
python-docx==1.1.0
fpdf2==2.7.7
```

### Utilities
```yaml
python-dotenv==1.0.0
pydantic==2.6.0
sqlalchemy==2.0.25
psutil==5.9.8
```

### Model Downloads (Ollama)
```bash
# LLM: Quantized llama3.1 8B (4-bit/8-bit)
ollama pull llama3.1:8b-instruct-q4_K_M

# Embedding model for legal retrieval
ollama pull nomic-embed-text
```

---

## 5. Project Folder Structure

```
saathi/
├── app/
│   ├── main.py                      # FastAPI entry point
│   ├── config.py
│   ├── api/routes/
│   │   ├── voice.py                 # /api/voice + /api/voice/text
│   │   ├── evidence.py              # /api/evidence + /api/evidence/manual
│   │   ├── status.py                # /api/status + async questions + edit transcription
│   │   └── generate.py              # /api/generate
│   ├── agents/
│   │   ├── crew.py                  # Orchestrates agent pipeline
│   │   ├── voice_intake_agent.py
│   │   ├── evidence_agent.py
│   │   └── legal_draft_agent.py
│   ├── services/
│   │   ├── stt_service.py           # faster-whisper (STT)
│   │   ├── ocr_service.py           # Surya OCR or Tesseract fallback
│   │   ├── llm_service.py           # Ollama wrapper
│   │   ├── vector_service.py        # Local vector store (JSONL)
│   │   └── document_service.py      # DOCX/PDF generation
│   └── utils/session_manager.py     # Session state (in-memory + SQLite)
│
├── ui/
│   ├── app.py                       # Streamlit entry point
│   ├── pages/1_Record_Complaint.py  # End-to-end workflow UI
│   └── components/
│       ├── voice_recorder.py
│       └── file_uploader.py
│
├── knowledge_base/chroma_db/        # Local vector store files (*.jsonl)
├── outputs/                         # Generated documents
├── logs/
├── tests/
├── .env
├── .env.example
└── requirements.txt
```

---

## 6. Key API Endpoints

- `POST /api/voice` (multipart): transcribe an uploaded/recorded audio file
- `POST /api/voice/text` (form): submit typed complaint text
- `POST /api/evidence` (multipart): upload evidence images for OCR
- `POST /api/evidence/manual` (form): add manual evidence text when OCR isn't available/accurate
- `GET /api/status/{session_id}`: session progress + preview + outputs
- `GET /api/status/{session_id}/transcription`: current transcription
- `POST /api/status/{session_id}/transcription`: update transcription (user edits)
- `POST /api/status/{session_id}/questions`: start missing-info suggestions (async)
- `GET /api/status/{session_id}/questions`: poll missing-info result
- `POST /api/generate`: run the pipeline and create output documents

- [ ] UI remains responsive during processing
- [ ] No crashes during 10 consecutive runs

### Demo Experience
- [ ] Judge persona can use without technical knowledge
- [ ] Progress feedback keeps user engaged
- [ ] Error messages are helpful, not technical
- [ ] WhatsApp-like voice interaction feels natural
