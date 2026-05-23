import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b-instruct-q4_K_M")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "tiny")
WHISPER_MODEL_DIR = Path(os.getenv("WHISPER_MODEL_DIR", str(BASE_DIR / "models" / "whisper")))

CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", str(BASE_DIR / "knowledge_base" / "chroma_db"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

MAX_AUDIO_DURATION = int(os.getenv("MAX_AUDIO_DURATION", "30"))
MAX_IMAGE_SIZE = int(os.getenv("MAX_IMAGE_SIZE", str(10 * 1024 * 1024)))
SUPPORTED_LANGUAGES = os.getenv("SUPPORTED_LANGUAGES", "hi,bn,ta,en").split(",")
SESSION_TIMEOUT = int(os.getenv("SESSION_TIMEOUT", "3600"))

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", str(BASE_DIR / "outputs")))
LOG_FILE = Path(os.getenv("LOG_FILE", str(BASE_DIR / "logs" / "app.log")))

API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "8080"))
UI_PORT = int(os.getenv("UI_PORT", "8501"))

LANGUAGE_NAMES = {
    "hi": "Hindi",
    "bn": "Bengali",
    "ta": "Tamil",
    "en": "English"
}

MEMORY_LIMITS = {
    "max_concurrent_sessions": 2,
    "model_load_timeout": 60,
    "agent_idle_timeout": 300,
    "max_audio_size_mb": 10
}

PATHS = {
    "base": BASE_DIR,
    "app": BASE_DIR / "app",
    "ui": BASE_DIR / "ui",
    "knowledge_base": BASE_DIR / "knowledge_base",
    "legal_docs": BASE_DIR / "knowledge_base" / "legal_docs",
    "templates": BASE_DIR / "knowledge_base" / "legal_docs" / "templates",
    "embeddings": BASE_DIR / "knowledge_base" / "embeddings",
    "outputs": OUTPUT_DIR,
    "logs": BASE_DIR / "logs",
    "models": BASE_DIR / "models",
    "whisper_models": WHISPER_MODEL_DIR
}

for path_key, path_value in PATHS.items():
    if isinstance(path_value, Path):
        path_value.mkdir(parents=True, exist_ok=True)
