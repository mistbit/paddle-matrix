"""Subtitle extraction service - coordinates the complete pipeline"""

import os
import logging
from typing import Optional, List
from pathlib import Path

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

            for frame, timestamp, frame_idx in processor.extract_frames_by_interval(sample_interval):
                processed_frames += 1

                # Recognize in each anchor region
                for anchor in anchors:
                    # Refine anchor region
                    region = self.detector.refine_anchor(anchor, frame)

                    # OCR recognition
                    ocr_lang = None
                    if anchor.language != Language.AUTO:
                        ocr_lang = anchor.language.value

                    detections = self.ocr_engine.recognize_in_region(
                        frame, region, ocr_lang
                    )

                    # Collect detection results
                    for det in detections:
                        detected_text = DetectedText(
                            text=det['text'],
                            confidence=det['confidence'],
                            box=det['box'],
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