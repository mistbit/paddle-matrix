"""Subtitle region detector - automatically discovers subtitle positions"""

import cv2
import numpy as np
from typing import List, Tuple, Optional
import logging

from app.models.domain import SubtitleAnchor, Language, TextDetection
from app.core.ocr_engine import OCREngine
from app.config import settings

logger = logging.getLogger(__name__)


class SubtitleDetector:
    """
    Subtitle region detector - automatically discovers subtitle positions

    Uses anchor discovery mechanism:
    1. Sample frames uniformly
    2. Detect text in bottom ROI
    3. Cluster by Y position
    4. Find stable regions (subtitles appear at consistent positions)
    """

    def __init__(self, ocr_engine: OCREngine):
        """
        Initialize subtitle detector

        Args:
            ocr_engine: OCR engine instance
        """
        self.ocr_engine = ocr_engine
        self.min_confidence = settings.SUBTITLE_MIN_CONFIDENCE
        self.roi_bottom_ratio = settings.SUBTITLE_ROI_BOTTOM_RATIO

    def detect_subtitle_region(
        self,
        frames: List[np.ndarray],
        timestamps: List[float]
    ) -> List[SubtitleAnchor]:
        """
        Detect subtitle regions (anchor discovery)

        Strategy:
        1. Perform OCR on each frame
        2. Analyze text box position distribution
        3. Identify stable text regions (subtitle characteristic)
        4. Determine subtitle anchors by position clustering

        Args:
            frames: Video frames list
            timestamps: Corresponding timestamps

        Returns:
            List of subtitle anchors
        """
        logger.info(f"Detecting subtitle regions from {len(frames)} frames")

        if not frames:
            return []

        # Collect all detection results
        all_detections = []

        for idx, (frame, timestamp) in enumerate(zip(frames, timestamps)):
            # Detect in bottom ROI
            roi_frame, roi_start = self._extract_bottom_roi(frame)
            detections = self.ocr_engine.detect_text(roi_frame)

            # Convert coordinates to original frame coordinate system
            for det in detections:
                det['abs_box'] = self._roi_to_absolute(det['box'], frame.shape, roi_start)
                det['frame_idx'] = idx
                det['timestamp'] = timestamp
                all_detections.append(det)

        # Analyze detection results to find subtitle anchors
        anchors = self._find_stable_regions(all_detections, frames[0].shape)

        logger.info(f"Found {len(anchors)} subtitle anchors")
        return anchors

    def _extract_bottom_roi(
        self,
        frame: np.ndarray
    ) -> Tuple[np.ndarray, int]:
        """
        Extract bottom ROI region from frame

        Args:
            frame: Input frame

        Returns:
            Tuple of (roi_frame, roi_start_y)
        """
        height = frame.shape[0]
        roi_start = int(height * (1 - self.roi_bottom_ratio))
        return frame[roi_start:, :], roi_start

    def _roi_to_absolute(
        self,
        roi_box: Tuple[int, int, int, int],
        frame_shape: Tuple[int, int, int],
        roi_start: int
    ) -> Tuple[int, int, int, int]:
        """
        Convert ROI coordinates to absolute coordinates

        Args:
            roi_box: Box in ROI coordinates
            frame_shape: Original frame shape
            roi_start: Y offset of ROI start

        Returns:
            Box in absolute coordinates
        """
        x1, y1, x2, y2 = roi_box
        return (int(x1), int(y1 + roi_start), int(x2), int(y2 + roi_start))

    def _find_stable_regions(
        self,
        detections: List[dict],
        frame_shape: Tuple[int, int, int]
    ) -> List[SubtitleAnchor]:
        """
        Find stable subtitle regions

        Algorithm:
        1. Cluster by Y coordinate (subtitles usually at fixed position)
        2. Filter out regions that appear only 1-2 times
        3. Analyze text content change frequency (subtitles change)

        Args:
            detections: All detection results
            frame_shape: Frame dimensions

        Returns:
            List of subtitle anchors
        """
        if not detections:
            return []

        frame_height, frame_width = frame_shape[:2]

        # Compute center coordinates for each detection
        for det in detections:
            box = det['abs_box']
            det['center_y'] = (box[1] + box[3]) / 2
            det['center_x'] = (box[0] + box[2]) / 2
            det['height'] = box[3] - box[1]
            det['width'] = box[2] - box[0]

        # Cluster by Y position
        y_clusters = self._cluster_by_y_position(detections)

        anchors = []
        for cluster in y_clusters:
            # Calculate average position for the region
            avg_y = np.mean([det['center_y'] for det in cluster])
            avg_height = np.mean([det['height'] for det in cluster])
            avg_width = np.mean([det['width'] for det in cluster])
            avg_x = np.mean([det['center_x'] for det in cluster])
            avg_confidence = np.mean([det['confidence'] for det in cluster])

            # Check if in bottom region (subtitles usually at bottom)
            if avg_y > 0.6 * frame_height:  # Lower 40% of frame
                # Detect language from text samples
                texts = [det['text'] for det in cluster]
                language = self._detect_language(texts)

                anchor = SubtitleAnchor(
                    center_x=avg_x / frame_width,
                    center_y=avg_y / frame_height,
                    height=avg_height / frame_height,
                    width=avg_width / frame_width,
                    language=language,
                    confidence=avg_confidence
                )
                anchors.append(anchor)

        return anchors

    def _cluster_by_y_position(
        self,
        detections: List[dict],
        tolerance_ratio: float = 0.05
    ) -> List[List[dict]]:
        """
        Cluster detections by Y coordinate position

        Args:
            detections: Detection results with center_y computed
            tolerance_ratio: Tolerance as ratio of average height

        Returns:
            List of clusters
        """
        if not detections:
            return []

        # Sort by Y coordinate
        sorted_dets = sorted(detections, key=lambda d: d['center_y'])

        clusters = []
        current_cluster = [sorted_dets[0]]

        for i in range(1, len(sorted_dets)):
            det = sorted_dets[i]
            avg_y = np.mean([d['center_y'] for d in current_cluster])
            avg_height = np.mean([d['height'] for d in current_cluster])
            tolerance = tolerance_ratio * avg_height * 2

            if abs(det['center_y'] - avg_y) < tolerance:
                current_cluster.append(det)
            else:
                # Only keep clusters with enough occurrences
                if len(current_cluster) >= 2:
                    clusters.append(current_cluster)
                current_cluster = [det]

        # Don't forget the last cluster
        if len(current_cluster) >= 2:
            clusters.append(current_cluster)

        return clusters

    def _detect_language(self, texts: List[str]) -> Language:
        """
        Detect language from text samples

        Simple heuristic based on character types.

        Args:
            texts: List of text strings

        Returns:
            Detected language
        """
        chinese_chars = 0
        english_chars = 0
        japanese_chars = 0
        korean_chars = 0

        for text in texts:
            for char in text:
                # Chinese characters (CJK Unified Ideographs)
                if '\u4e00' <= char <= '\u9fff':
                    chinese_chars += 1
                # Japanese Hiragana and Katakana
                elif '\u3040' <= char <= '\u30ff':
                    japanese_chars += 1
                # Korean Hangul
                elif '\uac00' <= char <= '\ud7a3':
                    korean_chars += 1
                # English letters
                elif char.isalpha():
                    english_chars += 1

        total = chinese_chars + english_chars + japanese_chars + korean_chars
        if total == 0:
            return Language.AUTO

        # Determine dominant language
        max_count = max(chinese_chars, english_chars, japanese_chars, korean_chars)

        if max_count == chinese_chars and chinese_chars > 0:
            return Language.CHINESE
        elif max_count == english_chars and english_chars > 0:
            return Language.ENGLISH
        elif max_count == japanese_chars and japanese_chars > 0:
            return Language.JAPANESE
        elif max_count == korean_chars and korean_chars > 0:
            return Language.KOREAN
        else:
            return Language.AUTO

    def refine_anchor(
        self,
        anchor: SubtitleAnchor,
        frame: np.ndarray
    ) -> Tuple[int, int, int, int]:
        """
        Refine anchor coordinates to absolute pixel values

        Args:
            anchor: Subtitle anchor
            frame: Video frame

        Returns:
            Precise subtitle region coordinates (x1, y1, x2, y2)
        """
        h, w = frame.shape[:2]

        # Convert to absolute coordinates
        center_x = int(anchor.center_x * w)
        center_y = int(anchor.center_y * h)
        box_height = int(anchor.height * h)
        box_width = int(anchor.width * w)

        # Calculate bounding box with some margin
        margin = 10
        x1 = max(0, center_x - box_width // 2 - margin)
        y1 = max(0, center_y - box_height // 2 - margin)
        x2 = min(w, center_x + box_width // 2 + margin)
        y2 = min(h, center_y + box_height // 2 + margin)

        return (x1, y1, x2, y2)

    def get_default_anchor(
        self,
        frame_height: int,
        frame_width: int,
        roi_bottom_ratio: float = None
    ) -> SubtitleAnchor:
        """
        Get default subtitle anchor based on ROI

        Args:
            frame_height: Frame height
            frame_width: Frame width
            roi_bottom_ratio: Bottom ROI ratio

        Returns:
            Default subtitle anchor
        """
        if roi_bottom_ratio is None:
            roi_bottom_ratio = self.roi_bottom_ratio

        return SubtitleAnchor(
            center_x=0.5,
            center_y=1.0 - roi_bottom_ratio / 2,
            height=roi_bottom_ratio * 0.3,
            width=0.8,
            language=Language.AUTO,
            confidence=0.5
        )