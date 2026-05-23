import os
import io
import logging
from typing import Dict, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)

class STTService:
    def __init__(self):
        self.model = None
        self.model_loaded = False
        self.model_name = None
        self.provider = None
        self._initialize()

    def _initialize(self):
        try:
            from faster_whisper import WhisperModel
            
            model_size = os.getenv("WHISPER_MODEL", "tiny")
            compute_type = "int8" if model_size.startswith("tiny") else "float16"
            
            logger.info(f"Loading Whisper model: {model_size} with compute type: {compute_type}")
            
            self.model = WhisperModel(
                model_size,
                device="cpu",
                compute_type=compute_type
            )
            
            self.model_loaded = True
            self.model_name = model_size
            self.provider = "faster-whisper"
            logger.info(f"Whisper model loaded successfully: {model_size}")
            
        except ImportError:
            logger.warning("faster-whisper not available, will try openai-whisper")
            try:
                import whisper
                self.model = whisper.load_model("tiny")
                self.model_loaded = True
                self.model_name = "tiny"
                self.provider = "openai-whisper"
                logger.info("OpenAI Whisper tiny model loaded successfully")
            except ImportError:
                logger.error("No Whisper implementation available. Install faster-whisper or openai-whisper")
                self.model = None
                self.model_loaded = False
                self.provider = None

    def transcribe_audio(
        self, 
        audio_data: bytes, 
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        if not self.model_loaded or self.model is None:
            raise RuntimeError("Whisper model not loaded")

        try:
            audio_array = self._prepare_audio(audio_data)
            
            if self.provider == "openai-whisper":
                result = self.model.transcribe(
                    audio_array,
                    language=language,
                    task="transcribe",
                    beam_size=5,
                    vad_filter=True
                )
                
                segments = list(result.get('segments', []))
                
                return {
                    "text": result.get('text', '').strip(),
                    "language": result.get('language', language or 'en'),
                    "confidence": self._calculate_confidence(segments),
                    "segments": [
                        {
                            "start": seg.get('start', 0),
                            "end": seg.get('end', 0),
                            "text": seg.get('text', '').strip()
                        }
                        for seg in segments
                    ]
                }
            elif self.provider == "faster-whisper":
                segments, info = self.model.transcribe(
                    audio_array,
                    language=language,
                    beam_size=5,
                    vad_filter=True
                )
                
                segment_list = list(segments)
                full_text = " ".join([seg.text for seg in segment_list])
                
                return {
                    "text": full_text.strip(),
                    "language": info.language if hasattr(info, 'language') else language or 'en',
                    "confidence": info.language_probability if hasattr(info, 'language_probability') else 0.9,
                    "segments": [
                        {
                            "start": seg.start,
                            "end": seg.end,
                            "text": seg.text.strip()
                        }
                        for seg in segment_list
                    ]
                }
            else:
                raise RuntimeError("Whisper model provider not recognized")

        except Exception as e:
            logger.error(f"Transcription error: {str(e)}")
            raise RuntimeError(f"Failed to transcribe audio: {str(e)}")

    def _prepare_audio(self, audio_data: bytes) -> np.ndarray:
        try:
            import torch
            import torchaudio
            
            audio_tensor, sample_rate = torchaudio.load(io.BytesIO(audio_data))
            
            if audio_tensor.shape[0] > 1:
                audio_tensor = torch.mean(audio_tensor, dim=0, keepdim=True)
            
            if sample_rate != 16000:
                resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=16000)
                audio_tensor = resampler(audio_tensor)
            
            audio_np = audio_tensor.squeeze().detach().cpu().numpy()
            audio_np = np.ascontiguousarray(audio_np.astype(np.float32, copy=False))
            return audio_np
            
        except ImportError:
            try:
                import soundfile as sf
                audio_np, sr = sf.read(io.BytesIO(audio_data), dtype="float32")
                
                if len(audio_np.shape) > 1:
                    audio_np = np.mean(audio_np, axis=1)
                
                if sr != 16000:
                    import librosa
                    audio_np = librosa.resample(audio_np, orig_sr=sr, target_sr=16000)
                audio_np = np.ascontiguousarray(np.asarray(audio_np, dtype=np.float32))
                return audio_np
                
            except ImportError:
                raise RuntimeError(
                    "Audio processing requires torchaudio or soundfile+librosa. "
                    "Install with: pip install torchaudio soundfile librosa"
                )

    def _calculate_confidence(self, segments: list) -> float:
        if not segments:
            return 0.0
        
        total_words = 0
        weighted_confidence = 0.0
        
        for seg in segments:
            if isinstance(seg, dict):
                avg_logprob = seg.get('avgLogProb', -0.5)
                no_speech_prob = seg.get('noSpeechProb', 0.1)
            else:
                avg_logprob = getattr(seg, 'avg_logprob', -0.5)
                no_speech_prob = getattr(seg, 'no_speech_prob', 0.1)
            
            confidence = np.exp(avg_logprob) * (1 - no_speech_prob)
            
            words = len(seg.get('text', '').split()) if isinstance(seg, dict) else len(seg.text.split())
            weighted_confidence += confidence * words
            total_words += words
        
        return weighted_confidence / total_words if total_words > 0 else 0.0

    def detect_language(self, audio_data: bytes) -> Dict[str, Any]:
        if not self.model_loaded or self.model is None:
            raise RuntimeError("Whisper model not loaded")

        try:
            audio_array = self._prepare_audio(audio_data)
            
            if self.provider == "openai-whisper":
                result = self.model.transcribe(audio_array, task="translate")
                detected_lang = result.get('language', 'unknown')
                lang_prob = 0.9
            elif self.provider == "faster-whisper":
                _, info = self.model.transcribe(audio_array, vad_filter=True)
                detected_lang = info.language
                lang_prob = info.language_probability
            else:
                raise RuntimeError("Whisper model provider not recognized")
            
            supported_langs = {
                'hi': 'Hindi',
                'bn': 'Bengali', 
                'ta': 'Tamil',
                'en': 'English'
            }
            
            return {
                "detected_language": detected_lang,
                "language_name": supported_langs.get(detected_lang, 'Unknown'),
                "confidence": lang_prob
            }
            
        except Exception as e:
            logger.error(f"Language detection error: {str(e)}")
            return {
                "detected_language": "unknown",
                "language_name": "Unknown",
                "confidence": 0.0
            }

    def is_ready(self) -> bool:
        return self.model_loaded and self.model is not None

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "loaded": self.model_loaded,
            "model_name": self.model_name,
            "provider": self.provider
        }


stt_service = STTService()
