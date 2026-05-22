import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_imports():
    try:
        from app.config import BASE_DIR, OLLAMA_HOST, SUPPORTED_LANGUAGES
        assert BASE_DIR.exists()
        assert OLLAMA_HOST == "http://127.0.0.1:11434"
        assert "hi" in SUPPORTED_LANGUAGES
        assert "bn" in SUPPORTED_LANGUAGES
        assert "ta" in SUPPORTED_LANGUAGES
        print("[PASS] Configuration imports successful")
    except Exception as e:
        raise Exception(f"Configuration import failed: {e}")

def test_database_models():
    try:
        from app.models.database import Session, ProcessingLog, SessionStatus
        assert Session is not None
        assert ProcessingLog is not None
        assert SessionStatus is not None
        assert SessionStatus.PENDING.value == "pending"
        print("[PASS] Database models import successful")
    except Exception as e:
        raise Exception(f"Database models import failed: {e}")

def test_pydantic_schemas():
    try:
        from app.models.schemas import (
            VoiceInput, VoiceResponse, EvidenceInput, EvidenceResponse,
            StatusResponse, SessionStatus, TranscriptionResult
        )
        assert VoiceInput is not None
        assert VoiceResponse is not None
        print("[PASS] Pydantic schemas import successful")
    except Exception as e:
        raise Exception(f"Pydantic schemas import failed: {e}")

def test_config_paths():
    try:
        from app.config import PATHS
        required_paths = ['base', 'app', 'ui', 'knowledge_base', 'outputs', 'logs']
        for path_key in required_paths:
            assert path_key in PATHS
            assert PATHS[path_key] is not None
        print("[PASS] Configuration paths verified")
    except Exception as e:
        raise Exception(f"Configuration paths failed: {e}")

def test_language_config():
    try:
        from app.config import LANGUAGE_NAMES
        assert LANGUAGE_NAMES['hi'] == "Hindi"
        assert LANGUAGE_NAMES['bn'] == "Bengali"
        assert LANGUAGE_NAMES['ta'] == "Tamil"
        print("[PASS] Language configuration verified")
    except Exception as e:
        raise Exception(f"Language config failed: {e}")

def test_memory_limits():
    try:
        from app.config import MEMORY_LIMITS
        assert MEMORY_LIMITS['max_concurrent_sessions'] == 2
        assert MEMORY_LIMITS['agent_idle_timeout'] == 300
        print("[PASS] Memory limits configured correctly")
    except Exception as e:
        raise Exception(f"Memory limits check failed: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("Running Configuration Tests...")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_database_models,
        test_pydantic_schemas,
        test_config_paths,
        test_language_config,
        test_memory_limits
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            failed += 1
    
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("SUCCESS: All configuration tests passed!")
    else:
        print(f"FAILURE: {failed} test(s) failed")
        sys.exit(1)
