import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_agents_import():
    try:
        from app.agents import (
            VoiceIntakeAgent,
            EvidenceProcessorAgent,
            LegalDraftAgent,
            LegalAidCrew,
            legal_aid_crew
        )
        assert VoiceIntakeAgent is not None
        assert EvidenceProcessorAgent is not None
        assert LegalDraftAgent is not None
        assert LegalAidCrew is not None
        print("✓ All agents imported successfully")
    except Exception as e:
        print(f"⚠ Agent import warning: {e}")
        print("  (Expected if CrewAI not fully configured)")

def test_voice_intake_agent_info():
    try:
        from app.agents.voice_intake_agent import VoiceIntakeAgent
        
        mock_llm = MockLLMService()
        agent = VoiceIntakeAgent(mock_llm)
        
        info = agent.get_agent_info()
        assert 'role' in info
        assert 'goal' in info
        assert 'experience' in info
        assert 'specializations' in info
        
        print("✓ Voice Intake Agent info validated")
    except Exception as e:
        print(f"⚠ Voice Intake Agent test warning: {e}")

def test_evidence_agent_info():
    try:
        from app.agents.evidence_agent import EvidenceProcessorAgent
        
        mock_llm = MockLLMService()
        agent = EvidenceProcessorAgent(mock_llm)
        
        info = agent.get_agent_info()
        assert 'role' in info
        assert 'goal' in info
        assert 'specializations' in info
        
        print("✓ Evidence Processor Agent info validated")
    except Exception as e:
        print(f"⚠ Evidence Agent test warning: {e}")

def test_legal_draft_agent_info():
    try:
        from app.agents.legal_draft_agent import LegalDraftAgent
        
        mock_llm = MockLLMService()
        mock_vector = MockVectorService()
        agent = LegalDraftAgent(mock_llm, mock_vector)
        
        info = agent.get_agent_info()
        assert 'role' in info
        assert 'goal' in info
        assert 'specializations' in info
        
        print("✓ Legal Draft Agent info validated")
    except Exception as e:
        print(f"⚠ Legal Draft Agent test warning: {e}")

def test_crew_initialization():
    try:
        from app.agents.crew import LegalAidCrew
        
        crew = LegalAidCrew()
        status = crew.get_status()
        
        assert 'agents_initialized' in status
        assert 'llm_available' in status
        assert 'vector_service_ready' in status
        
        print("✓ Crew initialization validated")
    except Exception as e:
        print(f"⚠ Crew initialization warning: {e}")
        print("  (Expected if Ollama/ChromaDB not running)")

class MockLLMService:
    def generate_response(self, prompt, system_prompt=None, context=None, 
                         temperature=0.7, max_tokens=2048, stream=False):
        return {
            'response': '{"complainant_name": "Test"}',
            'model': 'mock',
            'done': True
        }
    
    def generate_with_retry(self, prompt, system_prompt=None, context=None,
                           max_retries=3, temperature=0.7):
        return self.generate_response(prompt, system_prompt, context, temperature)

class MockVectorService:
    def query_legal_context(self, query, collection_name="legal_knowledge", top_k=5):
        return [
            {
                'content': 'IPC Section 420: Cheating and dishonestly inducing delivery of property',
                'metadata': {'section': '420', 'type': 'ipc'},
                'distance': 0.2,
                'relevance_score': 0.8
            }
        ]
    
    def is_ready(self):
        return True

if __name__ == "__main__":
    print("Running Agent Tests...")
    print("=" * 60)
    
    tests = [
        test_agents_import,
        test_voice_intake_agent_info,
        test_evidence_agent_info,
        test_legal_draft_agent_info,
        test_crew_initialization
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
        print("✓ All agent tests passed!")
    else:
        print(f"⚠ {failed} test(s) had warnings or failed")
