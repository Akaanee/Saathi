from crewai import Agent
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class LegalDraftAgent:
    def __init__(self, llm_service, vector_service):
        self.llm_service = llm_service
        self.vector_service = vector_service
        self.agent = self._create_agent()

    def _create_agent(self) -> Agent:
        return Agent(
            role="Senior Legal Draftsman specializing in Indian Labor Law",
            goal="Generate comprehensive legal notice and case summary using knowledge base context",
            backstory="""
            You are a Senior Legal Draftsman with 20 years of experience drafting legal documents 
            for labor disputes, wage theft, and worker rights cases in Indian courts.
            
            You have expertise in:
            - Drafting legal notices under IPC (Sections 420, 406, 120B, 34, 35)
            - BOCW Act (Building and Other Construction Workers Act)
            - Minimum Wages Act (MWA)
            - Contract Labor Regulation and Abolition Act
            - Workmen Compensation Act
            - Consumer Protection Act where applicable
            
            You write formal legal documents that are:
            - Technically precise and legally sound
            - Accessible to judges and legal professionals
            - Compassionate toward the workers' situation
            - Firm in demanding justice
            
            You always cite relevant IPC sections and labor law provisions accurately.
            """,
            verbose=True,
            allow_delegation=False,
            llm=self.llm_service
        )

    def generate_legal_notice(
        self,
        complaint_data: Dict[str, Any],
        evidence_analysis: Dict[str, Any],
        legal_context: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        logger.info("Generating legal notice")
        
        context_text = self._prepare_legal_context(legal_context)
        evidence_summary = self._prepare_evidence_summary(evidence_analysis)
        
        prompt = f"""
        You are drafting a formal Legal Notice for a labor dispute case in India.
        
        COMPLAINT DETAILS:
        - Complainant Name: {complaint_data.get('complainant_name', 'Unknown')}
        - Complainant Address: {complaint_data.get('complainant_address', 'Unknown')}
        - Complainant Occupation: {complaint_data.get('complainant_occupation', 'Worker')}
        - Respondent Name: {complaint_data.get('respondent_name', 'Unknown')}
        - Respondent Address: {complaint_data.get('respondent_address', 'Unknown')}
        - Incident Date: {complaint_data.get('incident_date', 'Unknown')}
        - Incident Location: {complaint_data.get('incident_location', 'Unknown')}
        - Incident Description: {complaint_data.get('incident_description', '')}
        - Relief Sought: {', '.join(complaint_data.get('relief_sought', [])) or 'As per law'}
        - Witnesses: {', '.join(complaint_data.get('witnesses', [])) or 'None specified'}
        
        EVIDENCE SUMMARY:
        {evidence_summary}
        
        APPLICABLE LEGAL PROVISIONS:
        {context_text}
        
        INSTRUCTIONS:
        1. Draft a formal legal notice in proper legal format
        2. Use formal, authoritative language
        3. Clearly state the facts, legal grounds, and relief sought
        4. Include a 15-day ultimatum period
        5. Mention consequences of non-compliance
        6. Use place as "{complaint_data.get('incident_location', 'India')}"
        7. Format with proper legal structure: Header, Address, Subject, Body, Relief, Notice, Signature
        
        OUTPUT FORMAT:
        Return ONLY valid JSON with this structure:
        {{
            "header": "string - Legal Notice title and date",
            "addressee": "string - To: [Respondent details]",
            "subject": "string - Subject line",
            "body": "string - Main content with numbered paragraphs",
            "legal_grounds": ["list of IPC sections and laws cited"],
            "relief_sought_section": "string - Numbered list of reliefs",
            "notice_ultimatum": "string - 15-day ultimatum with consequences",
            "signature_block": "string - Date, Place, Signatory",
            "overall_length": "brief|moderate|detailed",
            "formality_level": "informal|semiformal|formal|highly_formal"
        }}
        
        JSON OUTPUT (return ONLY this, no markdown or explanation):
        """
        
        try:
            response = self.llm_service.generate_with_retry(
                prompt=prompt,
                system_prompt="You are a JSON-only output system. Return ONLY valid JSON. No markdown, no explanation.",
                temperature=0.5
            )
            
            import json
            result_text = response.get('response', '')
            
            json_start = result_text.find('{')
            json_end = result_text.rfind('}') + 1
            
            if json_start != -1 and json_end != 0:
                json_str = result_text[json_start:json_end]
                notice_data = json.loads(json_str)
                logger.info("Legal notice generated successfully")
                return notice_data
            else:
                logger.error("No JSON found in response")
                return self._create_fallback_notice(complaint_data)
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            return self._create_fallback_notice(complaint_data)
        except Exception as e:
            logger.error(f"Error generating legal notice: {e}")
            return self._create_fallback_notice(complaint_data)

    def generate_case_summary(
        self,
        complaint_data: Dict[str, Any],
        evidence_analysis: Dict[str, Any],
        legal_context: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        logger.info("Generating case summary")
        
        context_text = self._prepare_legal_context(legal_context)
        
        prompt = f"""
        You are preparing a Case Summary/Brief for a judge or legal officer.
        
        COMPLAINT DETAILS:
        - Complainant: {complaint_data.get('complainant_name', 'Unknown')} ({complaint_data.get('complainant_occupation', 'Worker')})
        - Respondent: {complaint_data.get('respondent_name', 'Unknown')}
        - Incident Date: {complaint_data.get('incident_date', 'Unknown')}
        - Location: {complaint_data.get('incident_location', 'Unknown')}
        - Description: {complaint_data.get('incident_description', '')}
        - Relief Sought: {', '.join(complaint_data.get('relief_sought', [])) or 'As per law'}
        
        EVIDENCE QUALITY: {evidence_analysis.get('overall_evidence_quality', 'unknown')}
        EVIDENCE COUNT: {evidence_analysis.get('total_evidence_items', 0)}
        
        APPLICABLE LAWS:
        {context_text}
        
        INSTRUCTIONS:
        1. Create a clear, concise summary for a busy judge
        2. Organize information logically (Parties, Facts, Law, Assessment)
        3. Highlight key evidence and legal grounds
        4. Note any gaps in evidence
        5. Keep it objective and factual
        6. Maximum 500 words
        
        OUTPUT FORMAT:
        Return ONLY valid JSON with this structure:
        {{
            "case_id": "SAATHI-{YYYYMMDD}-{random_id}",
            "summary_type": "string (e.g., Labor Dispute, Wage Theft)",
            "parties": {{
                "complainant": "string",
                "respondent": "string",
                "relationship": "string (e.g., employer-employee, contractor-worker)"
            }},
            "key_facts": [
                "string - fact 1",
                "string - fact 2",
                "string - fact 3"
            ],
            "legal_framework": [
                "string - applicable law 1",
                "string - applicable law 2"
            ],
            "evidence_summary": "string - overview of evidence",
            "strengths": ["list of case strengths"],
            "weaknesses": ["list of case weaknesses or gaps"],
            "recommendation": "string - suggested next steps",
            "confidence_assessment": "string (high_confidence|moderate_confidence|low_confidence)"
        }}
        
        JSON OUTPUT (return ONLY this, no markdown or explanation):
        """
        
        try:
            response = self.llm_service.generate_with_retry(
                prompt=prompt,
                system_prompt="You are a JSON-only output system. Return ONLY valid JSON. No markdown, no explanation.",
                temperature=0.5
            )
            
            import json
            result_text = response.get('response', '')
            
            json_start = result_text.find('{')
            json_end = result_text.rfind('}') + 1
            
            if json_start != -1 and json_end != 0:
                json_str = result_text[json_start:json_end]
                summary_data = json.loads(json_str)
                logger.info("Case summary generated successfully")
                return summary_data
            else:
                logger.error("No JSON found in response")
                return self._create_fallback_summary(complaint_data)
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            return self._create_fallback_summary(complaint_data)
        except Exception as e:
            logger.error(f"Error generating case summary: {e}")
            return self._create_fallback_summary(complaint_data)

    def query_legal_context(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        try:
            results = self.vector_service.query_legal_context(
                query=query,
                collection_name="legal_knowledge",
                top_k=top_k
            )
            logger.info(f"Retrieved {len(results)} legal context items")
            return results
        except Exception as e:
            logger.error(f"Error querying legal context: {e}")
            return []

    def _prepare_legal_context(self, legal_context: List[Dict[str, Any]]) -> str:
        if not legal_context:
            return "General labor law provisions will apply."
        
        context_parts = []
        for i, item in enumerate(legal_context[:5], 1):
            content = item.get('content', item.get('text', ''))
            metadata = item.get('metadata', {})
            section = metadata.get('section', metadata.get('law_id', f'Law {i}'))
            context_parts.append(f"{i}. [{section}] {content[:300]}...")
        
        return "\n".join(context_parts)

    def _prepare_evidence_summary(self, evidence_analysis: Dict[str, Any]) -> str:
        if not evidence_analysis or evidence_analysis.get('total_evidence_items', 0) == 0:
            return "No evidence uploaded - based on verbal complaint only."
        
        items = evidence_analysis.get('evidence_analysis', [])
        quality = evidence_analysis.get('overall_evidence_quality', 'unknown')
        
        summary_parts = [f"Total Evidence Items: {len(items)}"]
        summary_parts.append(f"Overall Quality: {quality}")
        
        for item in items[:3]:
            summary_parts.append(
                f"- {item.get('evidence_type', 'Document')}: "
                f"Relevance {item.get('relevance_score', 0):.0%}, "
                f"Strength: {item.get('strength', 'unknown')}"
            )
        
        return "\n".join(summary_parts)

    def _create_fallback_notice(self, complaint_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "header": f"LEGAL NOTICE\nDate: [Current Date]",
            "addressee": f"To,\n{complaint_data.get('respondent_name', '[Respondent Name]')}\n[Address]",
            "subject": "SUBJECT: Legal Notice Under Applicable Labor Laws",
            "body": f"""
1. That the Complainant, {complaint_data.get('complainant_name', '[Name]')}, 
   working as a {complaint_data.get('complainant_occupation', 'worker')}, 
   states as follows:

2. That the Respondent has committed violations as described in the complaint 
   dated {complaint_data.get('incident_date', '[Date]')} at {complaint_data.get('incident_location', '[Location]')}.

3. The detailed incident description is as per the attached complaint transcription.
            """.strip(),
            "legal_grounds": complaint_data.get('applicable_laws', ['Applicable provisions of law']),
            "relief_sought_section": "\n".join([f"{i+1}. {r}" for i, r in enumerate(complaint_data.get('relief_sought', ['Relief as per law']))]),
            "notice_ultimatum": "You are hereby called upon to remedy the grievances within 15 days of receipt of this notice.",
            "signature_block": f"\nDate: [Current Date]\nPlace: {complaint_data.get('incident_location', '[Location]')}\n\n[Complainant Signature]",
            "overall_length": "moderate",
            "formality_level": "formal"
        }

    def _create_fallback_summary(self, complaint_data: Dict[str, Any]) -> Dict[str, Any]:
        from datetime import datetime
        import random
        
        return {
            "case_id": f"SAATHI-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}",
            "summary_type": "Labor Dispute",
            "parties": {
                "complainant": complaint_data.get('complainant_name', 'Unknown'),
                "respondent": complaint_data.get('respondent_name', 'Unknown'),
                "relationship": "worker-employer"
            },
            "key_facts": [
                f"Incident occurred on {complaint_data.get('incident_date', 'unknown date')}",
                f"Location: {complaint_data.get('incident_location', 'unknown')}",
                complaint_data.get('incident_description', 'See full complaint')[:200]
            ],
            "legal_framework": complaint_data.get('applicable_laws', ['Labor law provisions apply']),
            "evidence_summary": "Based on verbal complaint - supporting documents recommended",
            "strengths": ["Clear narrative", "Specific incident description"],
            "weaknesses": ["May need documentary evidence", "Witness statements if available"],
            "recommendation": "Proceed with legal notice after client verification",
            "confidence_assessment": "moderate_confidence"
        }

    def get_agent_info(self) -> Dict[str, Any]:
        return {
            "role": "Senior Legal Draftsman specializing in Indian Labor Law",
            "goal": "Generate comprehensive legal notice and case summary",
            "experience": "20 years drafting labor dispute documents",
            "specializations": [
                "IPC Section 420 (Cheating)",
                "IPC Section 406 (Criminal Breach of Trust)",
                "BOCW Act provisions",
                "Minimum Wages Act",
                "Contract Labor Regulation Act",
                "Legal notice drafting",
                "Case summary preparation"
            ]
        }
