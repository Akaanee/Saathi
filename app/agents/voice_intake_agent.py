from crewai import Agent
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class VoiceIntakeAgent:
    def __init__(self, llm_service):
        self.llm_service = llm_service
        self.agent = self._create_agent()

    def _create_agent(self) -> Agent:
        return Agent(
            role="Expert Legal Intake Specialist for Indian Courts",
            goal="Transform raw voice transcription into a perfectly structured legal complaint in JSON format",
            backstory="""
            You are a highly experienced Legal Intake Specialist with 15 years of experience 
            working in Legal Aid Clinics across India, specializing in helping informal workers 
            (migrants, construction workers, domestic workers) file complaints.
            
            You have deep expertise in:
            - Understanding complaints spoken in Hindi, Bengali, and Tamil
            - Extracting key information from unstructured narrative
            - Identifying legal grounds from factual descriptions
            - Recognizing IPC sections applicable to labor disputes
            - Understanding the BOCW Act, MWA, and other labor laws
            
            You are patient, empathetic, and skilled at piecing together partial information 
            from voices recordings that may be emotional or fragmented.
            
            Your output is ALWAYS structured JSON that follows the exact schema provided.
            """,
            verbose=True,
            allow_delegation=False,
            llm=self.llm_service
        )

    def process_transcription(
        self,
        transcription: str,
        language: str = "hi"
    ) -> Dict[str, Any]:
        logger.info(f"Processing transcription in {language}")
        
        language_names = {
            "hi": "Hindi",
            "bn": "Bengali",
            "ta": "Tamil",
            "en": "English"
        }
        lang_name = language_names.get(language, "the detected language")
        
        prompt = f"""
        You are processing a voice complaint recorded in {lang_name}.
        
        TRANSCRIPTION:
        {transcription}
        
        INSTRUCTIONS:
        1. Carefully analyze the above transcription
        2. Extract all relevant information even if mentioned indirectly or fragmented
        3. If information is not explicitly stated but can be reasonably inferred, note it as "inferred"
        4. If information is completely missing, use null or an empty list
        5. Pay special attention to:
           - Names of people mentioned (complainant, respondent, witnesses)
           - Locations (incident location, addresses)
           - Dates (incident date, when the issue started)
           - Specific incidents or events
           - Any mention of labor laws, IPC sections, or legal terms
           - Relief or compensation being sought
        
        OUTPUT FORMAT:
        Return ONLY valid JSON with this exact structure:
        {{
            "complainant_name": "string or null",
            "complainant_address": "string or null",
            "complainant_occupation": "string or null",
            "respondent_name": "string or null",
            "respondent_address": "string or null",
            "incident_date": "string or null (DD-MM-YYYY format)",
            "incident_location": "string or null",
            "incident_description": "string (detailed narrative)",
            "witnesses": ["list of witness names or empty list"],
            "relief_sought": ["list of specific reliefs or empty list"],
            "applicable_laws": ["list of IPC sections or laws mentioned or inferred"],
            "confidence_scores": {{
                "complainant": 0.0-1.0,
                "respondent": 0.0-1.0,
                "incident": 0.0-1.0,
                "relief": 0.0-1.0,
                "overall": 0.0-1.0
            }},
            "extraction_notes": "string explaining any inferences made or gaps in information"
        }}
        
        JSON OUTPUT (return ONLY this, no markdown or explanation):
        """
        
        try:
            response = self.llm_service.generate_with_retry(
                prompt=prompt,
                system_prompt="You are a JSON-only output system. Return ONLY valid JSON. No markdown, no explanation.",
                temperature=0.3
            )
            
            import json
            result_text = response.get('response', '')
            
            json_start = result_text.find('{')
            json_end = result_text.rfind('}') + 1
            
            if json_start != -1 and json_end != 0:
                json_str = result_text[json_start:json_end]
                structured_data = json.loads(json_str)
                logger.info("Successfully structured complaint data")
                return structured_data
            else:
                logger.error("No JSON found in response")
                return self._create_empty_complaint()
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            return self._create_empty_complaint()
        except Exception as e:
            logger.error(f"Error processing transcription: {e}")
            return self._create_empty_complaint()

    def _create_empty_complaint(self) -> Dict[str, Any]:
        return {
            "complainant_name": None,
            "complainant_address": None,
            "complainant_occupation": None,
            "respondent_name": None,
            "respondent_address": None,
            "incident_date": None,
            "incident_location": None,
            "incident_description": "Unable to structure complaint",
            "witnesses": [],
            "relief_sought": [],
            "applicable_laws": [],
            "confidence_scores": {
                "complainant": 0.0,
                "respondent": 0.0,
                "incident": 0.0,
                "relief": 0.0,
                "overall": 0.0
            },
            "extraction_notes": "Error occurred during processing"
        }

    def validate_complaint(self, complaint_data: Dict[str, Any]) -> Dict[str, Any]:
        required_fields = [
            'complainant_name',
            'incident_description',
            'incident_location'
        ]
        
        missing_fields = []
        for field in required_fields:
            if not complaint_data.get(field):
                missing_fields.append(field)
        
        if missing_fields:
            logger.warning(f"Missing required fields: {missing_fields}")
        
        return {
            "is_valid": len(missing_fields) == 0,
            "missing_fields": missing_fields,
            "warnings": self._generate_warnings(complaint_data)
        }

    def _generate_warnings(self, complaint_data: Dict[str, Any]) -> list:
        warnings = []
        
        if not complaint_data.get('respondent_name'):
            warnings.append("Respondent name not provided - notice will be addressed generically")
        
        if not complaint_data.get('incident_date'):
            warnings.append("Incident date not specified - using 'date unknown'")
        
        if not complaint_data.get('witnesses'):
            warnings.append("No witnesses mentioned - consider gathering evidence")
        
        if not complaint_data.get('applicable_laws'):
            warnings.append("No applicable laws identified - agent will suggest based on description")
        
        overall_confidence = complaint_data.get('confidence_scores', {}).get('overall', 0.0)
        if overall_confidence < 0.5:
            warnings.append("Low confidence in extraction - manual review recommended")
        
        return warnings

    def get_agent_info(self) -> Dict[str, Any]:
        return {
            "role": "Expert Legal Intake Specialist for Indian Courts",
            "goal": "Transform raw voice transcription into structured legal complaint",
            "experience": "15 years in Legal Aid Clinics",
            "specializations": [
                "Hindi, Bengali, Tamil transcription processing",
                "IPC sections for labor disputes",
                "BOCW Act and MWA interpretation",
                "Structured complaint generation"
            ]
        }
