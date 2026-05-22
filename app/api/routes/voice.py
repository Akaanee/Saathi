from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional
import logging
import io

from app.models.schemas import VoiceResponse, ErrorResponse
from app.utils.session_manager import session_manager
from app.services.stt_service import stt_service
from app.config import MAX_AUDIO_DURATION, SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["Voice"])

@router.post("", response_model=VoiceResponse)
async def transcribe_voice(
    audio: UploadFile = File(..., description="Audio file (WAV, WebM, MP3)"),
    language: Optional[str] = Form(None, description="Language code: hi, bn, ta, or auto"),
    session_id: Optional[str] = Form(None, description="Existing session ID or create new")
):
    try:
        logger.info(f"Received voice upload: {audio.filename}, language={language}")
        
        if language and language not in SUPPORTED_LANGUAGES + ["auto"]:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported language. Choose from: {', '.join(SUPPORTED_LANGUAGES)}, or 'auto'"
            )
        
        if not session_id:
            session_id = session_manager.create_session(language=language)
        else:
            session = session_manager.get_session(session_id)
            if not session:
                session_id = session_manager.create_session(language=language)
        
        audio_data = await audio.read()
        
        audio_size_mb = len(audio_data) / (1024 * 1024)
        if audio_size_mb > 10:
            raise HTTPException(
                status_code=400,
                detail=f"Audio file too large ({audio_size_mb:.1f}MB). Maximum is 10MB."
            )
        
        logger.info(f"Processing audio ({audio_size_mb:.1f}MB) for session {session_id}")
        
        detected_lang = language
        if language == "auto" or not language:
            try:
                lang_result = stt_service.detect_language(audio_data)
                detected_lang = lang_result.get('detected_language', 'hi')
                logger.info(f"Detected language: {detected_lang}")
            except Exception as e:
                logger.warning(f"Language detection failed: {e}, defaulting to Hindi")
                detected_lang = 'hi'
        
        transcription_result = stt_service.transcribe_audio(
            audio_data=audio_data,
            language=detected_lang if detected_lang != "auto" else None
        )
        
        transcription = transcription_result.get('text', '')
        confidence = transcription_result.get('confidence', 0.0)
        
        if not transcription or len(transcription.strip()) < 10:
            logger.warning("Transcription too short or empty")
            raise HTTPException(
                status_code=400,
                detail="Audio unclear or too short. Please try recording again with a clearer voice."
            )
        
        session_manager.add_transcription(session_id, transcription, detected_lang)
        
        logger.info(f"Transcription complete: {len(transcription)} characters, confidence={confidence:.2f}")
        
        return VoiceResponse(
            session_id=session_id,
            transcription=transcription,
            language=detected_lang,
            confidence=confidence
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voice transcription error: {e}", exc_info=True)
        if 'session_id' in locals():
            session_manager.set_error(session_id, str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Transcription failed: {str(e)}"
        )

@router.get("/languages")
async def get_supported_languages():
    return {
        "languages": [
            {"code": "hi", "name": "Hindi", "native": "हिंदी"},
            {"code": "bn", "name": "Bengali", "native": "বাংলা"},
            {"code": "ta", "name": "Tamil", "native": "தமிழ்"},
            {"code": "en", "name": "English", "native": "English"}
        ],
        "default": "hi"
    }
