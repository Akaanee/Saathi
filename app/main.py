from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import logging
import sys
from pathlib import Path

from app.api.routes import voice_router, evidence_router, status_router, generate_router
from app.models.schemas import HealthResponse
from app.config import API_HOST, API_PORT, PATHS
from app.agents.crew import legal_aid_crew
from app.services import stt_service, ocr_service, llm_service, vector_service

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(PATHS['logs'] / 'app.log', mode='a')
    ]
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="SAATHI Legal Aid API",
    description="Voice-first multi-agent legal aid system for India's informal workers",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

app.include_router(voice_router)
app.include_router(evidence_router)
app.include_router(status_router)
app.include_router(generate_router)

@app.on_event("startup")
async def startup_event():
    logger.info("=" * 70)
    logger.info("SAATHI Legal Aid API - Starting Up")
    logger.info("=" * 70)
    
    PATHS['logs'].mkdir(parents=True, exist_ok=True)
    PATHS['outputs'].mkdir(parents=True, exist_ok=True)
    
    logger.info(f"STT Service: {'Ready' if stt_service.is_ready() else 'Not Ready'}")
    logger.info(f"OCR Service: {'Ready' if ocr_service.is_ready() else 'Not Ready'}")
    logger.info(f"LLM Service: {'Ready' if llm_service.is_ready() else 'Not Ready'}")
    logger.info(f"Vector Service: {'Ready' if vector_service.is_ready() else 'Not Ready'}")
    
    crew_status = legal_aid_crew.get_status()
    logger.info(f"Crew Agents: {'Ready' if crew_status['agents_initialized'] else 'Not Ready'}")
    
    logger.info("=" * 70)
    logger.info(f"API Documentation: http://{API_HOST}:{API_PORT}/docs")
    logger.info(f"ReDoc Documentation: http://{API_HOST}:{API_PORT}/redoc")
    logger.info("=" * 70)

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("SAATHI Legal Aid API - Shutting Down")
    
    from app.utils.session_manager import session_manager
    session_manager.close()

@app.get("/", tags=["Root"])
async def root():
    return {
        "name": "SAATHI Legal Aid API",
        "version": "1.0.0",
        "description": "Voice-first multi-agent legal aid system for India's informal workers",
        "endpoints": {
            "voice": "/api/voice",
            "evidence": "/api/evidence",
            "status": "/api/status",
            "generate": "/api/generate",
            "health": "/health",
            "docs": "/docs"
        }
    }

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    return HealthResponse(
        status="healthy",
        ollama_connected=llm_service.is_ready(),
        whisper_loaded=stt_service.is_ready(),
        chromadb_ready=vector_service.is_ready()
    )

@app.get("/info", tags=["Info"])
async def get_info():
    return {
        "supported_languages": ["hi", "bn", "ta", "en"],
        "supported_evidence_formats": ["jpg", "jpeg", "png", "webp"],
        "max_audio_duration_seconds": 30,
        "max_audio_size_mb": 10,
        "max_evidence_files": 10,
        "output_formats": ["docx", "pdf", "txt"],
        "features": [
            "Voice transcription in Hindi, Bengali, Tamil",
            "OCR for evidence documents",
            "Legal notice generation",
            "Case summary generation",
            "Multi-agent AI processing"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting server on {API_HOST}:{API_PORT}")
    
    uvicorn.run(
        "app.main:app",
        host=API_HOST,
        port=API_PORT,
        reload=False,
        log_level="info"
    )
