"""Subtitle merger module - handles text deduplication and time merging"""

import numpy as np
from typing import List, Tuple
from difflib import SequenceMatcher
import logging
import re

from app.models.domain import DetectedText, Subtitle

logger = logging.getLogger(__name__)


class SubtitleMerger:
    """
    Subtitle merger - handles text deduplication and time merging

    Strategy:
    1. Sort by timestamp
    2. Merge consecutive similar texts
    3. Handle text change boundaries
    4. Generate final subtitle list
    """

    def __init__(
        self,
        similarity_threshold: float = 0.8,
        time_tolerance: float = 0.5,
        min_duration: float = 0.5
    ):
        """
        Initialize subtitle merger

        Args:
            similarity_threshold: Text similarity threshold for merging
            time_tolerance: Time tolerance for consecutive detections
            min_duration: Minimum subtitle duration in seconds
        """
        self.similarity_threshold = similarity_threshold
        self.time_tolerance = time_tolerance
        self.min_duration = min_duration

    def merge_detected_texts(
        self,
        detections: List[DetectedText]
    ) -> List[Subtitle]:
        """
        Merge detected texts into subtitles

        Strategy:
        1. Sort by time
        2. Merge consecutive identical or similar texts
        3. Handle text change boundaries
        4. Generate final subtitle list

        Args:
            detections: List of detected texts (time-ordered)

        Returns:
            Merged subtitle list
        """
        if not detections:
            return []

        # Sort by timestamp
        sorted_dets = sorted(detections, key=lambda d: d.timestamp)

        # Merge consecutive similar texts
        merged = []
        current_group = [sorted_dets[0]]

        for i in range(1, len(sorted_dets)):
            current = sorted_dets[i]
            prev = current_group[-1]

            # Check if should merge
            if self._should_merge(current, prev):
                current_group.append(current)
            else:
                # End current group, start new one
                merged.append(self._create_subtitle_from_group(current_group))
                current_group = [current]

        # Handle last group
        if current_group:
            merged.append(self._create_subtitle_from_group(current_group))

        # Post-process: adjust time boundaries
        subtitles = self._adjust_time_boundaries(merged)

        logger.info(f"Merged {len(detections)} detections into {len(subtitles)} subtitles")
        return subtitles

    def _should_merge(self, current: DetectedText, prev: DetectedText) -> bool:
        """
        Determine if two detections should be merged

        Args:
            current: Current detection
            prev: Previous detection

        Returns:
            True if should merge
        """
        # Check time gap
        time_gap = current.timestamp - prev.timestamp
        if time_gap > self.time_tolerance * 2:  # More than 2x time tolerance
            return False

        # Check text similarity
        similarity = self._text_similarity(current.text, prev.text)
        return similarity >= self.similarity_threshold

    def _text_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate text similarity

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score (0-1)
        """
        norm1 = self._normalize_text(text1)
        norm2 = self._normalize_text(text2)
        if not norm1 or not norm2:
            return 0.0
        return SequenceMatcher(None, norm1, norm2).ratio()

    def _create_subtitle_from_group(self, group: List[DetectedText]) -> Subtitle:
        """
        Create subtitle from a group of detections

        Args:
            group: List of detections in same group

        Returns:
            Subtitle object
        """
        start_time = group[0].timestamp
        end_time = group[-1].timestamp

        # Use most frequent text (or longest)
        text_counts = {}
        for det in group:
            text_counts[det.text] = text_counts.get(det.text, 0) + 1

        # Select most frequent text
        best_text = max(text_counts.items(), key=lambda x: x[1])[0]
        best_text_detections = [det for det in group if det.text == best_text]
        box_source = max(
            best_text_detections if best_text_detections else group,
            key=lambda det: det.confidence
        )

        # Calculate average confidence
        avg_confidence = np.mean([d.confidence for d in group])

        # Estimate end time (considering sampling interval)
        # If single frame, need to estimate reasonable end time
        if len(group) == 1:
            end_time = start_time + self.min_duration

        return Subtitle(
            index=0,  # Assigned later
            start_time=start_time,
            end_time=end_time,
            text=best_text,
            confidence=avg_confidence,
            box=box_source.box
        )

    def _adjust_time_boundaries(self, subtitles: List[Subtitle]) -> List[Subtitle]:
        """
        Adjust subtitle time boundaries

        Ensures no overlap and minimum duration.

        Args:
            subtitles: List of subtitles

        Returns:
            Adjusted subtitles
        """
        if not subtitles:
            return []

        adjusted = []

        for i, sub in enumerate(subtitles):
            if i > 0:
                prev = adjusted[-1]
                if sub.start_time <= prev.start_time:
                    sub.start_time = prev.start_time + 0.01
                if sub.start_time < prev.end_time:
                    gap = min(0.01, self.min_duration * 0.2)
                    prev.end_time = max(prev.start_time + 0.05, sub.start_time - gap)

            if sub.end_time <= sub.start_time:
                sub.end_time = sub.start_time + self.min_duration

            duration = sub.end_time - sub.start_time
            if duration < self.min_duration:
                sub.end_time = sub.start_time + self.min_duration

            sub.index = i + 1
            adjusted.append(sub)

        return adjusted

    def filter_low_confidence(
        self,
        subtitles: List[Subtitle],
        min_confidence: float = 0.7
    ) -> List[Subtitle]:
        """
        Filter low confidence subtitles

        Args:
            subtitles: List of subtitles
            min_confidence: Minimum confidence threshold

        Returns:
            Filtered subtitles
        """
        filtered = [s for s in subtitles if s.confidence >= min_confidence]

        # Re-index
        for i, sub in enumerate(filtered):
            sub.index = i + 1

        return filtered

    def deduplicate_similar(
        self,
        subtitles: List[Subtitle]
    ) -> List[Subtitle]:
        """
        Remove duplicate content subtitles

        Args:
            subtitles: List of subtitles

        Returns:
            Deduplicated subtitles
        """
        if len(subtitles) <= 1:
            return subtitles

        deduped = [subtitles[0]]

        for current in subtitles[1:]:
            prev = deduped[-1]
            gap = current.start_time - prev.end_time
            similar = self._text_similarity(current.text, prev.text)
            contain = self._is_text_contained(current.text, prev.text)

            if ((similar > 0.92 and gap < self.time_tolerance) or
                (contain and gap < self.time_tolerance * 1.2)):
                prev.end_time = current.end_time
                if len(self._normalize_text(current.text)) > len(self._normalize_text(prev.text)):
                    prev.text = current.text
                if current.box and (not prev.box or current.confidence >= prev.confidence):
                    prev.box = current.box
                prev.confidence = max(prev.confidence, current.confidence)
            else:
                deduped.append(current)

        # Re-index
        for i, sub in enumerate(deduped):
            sub.index = i + 1

        return deduped

    def merge_nearby(
        self,
        subtitles: List[Subtitle],
        max_gap: float = 1.0
    ) -> List[Subtitle]:
        """
        Merge nearby subtitles with same content

        Args:
            subtitles: List of subtitles
            max_gap: Maximum gap to merge (seconds)

        Returns:
            Merged subtitles
        """
        if len(subtitles) <= 1:
            return subtitles

        merged = [subtitles[0]]

        for current in subtitles[1:]:
            prev = merged[-1]
            gap = current.start_time - prev.end_time

            # If same text and small gap, merge
            if (self._text_similarity(current.text, prev.text) > 0.95 and
                gap <= max_gap):
                prev.end_time = current.end_time
            else:
                merged.append(current)

        # Re-index
        for i, sub in enumerate(merged):
            sub.index = i + 1

        return merged

    def _normalize_text(self, text: str) -> str:
        text = text.strip().lower()
        text = re.sub(r"\s+", "", text)
        text = re.sub(r"[^\w\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7a3]", "", text)
        return text

    def _is_text_contained(self, text1: str, text2: str) -> bool:
        n1 = self._normalize_text(text1)
        n2 = self._normalize_text(text2)
        if not n1 or not n2:
            return False
        return n1 in n2 or n2 in n1
