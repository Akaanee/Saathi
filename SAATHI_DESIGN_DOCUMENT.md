# SAATHI: Voice-First Legal Aid Agent - Architecture Design Document

## Project Overview
Saathi is a hackathon demo showcasing multi-agent orchestration for legal aid to India's informal workers. A judge records voice complaints in Hindi/Bengali/Tamil, uploads evidence images, and receives a draft legal notice (DOCX/PDF) with case summary—all powered by local, open-source AI.

---

## 1. System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SAATHI ARCHITECTURE                                 │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           STREAMLIT FRONTEND                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ Voice Record │  │ Image Upload │  │ Notice View  │  │ Case Summary │   │
│  │  Component   │  │  Component   │  │  Component   │  │  Component   │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
│         │                 │                 │                 │            │
│         └─────────────────┼─────────────────┼─────────────────┘            │
│                           │                  │                                │
│                           ▼                  ▼                                │
│                    ┌─────────────────────────────────┐                      │
│                    │       FastAPI Backend (8080)    │                      │
│                    │  ┌─────────────────────────────┐│                      │
│                    │  │      Session State Manager   ││                      │
│                    │  │   (In-memory + SQLite backup) ││                      │
│                    │  └──────────────┬──────────────┘│                      │
│                    └────────────────┼────────────────┘                      │
└─────────────────────────────────────┼───────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                 │
                    ▼                 ▼                 ▼
         ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
         │   WHISPER.CPP   │ │    SURYA OCR     │ │     CREWAI       │
         │   (STT Model)   │ │   (Image Parse)  │ │   Multi-Agent    │
         │                  │ │                  │ │   Orchestrator   │
         │  tinyInt8 model  │ │  Hindi/Bengali/  │ │                  │
         │  (75MB, 16GB OK) │ │  Tamil support   │ │                  │
         └────────┬─────────┘ └────────┬─────────┘ └────────┬─────────┘
                  │                    │                    │
                  │ Transcribed Text   │ Extracted Text    │ Agent Tasks
                  │                    │                    │
                  ▼                    ▼                    ▼
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
         │                       CHROMADB                               │
         │  Vector Database for Legal Knowledge Base                   │
         │  - IPC Section queries                                      │
         │  - Labor law precedents                                      │
         │  - Document templates                                        │
         └─────────────────────────────────────────────────────────────┘
                                      │
                                      │ Retrieved Context
                                      ▼
         ┌─────────────────────────────────────────────────────────────┐
         │                    CREWAI AGENT CREW                         │
         │                                                              │
         │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐ │
         │  │ Voice Intake   │  │ Evidence Proc  │  │ Legal Draft   │ │
         │  │ Agent          │──│ Agent          │──│ Agent         │ │
         │  │                │  │                │  │               │ │
         │  │ Task: Transcribe│  │ Task: OCR      │  │ Task: Generate│ │
         │  │ & Structure    │  │ & Extract      │  │ Notice+Summary│ │
         │  │                │  │                │  │               │ │
         │  └────────────────┘  └────────────────┘  └───────────────┘ │
         │           │                  │                   │         │
         │           └──────────────────┴───────────────────┘         │
         │                          │                                   │
         │                          ▼                                   │
         │              ┌─────────────────────────┐                     │
         │              │   Document Generator    │                     │
         │              │   (python-docx + FPDF)  │                     │
         │              └────────────┬────────────┘                     │
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
│ Judge clicks "Record" → Browser MediaRecorder API captures audio      │
│ → WebM/PCM format → Base64 encoded → POST /api/voice                  │
│                                                                         │
│ Optimization: 16kHz mono, 30-second max (keeps RAM < 500MB)            │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
Step 2: SPEECH-TO-TEXT
┌────────────────────────────────────────────────────────────────────────┐
│ FastAPI receives audio bytes → whisper.cpp loads tinyInt8 model       │
│ → Transcription in Hindi/Bengali/Tamil → Returns text                 │
│                                                                         │
│ Model: whisper.cpp base/tiny model (~75MB)                              │
│ Language detection: Built-in Whisper language detection               │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
Step 3: EVIDENCE OCR (Parallel)
┌────────────────────────────────────────────────────────────────────────┐
│ Judge uploads image (JPG/PNG) → POST /api/evidence                     │
│ → Surya OCR processes image → Extracts text in regional script         │
│ → Returns extracted text + confidence scores                           │
│                                                                         │
│ Surya: FastAPI wrapper around Surya OCR (No GPU needed, CPU-based)     │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
Step 4: AGENT ORCHESTRATION (CrewAI)
┌────────────────────────────────────────────────────────────────────────┐
│ Transcribed text + OCR text → Voice Intake Agent                      │
│ → Structures complaint: parties, incident, relief sought               │
│                                                                         │
│ Structured data → Evidence Processor Agent                              │
│ → Validates evidence relevance, flags gaps                             │
│                                                                         │
│ Structured complaint + Evidence → Legal Draft Agent                    │
│ → Uses ChromaDB context to find applicable IPC sections                │
│ → Generates: (1) Draft Legal Notice, (2) Case Summary                 │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
Step 5: DOCUMENT GENERATION
┌────────────────────────────────────────────────────────────────────────┐
│ CrewAI outputs structured JSON → Document Generator                   │
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
      ├─→ [status: processing_evidence] Surya OCR (can be parallel)
      │
      ├─→ [status: agents_running] CrewAI Pipeline
      │         │
      │         ├─→ Voice Intake Agent (Task 1)
      │         ├─→ Evidence Processor (Task 2)
      │         └─→ Legal Draft Agent (Task 3)
      │
      ├─→ [status: generating_documents] DOCX/PDF Creation
      │
      └─→ [status: complete] Download Ready
```

### Shared Context (via CrewAI Crew Memory)
```python
shared_context = {
    "original_complaint": "Hindi transcription...",
    "detected_language": "hi",
    "complainant_details": {...},
    "respondent_details": {...},
    "incident_description": "...",
    "relief_sought": "...",
    "evidence_texts": [...],
    "applicable_laws": ["IPC 420", "BOCW Act"],
    "draft_notice": "...",
    "case_summary": "..."
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
crewai==0.30.0
langchain-core==0.1.20
langchain-community==0.0.20
ollama==0.1.35
chromadb==0.4.22
sentence-transformers==2.3.1
```

### Speech & Vision
```yaml
# whisper.cpp Python bindings (via unofficial package)
whispercpp==1.4.0

# Surya OCR
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

# Embedding model for ChromaDB
ollama pull nomic-embed-text
```

### Whisper Model
```bash
# Download tiny model for whisper.cpp
# Will auto-download on first run (~75MB)
```

---

## 5. Project Folder Structure

```
saathi/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI entry point
│   ├── config.py                  # Environment & model config
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── voice.py           # /api/voice endpoint
│   │   │   ├── evidence.py        # /api/evidence endpoint
│   │   │   └── status.py          # /api/status/{id} endpoint
│   │   │
│   │   └── dependencies.py        # Shared dependencies
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── crew.py                # CrewAI crew definition
│   │   ├── voice_intake_agent.py  # Voice Intake Agent
│   │   ├── evidence_agent.py      # Evidence Processor Agent
│   │   └── legal_draft_agent.py   # Legal Draft Agent
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── stt_service.py         # Whisper/STT service
│   │   ├── ocr_service.py         # Surya/Tesseract OCR
│   │   ├── llm_service.py         # Ollama wrapper
│   │   ├── vector_service.py      # ChromaDB operations
│   │   └── document_service.py    # DOCX/PDF generation
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── schemas.py             # Pydantic models
│   │   └── database.py            # SQLAlchemy models
│   │
│   └── utils/
│       ├── __init__.py
│       ├── audio_utils.py         # Audio preprocessing
│       ├── image_utils.py         # Image preprocessing
│       └── session_manager.py     # Session state management
│
├── ui/
│   ├── __init__.py
│   ├── app.py                     # Streamlit entry point
│   │
│   ├── pages/
│   │   ├── __init__.py
│   │   ├── 1_Record_Complaint.py   # Main recording page
│   │   └── 2_View_Results.py      # Results/download page
│   │
│   └── components/
│       ├── __init__.py
│       ├── voice_recorder.py      # Voice recording widget
│       ├── file_uploader.py       # Evidence upload widget
│       ├── language_selector.py   # Language selection
│       └── progress_display.py    # Status/progress display
│
├── knowledge_base/
│   ├── __init__.py
│   ├── chroma_setup.py            # ChromaDB initialization
│   ├── legal_docs/               # Legal knowledge documents
│   │   ├── ipc_sections.json
│   │   ├── labor_laws.json
│   │   └── templates/
│   │       ├── legal_notice_template.docx
│   │       └── case_summary_template.txt
│   └── embeddings/               # Cached embeddings
│
├── tests/
│   ├── __init__.py
│   ├── test_stt.py
│   ├── test_ocr.py
│   ├── test_agents.py
│   └── test_api.py
│
├── scripts/
│   ├── download_models.py        # Model download helper
│   ├── seed_knowledge_base.py    # ChromaDB seeding
│   └── setup_ollama.py           # Ollama setup script
│
├── logs/
│   └── app.log                    # Application logs
│
├── outputs/                       # Generated documents
│   └── .gitkeep
│
├── .env                          # Environment variables
├── .env.example
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## 6. Build Sequence & Prompts

### Phase 1: Project Scaffolding (This Phase)

**Step 1.1: Create project structure and requirements.txt**
```prompt
Create the complete folder structure and requirements.txt for the Saathi project based on the architecture document I've provided. Include:
1. All directories as listed in section 5
2. requirements.txt with exact versions specified
3. .env.example with all necessary environment variables
4. __init__.py files for all Python packages
```

**Step 1.2: Create configuration and database models**
```prompt
Generate config.py with:
- Model paths (Ollama URL, Whisper model path, ChromaDB path)
- Resource limits (max audio duration, max image size)
- Supported languages list
- Environment variable loading

Generate database.py with SQLAlchemy models for:
- Session (id, created_at, status, language, metadata)
- ProcessingLog (session_id, agent, status, timestamp, output)
```

---

### Phase 2: Core Services

**Step 2.1: STT Service (Whisper)**
```prompt
Implement stt_service.py for the Saathi app:
- Use whispercpp Python bindings (whispercpp==1.4.0)
- Load tinyInt8 Whisper model on initialization
- transcribe_audio(audio_bytes) -> {text, language, confidence}
- Handle WebM to WAV conversion if needed
- Add streaming support for partial results
- Include error handling for corrupted audio
```

**Step 2.2: OCR Service (Surya)**
```prompt
Implement ocr_service.py for the Saathi app:
- Use Surya OCR for Indian language text extraction
- Fallback to Tesseract with pytesseract if Surya fails
- Support Hindi, Bengali, Tamil text detection
- extract_text_from_image(image_bytes) -> {text, language, confidence, boxes}
- Batch processing for multiple images
- Image preprocessing (resize, denoise) for better OCR
```

**Step 2.3: LLM Service (Ollama)**
```prompt
Implement llm_service.py for the Saathi app:
- Ollama API wrapper using ollama==0.1.35
- Connect to local Ollama at 127.0.0.1:11434
- generate_response(prompt, system_prompt, context) -> text
- Use llama3.1:8b-instruct-q4_K_M model
- Implement streaming for real-time output
- Add retry logic for model loading failures
- Memory management: unload model after 5 min idle
```

**Step 2.4: Vector Service (ChromaDB)**
```prompt
Implement vector_service.py for the Saathi app:
- ChromaDB client with sentence-transformers embeddings
- Use nomic-embed-text embedding model via Ollama
- initialize_knowledge_base(): seed with IPC sections, labor laws
- query_legal_context(query, top_k=5) -> List[Document]
- add_document(collection_name, text, metadata)
- Implement hybrid search (keyword + vector)
```

---

### Phase 3: Document Generation

**Step 3.1: Document Service**
```prompt
Implement document_service.py for the Saathi app:
- generate_legal_notice(complaint_data) -> DOCX bytes
  * Use python-docx==1.1.0
  * Include: Header, Parties, Factual Matrix, Legal Grounds, Relief Sought, Signature Block
  * Apply professional formatting with styles
  
- generate_case_summary(complaint_data) -> TXT string
  * Include: Case ID, Parties, Key Facts, Applicable Laws, Summary Assessment
  
- generate_pdf(docs) -> PDF bytes (optional, using fpdf2)
```

---

### Phase 4: CrewAI Agents

**Step 4.1: Voice Intake Agent**
```prompt
Implement voice_intake_agent.py for the Saathi app:
- Agent role: "Expert Legal Intake Specialist for Indian Courts"
- Goal: Transform raw voice transcription into structured complaint
- Backstory: 15 years experience in legal aid for informal workers
- Tools: Use CrewAI's built-in tools for text processing
- Task: Extract and structure:
  * Complainant details (name, address, occupation)
  * Respondent details (name, address, if known)
  * Incident date and location
  * Detailed incident description
  * Witnesses (if mentioned)
  * Relief sought (compensation, action, etc.)
  * Relevant law sections suspected
- Use Ollama with llama3.1 for LLM calls
```

**Step 4.2: Evidence Processor Agent**
```prompt
Implement evidence_agent.py for the Saathi app:
- Agent role: "Expert Forensic Document Analyst"
- Goal: Analyze uploaded evidence and validate against complaint
- Backstory: Former investigative journalist turned legal analyst
- Task: Process OCR-extracted text from images:
  * Extract relevant information (dates, amounts, names, locations)
  * Validate consistency with voice complaint
  * Flag contradictions or gaps
  * Suggest additional evidence if needed
  * Rank evidence strength
- Use Ollama with llama3.1 for LLM calls
```

**Step 4.3: Legal Draft Agent**
```prompt
Implement legal_draft_agent.py for the Saathi app:
- Agent role: "Senior Legal Draftsman specializing in Indian Labor Law"
- Goal: Generate comprehensive legal notice and case summary
- Backstory: Former High Court clerk with expertise in BOCW, MWA
- Task: Using ChromaDB context and structured complaint:
  * Identify applicable IPC sections and labor laws
  * Draft formal legal notice with proper legal language
  * Generate case summary for judge briefing
  * Ensure compliance with Indian legal document standards
- Use Ollama with llama3.1 for LLM calls
- Fetch context from ChromaDB knowledge base
```

**Step 4.4: Crew Orchestration**
```prompt
Implement crew.py for the Saathi app:
- Define Crew with sequential task execution:
  1. Voice Intake Task → Voice Intake Agent
  2. Evidence Processing Task → Evidence Agent (parallel with 1)
  3. Legal Draft Task → Legal Draft Agent (after 1 and 2)
- Use CrewAI's Crew class with process=Process.sequential
- Implement memory sharing between agents
- Add error handling and retry logic
- Include progress callbacks for Streamlit polling
```

---

### Phase 5: FastAPI Backend

**Step 5.1: API Routes**
```prompt
Implement FastAPI routes for the Saathi app:

routes/voice.py:
- POST /api/voice
  * Accept: multipart/form-data with audio file
  * Process: STT service
  * Return: {session_id, transcription, language}

routes/evidence.py:
- POST /api/evidence
  * Accept: multipart/form-data with image(s)
  * Process: OCR service
  * Return: {session_id, extracted_texts}

routes/status.py:
- GET /api/status/{session_id}
  * Return: {status, progress, current_agent, output_preview}
- POST /api/generate
  * Trigger CrewAI pipeline
  * Return: {session_id, status: "processing"}
```

**Step 5.2: Session Manager**
```prompt
Implement session_manager.py for the Saathi app:
- In-memory session store with SQLite backup
- SessionManager class:
  * create_session() -> Session
  * get_session(id) -> Session
  * update_session(id, **kwargs)
  * add_transcription(session_id, text)
  * add_evidence(session_id, texts[])
  * set_status(session_id, status)
  * get_status(session_id) -> str
- Thread-safe operations with locks
- Auto-save to SQLite every 30 seconds
```

---

### Phase 6: Streamlit UI

**Step 6.1: Voice Recorder Component**
```prompt
Implement components/voice_recorder.py for the Saathi app:
- Streamlit custom component using streamlit-js-evaluator
- Features:
  * Record button with visual feedback (red dot when recording)
  * 30-second max recording
  * Audio level indicator
  * Language selection dropdown
  * Playback before submission
  * Convert to WAV format for STT
```

**Step 6.2: Main Recording Page**
```prompt
Implement pages/1_Record_Complaint.py for the Saathi app:
- Page title: "📝 Record Your Complaint"
- Language selector (Hindi, Bengali, Tamil)
- Voice recorder component
- "Submit for Processing" button
- Evidence upload section:
  * Multi-file uploader for images
  * Preview thumbnails
  * Remove button for each
- Progress display during processing
- Error handling with retry option
```

**Step 6.3: Results Page**
```prompt
Implement pages/2_View_Results.py for the Saathi app:
- Display transcription with language tag
- Show extracted evidence text
- Display generated legal notice preview
- Download buttons:
  * "Download Legal Notice (DOCX)"
  * "Download Case Summary (TXT)"
  * "Download PDF"
- "Start New Complaint" button
- Option to regenerate with different parameters
```

---

### Phase 7: Setup & Testing Scripts

**Step 7.1: Model Download Script**
```prompt
Create scripts/download_models.py:
- Check Ollama installation
- Pull llama3.1:8b-instruct-q4_K_M (8B, 4-bit quantized)
- Pull nomic-embed-text for embeddings
- Download whisper.cpp tiny model
- Verify all models with test inference
- Print status and memory requirements
```

**Step 7.2: Knowledge Base Seeding**
```prompt
Create scripts/seed_knowledge_base.py:
- Load IPC sections from legal_docs/ipc_sections.json
- Load labor laws from legal_docs/labor_laws.json
- Chunk documents appropriately (500 tokens)
- Generate embeddings using nomic-embed-text
- Store in ChromaDB with appropriate metadata
- Verify with test queries
```

---

## 7. End-to-End Demo Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          DEMO EXECUTION FLOW                             │
└─────────────────────────────────────────────────────────────────────────┘

1. INITIALIZATION (at app startup)
   └─→ Load Whisper tiny model (~75MB into RAM)
   └─→ Initialize ChromaDB with legal knowledge
   └─→ Ollama loads llama3.1:8b on first agent call (3-5 sec)

2. JUDGE INTERACTION (Streamlit UI)
   
   a) Language Selection
      └─→ Choose "Hindi" from dropdown
      
   b) Voice Recording
      └─→ Click "Start Recording" button
      └─→ Speak: "मेरा नाम रमेश है, मैं एक मजदूर हूं..."
      └─→ Click "Stop Recording"
      └─→ Click "Submit"
      
   c) Evidence Upload
      └─→ Upload wage slip image
      └─→ Upload contractor's threats screenshot
      └─→ Click "Process Evidence"

3. PROCESSING PIPELINE (Backend)

   a) STT Processing (Whisper.cpp)
      └─→ ~2-3 seconds for 30-sec audio
      └─→ Returns: "मेरा नाम रमेश है, मैं बिजली विभाग..."
      
   b) OCR Processing (Surya)
      └─→ ~5 seconds per image
      └─→ Returns: extracted text with confidence scores
      
   c) CrewAI Pipeline (3 agents)
      └─→ Voice Intake Agent: 5-10 seconds
      └─→ Evidence Agent: 5-10 seconds (parallel)
      └─→ Legal Draft Agent: 10-15 seconds
      └─→ Total: ~20-30 seconds
      
   d) Document Generation
      └─→ ~2 seconds for DOCX + TXT

4. RESULT DELIVERY
   └─→ Streamlit shows: "Your documents are ready!"
   └─→ Judge clicks "Download Legal Notice"
   └─→ DOCX file saved to device

5. TOTAL TIME: ~45-60 seconds for complete pipeline
```

---

## 8. Memory & Resource Management

### Memory Budget (16GB RAM)
```
┌────────────────────────────────────────────────────────────────────────┐
│ COMPONENT                    │ BASE RAM    │ PEAK RAM  │ NOTES         │
├──────────────────────────────┼─────────────┼───────────┼──────────────┤
│ Windows/System               │ ~4GB        │ ~4GB      │ Fixed         │
│ Streamlit UI                 │ ~200MB      │ ~400MB    │ Frontend      │
│ FastAPI + Session Manager    │ ~150MB      │ ~300MB    │ Backend       │
│ Whisper tiny model           │ ~150MB      │ ~200MB    │ STT           │
│ Ollama + llama3.1:8b-q4     │ ~5GB        │ ~6GB      │ LLM           │
│ ChromaDB + embeddings        │ ~500MB      │ ~1GB      │ Knowledge     │
│ Surya OCR                    │ ~300MB      │ ~500MB    │ Per image     │
│ Document generation          │ ~100MB      │ ~200MB    │ Temp          │
├──────────────────────────────┼─────────────┼───────────┼──────────────┤
│ TOTAL                        │ ~10.4GB     │ ~12.6GB   │ ✓ Fits 16GB   │
└──────────────────────────────┴─────────────┴───────────┴──────────────┘
```

### Optimizations
1. **Lazy Loading**: Ollama loads model only on first request
2. **Model Unloading**: Unload Ollama after 5 minutes idle
3. **Batch OCR**: Process images sequentially to limit memory spike
4. **Streaming Output**: Stream LLM tokens to reduce perceived latency
5. **Chunked Transcription**: Process audio in 30-second chunks

---

## 9. Testing Strategy

### Unit Tests
```bash
# Test each service independently
pytest tests/test_stt.py -v          # Mock audio input
pytest tests/test_ocr.py -v          # Mock image input
pytest tests/test_agents.py -v       # Mock Ollama responses
pytest tests/test_api.py -v          # Test endpoints
```

### Integration Tests
```bash
# Test full pipeline with sample data
pytest tests/integration/ -v

# Sample test case:
# 1. Submit Hindi audio file
# 2. Verify transcription accuracy
# 3. Submit evidence image
# 4. Verify document generation
# 5. Validate DOCX structure
```

### Manual Testing Checklist
- [ ] Record 30-second Hindi audio → verify transcription
- [ ] Upload wage slip image → verify OCR text extraction
- [ ] Complete pipeline → verify DOCX download
- [ ] Switch to Bengali → verify language detection
- [ ] Switch to Tamil → verify script recognition
- [ ] Upload 5 images → verify batch processing
- [ ] Check memory usage in Task Manager < 14GB
- [ ] Verify Ollama uses ~5GB RAM

---

## 10. Potential Pitfalls & Workarounds

### Pitfall 1: Ollama Model Loading Time
**Problem**: First agent call takes 10-30 seconds to load llama3.1
**Workaround**: 
- Pre-warm model on app startup with dummy request
- Show "Initializing AI models..." message
- Implement optimistic loading when user starts recording

### Pitfall 2: Whisper Recognition Accuracy for Indian Accents
**Problem**: Whisper may misrecognize regional accents
**Workaround**:
- Use tinyInt8 model (trained on more diverse data)
- Implement post-processing with language-specific corrections
- Allow manual transcription correction in UI

### Pitfall 3: ChromaDB Query Speed
**Problem**: Semantic search may return irrelevant results
**Workaround**:
- Fine-tune chunk sizes (500 tokens)
- Add metadata filtering (IPC vs Labor Law)
- Use hybrid search (BM25 + vector)

### Pitfall 4: Surya OCR for Handwritten Text
**Problem**: Surya OCR struggles with handwritten documents
**Workaround**:
- Display confidence scores to user
- Suggest "Type text manually" fallback
- Focus demo on printed/typed evidence

### Pitfall 5: Memory Pressure on 16GB RAM
**Problem**: Multiple agents + models may exceed RAM
**Workaround**:
- Sequential agent execution (not parallel)
- Force garbage collection after each step
- Monitor with psutil and log warnings
- Cap concurrent sessions to 2

### Pitfall 6: Ollama Context Window Limits
**Problem**: llama3.1 8B has 8K context, may truncate long complaints
**Workaround**:
- Chunk long transcriptions
- Summarize intermediate agent outputs
- Set max_input_tokens=6000 in Ollama config

---

## 11. Configuration Reference

### .env File
```bash
# Ollama Configuration
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.1:8b-instruct-q4_K_M
OLLAMA_EMBED_MODEL=nomic-embed-text

# Whisper Configuration
WHISPER_MODEL=tiny
WHISPER_MODEL_DIR=models/whisper

# ChromaDB Configuration
CHROMA_PERSIST_DIR=knowledge_base/chroma_db
EMBEDDING_MODEL=all-MiniLM-L6-v2

# Application Configuration
MAX_AUDIO_DURATION=30
MAX_IMAGE_SIZE=10485760  # 10MB
SUPPORTED_LANGUAGES=hi,bn,ta
SESSION_TIMEOUT=3600

# Paths
OUTPUT_DIR=outputs
LOG_FILE=logs/app.log
```

---

## 12. Success Metrics for Hackathon Demo

### Functional Requirements
- [ ] Voice recording in Hindi, Bengali, Tamil works
- [ ] STT produces readable transcription
- [ ] OCR extracts text from printed documents
- [ ] Legal notice generates with proper structure
- [ ] Case summary provides accurate briefing
- [ ] Documents are downloadable

### Performance Requirements
- [ ] Pipeline completes in < 60 seconds
- [ ] Memory stays below 14GB
- [ ] UI remains responsive during processing
- [ ] No crashes during 10 consecutive runs

### Demo Experience
- [ ] Judge persona can use without technical knowledge
- [ ] Progress feedback keeps user engaged
- [ ] Error messages are helpful, not technical
- [ ] WhatsApp-like voice interaction feels natural
