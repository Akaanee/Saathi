import io
import logging
from typing import Dict, Any, List
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np

logger = logging.getLogger(__name__)

class OCRService:
    def __init__(self):
        self.surya_available = False
        self.tesseract_available = False
        self._initialize()

    def _initialize(self):
        try:
            from surya.ocr import run_ocr
            from surya.model.detection.segformer import load_model as load_det_model, load_processor as load_det_processor
            from surya.model.recognition.model import load_model as load_rec_model
            from surya.model.recognition.processor import load_processor as load_rec_processor
            
            self.det_model, self.det_processor = load_det_model(), load_det_processor()
            self.rec_model, self.rec_processor = load_rec_model(), load_rec_processor()
            self.surya_available = True
            logger.info("Surya OCR loaded successfully")
            
        except ImportError:
            logger.warning("Surya OCR not available, using Tesseract fallback")
            try:
                import pytesseract
                self.pytesseract = pytesseract
                self.tesseract_available = True
                logger.info("Tesseract OCR loaded successfully")
                
            except ImportError:
                logger.error("No OCR implementation available. Install surya-ocr or pytesseract")

    def extract_text_from_image(
        self, 
        image_data: bytes,
        language_hint: str = 'eng'
    ) -> Dict[str, Any]:
        if not (self.surya_available or self.tesseract_available):
            raise RuntimeError("No OCR engine available")

        try:
            image = Image.open(io.BytesIO(image_data))
            
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            processed_image = self._preprocess_image(image)
            
            if self.surya_available:
                return self._extract_with_surya(processed_image, language_hint)
            else:
                return self._extract_with_tesseract(processed_image, language_hint)
                
        except Exception as e:
            logger.error(f"OCR extraction error: {str(e)}")
            raise RuntimeError(f"Failed to extract text from image: {str(e)}")

    def extract_text_from_multiple_images(
        self,
        image_data_list: List[bytes],
        language_hint: str = 'eng'
    ) -> List[Dict[str, Any]]:
        results = []
        for i, image_data in enumerate(image_data_list):
            try:
                result = self.extract_text_from_image(image_data, language_hint)
                result['image_index'] = i
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to process image {i}: {str(e)}")
                results.append({
                    'image_index': i,
                    'success': False,
                    'error': str(e),
                    'text': '',
                    'confidence': 0.0,
                    'detected_language': 'unknown'
                })
        
        return results

    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.5)
        
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(1.3)
        
        image = image.filter(ImageFilter.MedianFilter(size=3))
        
        max_size = (2000, 2000)
        if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        return image

    def _extract_with_surya(self, image: Image.Image, language_hint: str) -> Dict[str, Any]:
        from surya.ocr import run_ocr
        from surya.languages import Language
        
        lang_map = {
            'hi': Language(["hi"]),
            'bn': Language(["bn"]),
            'ta': Language(["ta"]),
            'en': Language(["en"])
        }
        
        languages = lang_map.get(language_hint, Language(["en"]))
        
        predictions = run_ocr(
            [image],
            self.det_model,
            self.det_processor,
            self.rec_model,
            self.rec_processor,
            languages=languages
        )
        
        pred = predictions[0]
        
        text_lines = []
        confidence_scores = []
        
        for text_line in pred.text_lines:
            text_lines.append(text_line.text)
            confidence_scores.append(text_line.confidence)
        
        full_text = "\n".join(text_lines)
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        
        return {
            "text": full_text,
            "confidence": avg_confidence,
            "detected_language": language_hint,
            "word_count": len(full_text.split()),
            "line_count": len(text_lines),
            "bboxes": [
                {
                    "text": line.text,
                    "bbox": line.bbox,
                    "confidence": line.confidence
                }
                for line in pred.text_lines
            ]
        }

    def _extract_with_tesseract(self, image: Image.Image, language_hint: str) -> Dict[str, Any]:
        tess_lang_map = {
            'hi': 'hin',
            'bn': 'ben',
            'ta': 'tam',
            'en': 'eng'
        }
        
        tess_lang = tess_lang_map.get(language_hint, 'eng')
        
        custom_config = r'--oem 3 --psm 6'
        
        data = self.pytesseract.image_to_data(
            image, 
            lang=tess_lang,
            config=custom_config,
            output_type=self.pytesseract.Output.DICT
        )
        
        text_lines = []
        confidences = []
        
        for i, text in enumerate(data['text']):
            conf = int(data['conf'][i])
            if conf > 30 and text.strip():
                text_lines.append(text)
                confidences.append(conf / 100.0)
        
        full_text = "\n".join(text_lines)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        return {
            "text": full_text,
            "confidence": avg_confidence,
            "detected_language": language_hint,
            "word_count": len(full_text.split()),
            "line_count": len(text_lines),
            "bboxes": []
        }

    def extract_structured_data(
        self,
        image_data: bytes,
        expected_fields: List[str]
    ) -> Dict[str, Any]:
        result = self.extract_text_from_image(image_data)
        
        extracted_data = {
            field: self._find_field_in_text(result['text'], field)
            for field in expected_fields
        }
        
        return {
            "text": result['text'],
            "confidence": result['confidence'],
            "structured_data": extracted_data,
            "raw_result": result
        }

    def _find_field_in_text(self, text: str, field: str) -> str:
        field_lower = field.lower()
        text_lines = text.split('\n')
        
        for i, line in enumerate(text_lines):
            if field_lower in line.lower():
                if i + 1 < len(text_lines):
                    return text_lines[i + 1].strip()
                return line.replace(field, '').strip()
        
        return ''

    def is_ready(self) -> bool:
        return self.surya_available or self.tesseract_available

    def get_engine_info(self) -> Dict[str, Any]:
        return {
            "surya_available": self.surya_available,
            "tesseract_available": self.tesseract_available,
            "primary_engine": "surya" if self.surya_available else "tesseract"
        }


ocr_service = OCRService()
