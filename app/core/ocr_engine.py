"""OCR Engine module - wraps PaddleOCR for text detection and recognition"""

import cv2
import numpy as np
from typing import List, Optional, Tuple
import logging

from app.config import settings
from app.models.domain import TextDetection

logger = logging.getLogger(__name__)


class OCREngine:
    """
    OCR Engine - wraps PaddleOCR for text detection and recognition

    Supports multiple languages and provides both detection-only and
    full OCR capabilities.

    Note: GPU usage is determined by the installed PaddlePaddle version:
    - paddlepaddle: CPU only
    - paddlepaddle-gpu: GPU acceleration
    """

    def __init__(
        self,
        lang: str = 'ch',
        use_angle_cls: bool = True
    ):
        """
        Initialize OCR engine

        Args:
            lang: Language code ('ch', 'en', 'korean', 'japan', etc.)
            use_angle_cls: Whether to use angle classifier
        """
        self.lang = lang
        self.use_angle_cls = use_angle_cls

        # Lazy initialization of OCR instances
        self._ocr_instances = {}

        logger.info(f"OCREngine initialized with lang={lang}")

    def _get_ocr_instance(self, lang: Optional[str] = None) -> 'PaddleOCR':
        """
        Get or create OCR instance for specified language

        Args:
            lang: Language code (uses default if None)

        Returns:
            PaddleOCR instance
        """
        target_lang = lang or self.lang

        if target_lang not in self._ocr_instances:
            logger.info(f"Creating new PaddleOCR instance for lang={target_lang}")
            try:
                from paddleocr import PaddleOCR
                self._ocr_instances[target_lang] = PaddleOCR(
                    use_angle_cls=self.use_angle_cls,
                    lang=target_lang,
                    det_db_thresh=settings.PADDLEOCR_DET_DB_THRESH,
                    det_db_box_thresh=settings.PADDLEOCR_DET_DB_BOX_THRESH
                )
            except Exception as e:
                logger.error(f"Failed to create PaddleOCR instance: {e}")
                raise

        return self._ocr_instances[target_lang]

    def detect_text(
        self,
        image: np.ndarray,
        lang: Optional[str] = None
    ) -> List[dict]:
        """
        Detect text in image

        Args:
            image: OpenCV image (BGR format)
            lang: Optional language override

        Returns:
            List of detections: [{'box': (x1,y1,x2,y2), 'text': str, 'confidence': float}, ...]
        """
        ocr = self._get_ocr_instance(lang)

        # PaddleOCR expects RGB, OpenCV uses BGR
        if len(image.shape) == 3:
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            rgb_image = image

        try:
            result = ocr.ocr(rgb_image)
        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return []

        if not result or not result[0]:
            return []

        detections = []
        for line in result[0]:
            box_points = line[0]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            text = line[1][0]
            confidence = line[1][1]

            # Convert to (x1, y1, x2, y2) format
            x_coords = [p[0] for p in box_points]
            y_coords = [p[1] for p in box_points]
            box = (min(x_coords), min(y_coords), max(x_coords), max(y_coords))

            detections.append({
                'box': box,
                'text': text,
                'confidence': confidence
            })

        return detections

    def recognize_in_region(
        self,
        image: np.ndarray,
        region: Tuple[int, int, int, int],
        lang: Optional[str] = None
    ) -> List[dict]:
        """
        Recognize text in specified region

        Args:
            image: Full image
            region: (x1, y1, x2, y2) region coordinates
            lang: Optional language override

        Returns:
            List of recognition results with coordinates adjusted to original image
        """
        x1, y1, x2, y2 = region

        # Clamp coordinates to image bounds
        h, w = image.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        roi = image[y1:y2, x1:x2]

        if roi.size == 0:
            return []

        detections = self.detect_text(roi, lang)

        # Convert coordinates to original image coordinate system
        for det in detections:
            box = det['box']
            det['box'] = (
                int(box[0] + x1),
                int(box[1] + y1),
                int(box[2] + x1),
                int(box[3] + y1)
            )

        return detections

    def detect_with_language_detection(
        self,
        image: np.ndarray,
        languages: List[str] = None
    ) -> Tuple[List[dict], str]:
        """
        Detect text and identify best language

        Args:
            image: Image to process
            languages: List of languages to try (default: ['ch', 'en'])

        Returns:
            Tuple of (detections, detected_language)
        """
        if languages is None:
            languages = ['ch', 'en']

        best_lang = 'ch'  # Default to Chinese
        best_result = []
        max_confidence = 0

        for lang in languages:
            try:
                result = self.detect_text(image, lang)

                if result:
                    avg_conf = sum(d['confidence'] for d in result) / len(result)
                    if avg_conf > max_confidence:
                        max_confidence = avg_conf
                        best_result = result
                        best_lang = lang
            except Exception as e:
                logger.warning(f"OCR with lang={lang} failed: {e}")
                continue

        return best_result, best_lang

    def detect_text_objects(
        self,
        image: np.ndarray,
        lang: Optional[str] = None
    ) -> List[TextDetection]:
        """
        Detect text and return as TextDetection objects

        Args:
            image: OpenCV image
            lang: Optional language override

        Returns:
            List of TextDetection objects
        """
        detections = self.detect_text(image, lang)

        results = []
        for det in detections:
            box = det['box']
            x1, y1, x2, y2 = box

            text_det = TextDetection(
                box=box,
                text=det['text'],
                confidence=det['confidence'],
                center_y=(y1 + y2) / 2,
                center_x=(x1 + x2) / 2,
                height=y2 - y1,
                width=x2 - x1
            )
            results.append(text_det)

        return results

    def is_available(self) -> bool:
        """Check if PaddleOCR is available"""
        try:
            from paddleocr import PaddleOCR
            return True
        except ImportError:
            return False

    def warm_up(self, langs: List[str] = None):
        """
        Warm up OCR models by preloading them

        Args:
            langs: List of languages to preload
        """
        if langs is None:
            langs = [self.lang]

        for lang in langs:
            try:
                self._get_ocr_instance(lang)
                logger.info(f"Warmed up OCR model for lang={lang}")
            except Exception as e:
                logger.warning(f"Failed to warm up OCR for lang={lang}: {e}")