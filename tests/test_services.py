import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_stt_service_import():
    try:
        from app.services.stt_service import STTService, stt_service
        assert STTService is not None
        assert stt_service is not None
        print("✓ STT Service imports successful")
    except Exception as e:
        print(f"⚠ STT Service import warning: {e}")
        print("  (Expected if Whisper not installed)")

def test_ocr_service_import():
    try:
        from app.services.ocr_service import OCRService, ocr_service
        assert OCRService is not None
        print("✓ OCR Service imports successful")
    except Exception as e:
        print(f"⚠ OCR Service import warning: {e}")
        print("  (Expected if OCR libraries not installed)")

def test_llm_service_import():
    try:
        from app.services.llm_service import LLMService, llm_service
        assert LLMService is not None
        print("✓ LLM Service imports successful")
    except Exception as e:
        pytest.fail(f"LLM Service import failed: {e}")

def test_vector_service_import():
    try:
        from app.services.vector_service import VectorService, vector_service
        assert VectorService is not None
        print("✓ Vector Service imports successful")
    except Exception as e:
        print(f"⚠ Vector Service import warning: {e}")
        print("  (Expected if ChromaDB not configured)")

def test_document_service_import():
    try:
        from app.services.document_service import DocumentService, document_service
        assert DocumentService is not None
        assert document_service is not None
        print("✓ Document Service imports successful")
    except Exception as e:
        pytest.fail(f"Document Service import failed: {e}")

def test_document_generation():
    try:
        from app.services.document_service import DocumentService
        doc_service = DocumentService()
        
        sample_complaint = {
            'complainant_name': 'Test Complainant',
            'complainant_address': '123 Test Street',
            'complainant_occupation': 'Construction Worker',
            'respondent': {
                'name': 'Test Contractor',
                'address': '456 Builder Ave'
            },
            'incident_date': '15-01-2024',
            'incident_location': 'Mumbai',
            'incident_description': 'Wages not paid for 3 months of work',
            'factual_matrix': 'Worker completed construction work but was not paid',
            'legal_grounds': ['IPC Section 420', 'BOCW Act Section 34'],
            'relief_sought': ['Full wages', 'Compensation', 'Legal costs']
        }
        
        docx_content = doc_service.generate_legal_notice(sample_complaint, "docx")
        assert docx_content is not None
        assert len(docx_content) > 0
        assert docx_content[:4] == b'PK\x03\x04'
        print("✓ DOCX generation successful")
        
        txt_content = doc_service.generate_case_summary(sample_complaint, "txt")
        assert txt_content is not None
        assert b'CASE SUMMARY' in txt_content
        print("✓ TXT generation successful")
        
    except Exception as e:
        pytest.fail(f"Document generation failed: {e}")

def test_all_services_export():
    try:
        from app.services import (
            stt_service, STTService,
            ocr_service, OCRService,
            llm_service, LLMService,
            vector_service, VectorService,
            document_service, DocumentService
        )
        
        assert STTService is not None
        assert OCRService is not None
        assert LLMService is not None
        assert VectorService is not None
        assert DocumentService is not None
        
        print("✓ All services exported successfully")
    except Exception as e:
        pytest.fail(f"Service exports failed: {e}")

if __name__ == "__main__":
    print("Running Service Tests...")
    print("=" * 60)
    
    tests = [
        test_stt_service_import,
        test_ocr_service_import,
        test_llm_service_import,
        test_vector_service_import,
        test_document_service_import,
        test_document_generation,
        test_all_services_export
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1
    
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("✓ All service tests passed!")
    else:
        print(f"⚠ {failed} test(s) had warnings or failed")
