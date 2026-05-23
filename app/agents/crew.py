from typing import Dict, Any, List, Optional
import logging
import time

from app.services import llm_service, vector_service
from app.agents.voice_intake_agent import VoiceIntakeAgent
from app.agents.evidence_agent import EvidenceProcessorAgent
from app.agents.legal_draft_agent import LegalDraftAgent

logger = logging.getLogger(__name__)

class LegalAidCrew:
    def __init__(self):
        self.llm = llm_service
        self.voice_intake_agent = None
        self.evidence_agent = None
        self.legal_draft_agent = None
        self.crew = None
        self._initialize_agents()

    def _initialize_agents(self):
        logger.info("Initializing CrewAI agents...")

        self.voice_intake_agent = VoiceIntakeAgent(self.llm)
        self.evidence_agent = EvidenceProcessorAgent(self.llm)
        self.legal_draft_agent = LegalDraftAgent(self.llm, vector_service)
        
        logger.info("All agents initialized successfully")

    def process_complaint(
        self,
        transcription: str,
        language: str,
        ocr_results: List[Dict[str, Any]],
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        logger.info("Starting complaint processing pipeline")
        start_time = time.time()
        
        try:
            if progress_callback:
                progress_callback("voice_intake", 0, "Starting voice intake processing...")
            
            complaint_data = self.voice_intake_agent.process_transcription(
                transcription=transcription,
                language=language
            )

            if isinstance(complaint_data, dict):
                complaint_data["_raw_transcription"] = transcription
            
            validation = self.voice_intake_agent.validate_complaint(complaint_data)
            complaint_data['_validation'] = validation
            
            if progress_callback:
                progress_callback("voice_intake", 100, "Voice intake complete")
                progress_callback("evidence", 0, "Processing evidence...")
            
            evidence_analysis = self._process_evidence(ocr_results, complaint_data)
            
            if progress_callback:
                progress_callback("evidence", 100, "Evidence analysis complete")
                progress_callback("legal_context", 0, "Querying legal knowledge base...")
            
            legal_context = self._get_legal_context(complaint_data)
            
            if progress_callback:
                progress_callback("legal_context", 100, "Legal context retrieved")
                progress_callback("drafting", 0, "Generating legal documents...")
            
            legal_notice = self.legal_draft_agent.generate_legal_notice(
                complaint_data=complaint_data,
                evidence_analysis=evidence_analysis,
                legal_context=legal_context
            )
            
            case_summary = self.legal_draft_agent.generate_case_summary(
                complaint_data=complaint_data,
                evidence_analysis=evidence_analysis,
                legal_context=legal_context
            )
            
            if progress_callback:
                progress_callback("drafting", 100, "Document generation complete")
            
            elapsed_time = time.time() - start_time
            logger.info(f"Complaint processing completed in {elapsed_time:.2f} seconds")
            
            return {
                "success": True,
                "complaint_data": complaint_data,
                "evidence_analysis": evidence_analysis,
                "legal_notice": legal_notice,
                "case_summary": case_summary,
                "processing_time": elapsed_time,
                "status": "complete"
            }
            
        except Exception as e:
            logger.error(f"Error in complaint processing pipeline: {e}")
            return {
                "success": False,
                "error": str(e),
                "status": "error"
            }

    def _process_evidence(
        self,
        ocr_results: List[Dict[str, Any]],
        complaint_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        if not ocr_results:
            logger.info("No evidence to process")
            return {
                "total_evidence_items": 0,
                "evidence_analysis": [],
                "overall_evidence_quality": "none",
                "consistency_check": {
                    "is_consistent": True,
                    "contradictions": [],
                    "supporting_evidence": []
                },
                "recommended_additional_evidence": [
                    "Wage slips",
                    "Employment contract",
                    "Bank statements",
                    "Photographs",
                    "Witness statements"
                ],
                "case_building_notes": "No evidence uploaded - verbal complaint only"
            }
        
        return self.evidence_agent.process_evidence(
            ocr_results=ocr_results,
            complaint_data=complaint_data
        )

    def _get_legal_context(
        self,
        complaint_data: Dict[str, Any],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        incident_description = complaint_data.get('incident_description') or ''
        relief_sought = complaint_data.get('relief_sought')
        applicable_laws = complaint_data.get('applicable_laws')

        if not isinstance(relief_sought, list):
            relief_sought = []
        if not isinstance(applicable_laws, list):
            applicable_laws = []

        query_parts = [
            str(incident_description),
            ' '.join([str(x) for x in relief_sought if x]),
            ' '.join([str(x) for x in applicable_laws if x])
        ]
        
        query = ' '.join([q for q in query_parts if q])[:500]
        
        if not query.strip():
            query = "labor law wage theft worker rights"
        
        try:
            legal_context = self.legal_draft_agent.query_legal_context(
                query=query,
                top_k=top_k
            )
            
            if not legal_context:
                logger.warning("No legal context found in knowledge base")
                return []
            
            return legal_context
            
        except Exception as e:
            logger.error(f"Error retrieving legal context: {e}")
            return []

    def create_crew_workflow(self) -> Any:
        try:
            from crewai import Crew, Task
            from crewai.process import Process
        except Exception as e:
            raise RuntimeError(f"CrewAI is not available: {e}")

        voice_intake_task = Task(
            description="Process voice transcription and extract structured complaint data",
            agent=self.voice_intake_agent.agent,
            expected_output="Structured JSON complaint data with all fields populated"
        )
        
        evidence_task = Task(
            description="Analyze uploaded evidence documents for consistency with complaint",
            agent=self.evidence_agent.agent,
            expected_output="Evidence analysis with relevance scores and consistency checks"
        )
        
        legal_draft_task = Task(
            description="Generate legal notice and case summary using knowledge base",
            agent=self.legal_draft_agent.agent,
            expected_output="Formatted legal notice and case summary documents",
            context=[voice_intake_task, evidence_task]
        )
        
        self.crew = Crew(
            agents=[
                self.voice_intake_agent.agent,
                self.evidence_agent.agent,
                self.legal_draft_agent.agent
            ],
            tasks=[
                voice_intake_task,
                evidence_task,
                legal_draft_task
            ],
            process=Process.sequential,
            manager_cls=None,
            verbose=2
        )
        
        logger.info("Crew workflow created")
        return self.crew

    def get_status(self) -> Dict[str, Any]:
        return {
            "agents_initialized": all([
                self.voice_intake_agent,
                self.evidence_agent,
                self.legal_draft_agent
            ]),
            "llm_available": llm_service.is_ready(),
            "vector_service_ready": vector_service.is_ready(),
            "crew_ready": self.crew is not None
        }

    def health_check(self) -> Dict[str, Any]:
        return {
            "overall_status": "healthy" if llm_service.is_ready() else "degraded",
            "llm_service": llm_service.check_model_status(),
            "vector_service": {
                "ready": vector_service.is_ready(),
                "collections": list(vector_service.collections.keys()) if vector_service.collections else []
            },
            "crew_status": self.get_status()
        }


legal_aid_crew = LegalAidCrew()
