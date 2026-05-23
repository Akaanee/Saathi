# SAATHI - Quick Start Guide

## 🚀 Demo Commands

### **Step 1: Install Dependencies**

```bash
# Navigate to project
cd c:\Users\arghy\Documents\trae_projects\Saathi

# Install uv (fast Python package manager) - Windows PowerShell
powershell -ExecutionPolicy ByPass -c "irm `https://astral.sh/uv/install.ps1`  | iex"

# Install all dependencies
uv pip install -r requirements.txt
```

### **Step 2: Start Ollama**

Open a new terminal and run:

```bash
# Install Ollama - Windows PowerShell
irm `https://ollama.com/install.ps1`  | iex

# Start Ollama server
ollama serve

# Pull required models (first time only)
ollama pull llama3.1:8b-instruct-q4_K_M
ollama pull nomic-embed-text
```

### **Step 3: Start Backend API**

Open another terminal and run:

```bash
cd c:\Users\arghy\Documents\trae_projects\Saathi

# Start FastAPI backend
python app/main.py
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8080
```

API documentation available at: http://127.0.0.1:8080/docs

### **Step 4: Start Frontend UI**

Open a third terminal and run:

```bash
cd c:\Users\arghy\Documents\trae_projects\Saathi

# Start Streamlit UI
python -m streamlit run ui/app.py --server.port 8501
```

Streamlit will open automatically in your browser at: http://localhost:8501

---

## 📋 Complete Demo Workflow

### **1. Open Browser**
Navigate to: http://localhost:8501

### **2. Select Page**
Click "Record Complaint" in the sidebar

### **3. Provide Complaint Input**
- Choose one of:
  - Microphone (browser permission required)
  - Upload audio file
  - Type complaint (for users who can't speak)
- Pick language (Auto Detect recommended for mixed speech)
- If using microphone and nothing is captured:
  - Click "Request microphone permission"
  - In browser site settings, set Microphone = Allow and select the correct input device (built-in/headset)
- Include:
  - Your name and occupation
  - Respondent's name and details
  - What happened
  - When and where
  - What relief you seek

### **4. Submit Transcription**
Click "Submit for Transcription"

### **5. Upload Evidence**
- Click "Upload Evidence" tab
- Upload images (wage slips, contracts, photos)
- Click "Process Evidence"

### **6. Generate Documents**
- Click "Generate Documents" tab
- Click "Generate Legal Notice & Case Summary"
- Wait for processing (30-60 seconds)
- Preview is shown in the UI and downloadable files are saved under `outputs/`

---

## 🎯 Testing API Endpoints

### **Check Health**
```bash
curl http://127.0.0.1:8080/health
```

### **Get API Info**
```bash
curl http://127.0.0.1:8080/info
```

### **Upload Voice (if you have audio file)**
```bash
curl -X POST "http://127.0.0.1:8080/api/voice" \
  -F "audio=@recording.wav" \
  -F "language=hi"
```

### **Submit Typed Complaint**
```bash
curl -X POST "http://127.0.0.1:8080/api/voice/text" \
  -F "transcription=My salary is unpaid..." \
  -F "language=auto"
```

### **Check Status**
```bash
curl http://127.0.0.1:8080/api/status/{session_id}
```

### **Suggest Missing Info (Async)**
```bash
curl -X POST "http://127.0.0.1:8080/api/status/{session_id}/questions"
curl http://127.0.0.1:8080/api/status/{session_id}/questions
```

### **Generate Documents**
```bash
curl -X POST "http://127.0.0.1:8080/api/generate" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "your-session-id"}'
```

---

## ⚙️ Configuration

### **Environment Variables (.env)**
Set values in `.env` in the project root:

```env
# Ollama
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.1:8b-instruct-q4_K_M
OLLAMA_EMBED_MODEL=nomic-embed-text

# Whisper (for speech-to-text)
WHISPER_MODEL=tiny

# Tesseract (OCR fallback when Surya OCR isn't available)
# Set to your local tesseract.exe if it's not on PATH
TESSERACT_CMD=C:\Users\arghy\Documents\trae_projects\Saathi\Tesseract-OCR\tesseract.exe

# Application
MAX_AUDIO_DURATION=30
MAX_IMAGE_SIZE=10485760
SUPPORTED_LANGUAGES=hi,bn,ta,en
SESSION_TIMEOUT=3600

# Server
API_HOST=127.0.0.1
API_PORT=8080
UI_PORT=8501
```

---

## 🛠️ Troubleshooting

### **Port Already in Use**
If port 8080 or 8501 is busy:
```bash
# Use different ports
python app/main.py  # Edit API_PORT in .env to 8081
streamlit run ui/app.py --server.port 8502
```

### **Ollama Not Running**
```bash
# Check if Ollama is running
ollama list

# If not, start it
ollama serve
```

### **Model Not Found**
```bash
# Pull the model
ollama pull llama3.1:8b-instruct-q4_K_M
```

### **Import Errors**
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### **Memory Issues**
If you encounter out of memory errors:
1. Close other applications
2. Use smaller models:
   - `ollama pull llama3.2:3b` (instead of 8b)
   - Edit `OLLAMA_MODEL` in `.env`

---

## 📊 System Requirements

### **Minimum**
- 8GB RAM
- Python 3.10+
- Windows 10+

### **Recommended**
- 16GB RAM
- Python 3.14+
- Windows 11

### **Storage**
- ~10GB for models
- ~1GB for project

---

## 🎓 Architecture Overview

```
┌─────────────────────────────────────┐
│    Browser (Streamlit - :8501)      │
│  ┌─────────────────────────────────┐ │
│  │ Voice/Upload/Typed Input       │ │
│  │ Evidence Upload + Progress     │ │
│  │ Preview + Downloads            │ │
│  └─────────────────────────────────┘ │
└──────────────┬──────────────────────┘
               │ HTTP
               ▼
┌─────────────────────────────────────┐
│    FastAPI Backend (Port :8080)      │
│  ┌─────────────────────────────────┐ │
│  │ Session Manager + Routes         │ │
│  │ - Voice Transcription           │ │
│  │ - Evidence OCR                  │ │
│  │ - Document Generation            │ │
│  └─────────────────────────────────┘ │
└──────────────┬──────────────────────┘
               │
    ┌──────────┼──────────┬──────────┐
    │          │          │          │
    ▼          ▼          ▼          ▼
  Whisper    Surya/    Ollama    Local Vector
  (STT)     Tesseract (LLM)     Store (JSONL)
```

---

## 🔧 Development Commands

### **Run Tests**
```bash
python tests/run_tests.py
```

### **Run Backend Only**
```bash
python app/main.py
```

### **Run Frontend Only**
```bash
streamlit run ui/app.py
```

### **Check Python Version**
```bash
python --version
```

### **Check Installed Packages**
```bash
pip list
```

---

## 📝 File Structure

```
saathi/
├── app/
│   ├── main.py                 # FastAPI backend
│   ├── config.py               # Configuration
│   ├── models/                # Database + Pydantic
│   ├── services/              # STT, OCR, LLM, Vector, Document
│   ├── agents/                # Agent pipeline (Python)
│   ├── api/routes/            # API endpoints
│   └── utils/                 # Utilities
├── ui/
│   ├── app.py                 # Streamlit entry
│   ├── pages/                 # Workflow page(s)
│   └── components/            # Reusable components
├── tests/                     # Test suite
├── requirements.txt           # Dependencies
└── README_DEMO.md            # This file
```

---

## 🎉 Demo Tips

1. **Voice Recording**: Speak clearly in natural language
2. **Evidence**: Upload clear, well-lit photos
3. **Patience**: First-time model loading takes 10-30 seconds
4. **Review**: Always review generated documents with a lawyer

---

## 📞 Support

For issues:
1. Check console logs in both terminals
2. Verify Ollama is running: `ollama list`
3. Check API health: http://127.0.0.1:8080/health
4. Review this guide's troubleshooting section

---

## ⚠️ Disclaimer

This is a **hackathon demo**:
- Generated documents are **drafts**
- Should be reviewed by a **qualified lawyer**
- Not a substitute for **professional legal advice**
- For **educational purposes only**
