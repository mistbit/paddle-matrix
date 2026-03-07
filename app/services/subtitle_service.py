"""Subtitle extraction service - coordinates the complete pipeline"""

import os
import logging
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
import re
import numpy as np

from app.config import settings
from app.core.video_processor import VideoProcessor
from app.core.subtitle_detector import SubtitleDetector
from app.core.ocr_engine import OCREngine
from app.core.subtitle_merger import SubtitleMerger
from app.core.srt_generator import SRTGenerator
from app.models.domain import (
    SubtitleAnchor, Subtitle, SubtitleExtractionResult,
    Language, DetectedText
)

logger = logging.getLogger(__name__)


class SubtitleService:
    """
    Subtitle extraction service - coordinates the complete pipeline

    Pipeline:
    1. Video preprocessing
    2. Subtitle region detection (anchor discovery)
    3. Main detection (sampling + OCR)
    4. Subtitle merging
    5. SRT generation
    """

    def __init__(self):
        self.ocr_engine = None
        self.detector = None
        self.merger = None

    def _initialize(self, language: str = 'ch'):
        """Lazy initialization of components"""
        if self.ocr_engine is None:
            self.ocr_engine = OCREngine(
                lang=language,
                use_angle_cls=settings.PADDLEOCR_USE_ANGLE_CLS
            )

        if self.detector is None:
            self.detector = SubtitleDetector(self.ocr_engine)

        if self.merger is None:
            self.merger = SubtitleMerger(
                similarity_threshold=settings.SUBTITLE_MERGE_THRESHOLD,
                time_tolerance=settings.SUBTITLE_TIME_TOLERANCE
            )

    def extract_subtitles(
        self,
        video_path: str,
        language: str = 'auto',
        sample_interval: float = 1.0,
        detect_region: bool = True,
        roi_bottom_ratio: float = 0.35,
        merge_threshold: float = 0.8
    ) -> SubtitleExtractionResult:
        """
        Extract subtitles from video

        Args:
            video_path: Path to video file
            language: Language code ('auto', 'ch', 'en', 'korean', 'japan')
            sample_interval: Sampling interval in seconds
            detect_region: Whether to auto-detect subtitle region
            roi_bottom_ratio: Bottom ROI ratio (when detect_region=False)
            merge_threshold: Merge similarity threshold

        Returns:
            SubtitleExtractionResult
        """
        logger.info(f"Starting subtitle extraction: {video_path}")

        # Initialize
        lang = language if language != 'auto' else 'ch'
        self._initialize(lang)

        # Update merger parameters
        self.merger.similarity_threshold = merge_threshold

        # Phase 1: Video preprocessing
        with VideoProcessor(video_path) as processor:
            total_frames = processor.total_frames
            duration = processor.duration

            # Phase 2: Subtitle region detection (pre-detection)
            anchors = []
            if detect_region:
                logger.info("Detecting subtitle regions...")
                # Extract pre-detection frames
                pre_frames = []
                pre_timestamps = []
                for frame, ts, idx in processor.extract_specific_frames(
                    settings.SUBTITLE_DETECTION_SAMPLE_RATE
                ):
                    pre_frames.append(frame)
                    pre_timestamps.append(ts)

                # Detect subtitle regions
                if pre_frames:
                    anchors = self.detector.detect_subtitle_region(pre_frames, pre_timestamps)

                if not anchors:
                    logger.warning("No subtitle anchors detected, using default bottom ROI")
                    # Use default bottom region
                    anchors = [self.detector.get_default_anchor(
                        processor.height, processor.width, roi_bottom_ratio
                    )]
            else:
                # Use specified bottom ROI
                anchors = [SubtitleAnchor(
                    center_x=0.5,
                    center_y=1.0 - roi_bottom_ratio / 2,
                    height=roi_bottom_ratio * 0.3,
                    width=0.8,
                    language=Language.AUTO,
                    confidence=0.5
                )]

            # Phase 3: Main detection - sample and recognize
            logger.info(f"Processing video with sample interval: {sample_interval}s")

            all_detections = []
            processed_frames = 0

            tracker_states = [self._create_tracker_state() for _ in anchors]
            for frame, timestamp, frame_idx in processor.extract_frames_by_interval(sample_interval):
                processed_frames += 1

                # Recognize in each anchor region
                for anchor_idx, anchor in enumerate(anchors):
                    tracker_state = tracker_states[anchor_idx]
                    # Refine anchor region
                    region = self._resolve_detection_region(anchor, frame, tracker_state)

                    # OCR recognition
                    ocr_lang = None
                    if anchor.language != Language.AUTO:
                        ocr_lang = anchor.language.value

                    detections = self.ocr_engine.recognize_in_region(
                        frame, region, ocr_lang
                    )

                    merged_detection = self._merge_detections_in_frame(detections)
                    if not merged_detection:
                        continue
                    optimized_box = self._self_optimize_box(
                        merged_detection["box"],
                        merged_detection["confidence"],
                        tracker_state,
                        frame.shape
                    )
                    merged_detection["box"] = optimized_box

                    detected_text = DetectedText(
                        text=merged_detection['text'],
                        confidence=merged_detection['confidence'],
                        box=merged_detection['box'],
                        timestamp=timestamp,
                        frame_index=frame_idx
                    )
                    all_detections.append(detected_text)

        # Phase 4: Merge and generate subtitles
        logger.info(f"Merging {len(all_detections)} text detections...")

        subtitles = self.merger.merge_detected_texts(all_detections)
        subtitles = self.merger.filter_low_confidence(subtitles, settings.SUBTITLE_MIN_CONFIDENCE)
        subtitles = self.merger.deduplicate_similar(subtitles)

        # Detect final language
        detected_lang = Language.AUTO
        if anchors:
            detected_lang = anchors[0].language

        result = SubtitleExtractionResult(
            subtitles=subtitles,
            anchors=anchors,
            total_frames=total_frames,
            processed_frames=processed_frames,
            duration=duration,
            language=detected_lang
        )

        logger.info(f"Extraction complete: {len(subtitles)} subtitles generated")
        return result

    def generate_srt(self, result: SubtitleExtractionResult) -> str:
        """
        Generate SRT format subtitle

        Args:
            result: Extraction result

        Returns:
            SRT format string
        """
        return SRTGenerator.generate(result.subtitles)

    def save_srt(self, result: SubtitleExtractionResult, output_path: str) -> str:
        """
        Save SRT file

        Args:
            result: Extraction result
            output_path: Output file path

        Returns:
            Saved file path
        """
        return SRTGenerator.save_to_file(result.subtitles, output_path)

    def extract_and_save(
        self,
        video_path: str,
        output_path: str,
        **kwargs
    ) -> SubtitleExtractionResult:
        """
        Extract subtitles and save to file

        Args:
            video_path: Path to video file
            output_path: Output SRT file path
            **kwargs: Additional arguments for extract_subtitles

        Returns:
            SubtitleExtractionResult
        """
        result = self.extract_subtitles(video_path, **kwargs)
        self.save_srt(result, output_path)
        return result

    def _merge_detections_in_frame(self, detections: List[dict]) -> Optional[dict]:
        cleaned = []
        for det in detections:
            text = det.get('text', '').strip()
            if not text:
                continue
            if det.get('confidence', 0.0) < settings.SUBTITLE_MIN_CONFIDENCE * 0.45:
                continue
            cleaned.append(det)

        if not cleaned:
            return None

        cleaned = sorted(
            cleaned,
            key=lambda d: ((d['box'][1] + d['box'][3]) / 2, d['box'][0])
        )

        heights = [max(1, d['box'][3] - d['box'][1]) for d in cleaned]
        line_gap = max(8, int(np.mean(heights) * 0.75))
        lines = []
        current = [cleaned[0]]

        for det in cleaned[1:]:
            prev_center_y = np.mean([(d['box'][1] + d['box'][3]) / 2 for d in current])
            cur_center_y = (det['box'][1] + det['box'][3]) / 2
            if abs(cur_center_y - prev_center_y) <= line_gap:
                current.append(det)
            else:
                lines.append(current)
                current = [det]
        lines.append(current)

        line_texts = []
        all_boxes = []
        all_scores = []
        for line in lines:
            line = sorted(line, key=lambda d: d['box'][0])
            line_text = self._join_texts([d['text'] for d in line])
            if line_text:
                line_texts.append(line_text)
                all_boxes.extend([d['box'] for d in line])
                all_scores.extend([d['confidence'] for d in line])

        if not line_texts:
            return None

        x1 = min(b[0] for b in all_boxes)
        y1 = min(b[1] for b in all_boxes)
        x2 = max(b[2] for b in all_boxes)
        y2 = max(b[3] for b in all_boxes)
        text = "\n".join(line_texts)
        confidence = float(np.mean(all_scores))
        return {"text": text, "confidence": confidence, "box": (x1, y1, x2, y2)}

    def _join_texts(self, pieces: List[str]) -> str:
        if not pieces:
            return ""

        merged = pieces[0].strip()
        for piece in pieces[1:]:
            right = piece.strip()
            if not right:
                continue
            if self._needs_space(merged[-1], right[0]):
                merged += " " + right
            else:
                merged += right

        merged = re.sub(r'\s+', ' ', merged).strip()
        return merged

    def _needs_space(self, left_char: str, right_char: str) -> bool:
        return left_char.isalnum() and right_char.isalnum()

    def _create_tracker_state(self) -> Dict[str, Any]:
        return {"stable_box": None, "history": []}

    def _resolve_detection_region(
        self,
        anchor: SubtitleAnchor,
        frame: np.ndarray,
        tracker_state: Dict[str, Any]
    ) -> Tuple[int, int, int, int]:
        base = self.detector.refine_anchor(anchor, frame)
        stable = tracker_state.get("stable_box")
        if stable is None:
            return base

        sh = max(1, stable[3] - stable[1])
        sw = max(1, stable[2] - stable[0])
        pad_x = max(30, int(sw * 0.45))
        pad_y = max(20, int(sh * 0.9))
        adaptive = (
            stable[0] - pad_x,
            stable[1] - pad_y,
            stable[2] + pad_x,
            stable[3] + pad_y
        )
        combined = (
            min(base[0], adaptive[0]),
            min(base[1], adaptive[1]),
            max(base[2], adaptive[2]),
            max(base[3], adaptive[3])
        )
        return self._clamp_box(combined, frame.shape)

    def _self_optimize_box(
        self,
        raw_box: Tuple[int, int, int, int],
        confidence: float,
        tracker_state: Dict[str, Any],
        frame_shape: Tuple[int, int, int]
    ) -> Tuple[int, int, int, int]:
        expanded = self._expand_box(raw_box, frame_shape)
        stable = tracker_state.get("stable_box")

        if stable is None:
            candidate = expanded
        else:
            iou = self._box_iou(expanded, stable)
            if iou >= 0.12:
                alpha = 0.72 if confidence >= settings.SUBTITLE_MIN_CONFIDENCE else 0.5
                candidate = tuple(
                    int(round(alpha * expanded[i] + (1.0 - alpha) * stable[i]))
                    for i in range(4)
                )
            elif confidence < settings.SUBTITLE_MIN_CONFIDENCE * 0.9:
                candidate = stable
            else:
                candidate = expanded

        candidate = self._clamp_box(candidate, frame_shape)
        history = tracker_state["history"]
        history.append(candidate)
        if len(history) > 10:
            history.pop(0)
        tracker_state["stable_box"] = self._median_box(history)
        return tracker_state["stable_box"]

    def _expand_box(
        self,
        box: Tuple[int, int, int, int],
        frame_shape: Tuple[int, int, int]
    ) -> Tuple[int, int, int, int]:
        x1, y1, x2, y2 = box
        width = max(1, x2 - x1)
        height = max(1, y2 - y1)
        pad_x = max(6, int(width * 0.04))
        pad_top = max(4, int(height * 0.3))
        pad_bottom = max(4, int(height * 0.22))
        expanded = (x1 - pad_x, y1 - pad_top, x2 + pad_x, y2 + pad_bottom)
        return self._clamp_box(expanded, frame_shape)

    def _median_box(self, boxes: List[Tuple[int, int, int, int]]) -> Tuple[int, int, int, int]:
        arr = np.array(boxes, dtype=np.float64)
        med = np.median(arr, axis=0)
        return (
            int(round(med[0])),
            int(round(med[1])),
            int(round(med[2])),
            int(round(med[3]))
        )

    def _clamp_box(
        self,
        box: Tuple[int, int, int, int],
        frame_shape: Tuple[int, int, int]
    ) -> Tuple[int, int, int, int]:
        h, w = frame_shape[:2]
        x1, y1, x2, y2 = box
        x1 = int(max(0, min(w - 1, x1)))
        y1 = int(max(0, min(h - 1, y1)))
        x2 = int(max(x1 + 1, min(w, x2)))
        y2 = int(max(y1 + 1, min(h, y2)))
        return (x1, y1, x2, y2)

    def _box_iou(
        self,
        box_a: Tuple[int, int, int, int],
        box_b: Tuple[int, int, int, int]
    ) -> float:
        ax1, ay1, ax2, ay2 = box_a
        bx1, by1, bx2, by2 = box_b
        ix1 = max(ax1, bx1)
        iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2)
        iy2 = min(ay2, by2)
        iw = max(0, ix2 - ix1)
        ih = max(0, iy2 - iy1)
        inter = float(iw * ih)
        if inter <= 0.0:
            return 0.0
        area_a = float(max(1, ax2 - ax1) * max(1, ay2 - ay1))
        area_b = float(max(1, bx2 - bx1) * max(1, by2 - by1))
        union = area_a + area_b - inter
        if union <= 0.0:
            return 0.0
        return inter / union
