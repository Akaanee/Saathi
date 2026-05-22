from .voice import router as voice_router
from .evidence import router as evidence_router
from .status import router as status_router
from .generate import router as generate_router

__all__ = [
    'voice_router',
    'evidence_router',
    'status_router',
    'generate_router'
]
