import sys
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class EvidenceProcessorAgent:
    def __init__(self, llm_service):
        self.llm_service = llm_service
        self.agent = self._create_agent()

    def _create_agent(self) -> Optional[Any]:
        if sys.version_info >= (3, 14):
            return None

        try:
            from crewai import Agent
        except Exception:
            return None

        return Agent(
            role="Expert Forensic Document Analyst",
            goal="Analyze uploaded evidence and validate consistency with voice complaint",
            backstory="""
            You are a former investigative journalist turned legal document analyst with 
            expertise in forensic examination of evidence for labor disputes and wage theft cases.
            
            You have extensive experience with:
            - Examining wage slips, payment records, and bank statements
            - Identifying discrepancies in employment documentation
            - Detecting forged or altered documents
            - Cross-referencing evidence with verbal complaints
            - Identifying gaps in evidence that need to be filled
            - Understanding common fraud patterns in contractor-worker relationships
            
            You are meticulous, skeptical, and excellent at finding inconsistencies that 
            might be missed by others. You prioritize factual accuracy over convenience.
            
            Your analysis helps lawyers and legal aid workers build stronger cases.
            """,
            verbose=True,
            allow_delegation=False,
            llm=self.llm_service
        )

    def process_evidence(
        self,
        ocr_results: List[Dict[str, Any]],
        complaint_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        logger.info(f"Processing {len(ocr_results)} evidence items")
        
        evidence_texts = self._prepare_evidence_texts(ocr_results)
        
        prompt = f"""
        You are analyzing evidence documents extracted from images using OCR.
        
        VOICE COMPLAINT CONTEXT:
        - Complainant: {complaint_data.get('complainant_name', 'Unknown')}
        - Respondent: {complaint_data.get('respondent_name', 'Unknown')}
        - Incident: {complaint_data.get('incident_description', 'See transcription')}
        - Location: {complaint_data.get('incident_location', 'Unknown')}
        - Relief Sought: {', '.join(complaint_data.get('relief_sought', [])) or 'Not specified'}
        
        EXTRACTED EVIDENCE TEXTS:
        {evidence_texts}
        
        INSTRUCTIONS:
        1. Analyze each piece of evidence for relevance to the complaint
        2. Identify specific information extracted (dates, amounts, names, etc.)
        3. Check for consistency with the voice complaint
        4. Flag any contradictions or suspicious elements
        5. Suggest additional evidence that would strengthen the case
        6. Rank the evidence by strength/reliability
        
        OUTPUT FORMAT:
        Return ONLY valid JSON with this structure:
        {{
            "total_evidence_items": number,
            "evidence_analysis": [
                {{
                    "evidence_id": "string",
                    "evidence_type": "string (e.g., wage_slip, contract, screenshot)",
                    "relevance_score": 0.0-1.0,
                    "reliability_score": 0.0-1.0,
                    "extracted_information": {{
                        "dates": ["list of dates found"],
                        "amounts": ["list of monetary amounts"],
                        "names": ["list of names found"],
                        "locations": ["list of locations"],
                        "other_key_info": ["list of other important information"]
                    }},
                    "consistency_with_complaint": "consistent|inconsistent|partial",
                    "consistency_details": "string explaining consistency check",
                    "concerns": ["list of concerns or flags if any"],
                    "strength": "strong|moderate|weak"
                }}
            ],
            "overall_evidence_quality": "strong|moderate|weak",
            "consistency_check": {{
                "is_consistent": true/false,
                "contradictions": ["list of contradictions found"],
                "supporting_evidence": ["list of evidence supporting the complaint"]
            }},
            "recommended_additional_evidence": ["list of evidence types to gather"],
            "case_building_notes": "string with overall assessment"
        }}
        
        JSON OUTPUT (return ONLY this, no markdown or explanation):
        """
        
        try:
            response = self.llm_service.generate_with_retry(
                prompt=prompt,
                system_prompt="You are a JSON-only output system. Return ONLY valid JSON. No markdown, no explanation.",
                temperature=0.3
            )
            
            result_text = response.get('response', '')
            analysis_result = self._parse_json_object(result_text)
            if analysis_result is not None:
                logger.info(f"Evidence analysis complete: {len(analysis_result.get('evidence_analysis', []))} items analyzed")
                return analysis_result
            else:
                logger.error("No JSON found in response")
                return self._create_empty_analysis(len(ocr_results))
                
        except Exception as e:
            logger.error(f"Error processing evidence: {e}")
            return self._create_empty_analysis(len(ocr_results))

    def _parse_json_object(self, text: str) -> Optional[Dict[str, Any]]:
        import json

        if not text:
            return None

        json_start = text.find('{')
        json_end = text.rfind('}') + 1
        if json_start == -1 or json_end <= json_start:
            return None

        candidate = text[json_start:json_end]
        candidate = self._sanitize_json(candidate)

        try:
            parsed = json.loads(candidate)
        except Exception:
            return None

        if isinstance(parsed, dict):
            return parsed
        return None

    def _sanitize_json(self, text: str) -> str:
        out = []
        in_string = False
        escape = False

        for ch in text:
            if escape:
                out.append(ch)
                escape = False
                continue

            if ch == '\\\\':
                out.append(ch)
                escape = True
                continue

            if ch == '"':
                out.append(ch)
                in_string = not in_string
                continue

            if in_string:
                if ch == '\n':
                    out.append('\\\\n')
                    continue
                if ch == '\r':
                    out.append('\\\\r')
                    continue
                if ch == '\t':
                    out.append('\\\\t')
                    continue
                if ord(ch) < 32:
                    out.append(' ')
                    continue
                out.append(ch)
            else:
                if ord(ch) < 32 and ch not in ('\n', '\r', '\t'):
                    continue
                out.append(ch)

        return ''.join(out)

    def _prepare_evidence_texts(self, ocr_results: List[Dict[str, Any]]) -> str:
        texts = []
        for i, result in enumerate(ocr_results):
            evidence_text = f"""
--- Evidence Item {i+1} ---
Filename/Index: {result.get('filename', f'Image {i+1}')}
Extracted Text:
{result.get('text', 'No text extracted')}
Confidence: {result.get('confidence', 0.0):.2f}
Language: {result.get('detected_language', 'unknown')}
Word Count: {result.get('word_count', 0)}
            """.strip()
            texts.append(evidence_text)
        
        return "\n\n".join(texts)

    def validate_evidence(
        self,
        analysis_result: Dict[str, Any],
        complaint_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        validation_results = {
            "has_evidence": analysis_result.get('total_evidence_items', 0) > 0,
            "quality_threshold_met": analysis_result.get('overall_evidence_quality') in ['strong', 'moderate'],
            "complaint_supported": analysis_result.get('consistency_check', {}).get('is_consistent', False),
            "red_flags": [],
            "action_items": []
        }
        
        if not validation_results["has_evidence"]:
            validation_results["red_flags"].append("No evidence uploaded")
            validation_results["action_items"].append("Upload wage slips, contracts, or other supporting documents")
        
        if analysis_result.get('overall_evidence_quality') == 'weak':
            validation_results["red_flags"].append("Evidence quality is weak")
            validation_results["action_items"].append("Try to obtain clearer copies of documents")
        
        contradictions = analysis_result.get('consistency_check', {}).get('contradictions', [])
        if contradictions:
            validation_results["red_flags"].append(f"Found {len(contradictions)} contradictions")
            validation_results["action_items"].append("Review contradictions and gather supporting evidence")
        
        evidence_types = [e.get('evidence_type', 'unknown') for e in analysis_result.get('evidence_analysis', [])]
        required_types = ['wage_slip', 'contract', 'payment_record']
        missing_types = [rt for rt in required_types if rt not in evidence_types]
        
        if missing_types:
            validation_results["action_items"].append(f"Consider gathering: {', '.join(missing_types)}")
        
        return validation_results

    def _create_empty_analysis(self, item_count: int) -> Dict[str, Any]:
        return {
            "total_evidence_items": item_count,
            "evidence_analysis": [],
            "overall_evidence_quality": "unknown",
            "consistency_check": {
                "is_consistent": False,
                "contradictions": [],
                "supporting_evidence": []
            },
            "recommended_additional_evidence": [
                "Wage slips or payment records",
                "Employment contract or agreement",
                "Bank transaction history",
                "Photographs of workplace conditions",
                "Witness statements"
            ],
            "case_building_notes": "Unable to analyze evidence - please review manually"
        }

    def extract_structured_data(self, ocr_result: Dict[str, Any]) -> Dict[str, Any]:
        text = ocr_result.get('text', '')
        
        import re
        
        dates = re.findall(r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}', text)
        amounts = re.findall(r'₹[\d,]+|Rs\.?\s*[\d,]+|\d+[\d,]*\s*(?:rupees|Rs)', text, re.IGNORECASE)
        
        potential_names = []
        lines = text.split('\n')
        for line in lines[:5]:
            if len(line.strip()) > 3 and len(line.strip()) < 50:
                potential_names.append(line.strip())
        
        return {
            "dates": dates,
            "amounts": amounts,
            "potential_names": potential_names[:3],
            "full_text_length": len(text),
            "confidence": ocr_result.get('confidence', 0.0)
        }

    def get_agent_info(self) -> Dict[str, Any]:
        return {
            "role": "Expert Forensic Document Analyst",
            "goal": "Analyze uploaded evidence and validate consistency with voice complaint",
            "experience": "Former investigative journalist turned legal document analyst",
            "specializations": [
                "Wage slip examination",
                "Contract analysis",
                "Forgery detection",
                "Evidence consistency checking",
                "Labor dispute documentation"
            ]
        }
