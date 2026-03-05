import cv2
import numpy as np

from app.core.subtitle_detector import SubtitleDetector


class MockOCREngine:
    def __init__(self, detections):
        self._detections = detections
        self._idx = 0

    def detect_text(self, image, lang=None):
        if self._idx >= len(self._detections):
            return []
        result = self._detections[self._idx]
        self._idx += 1
        return result


def _build_frames(count=6, h=720, w=1280):
    frames = []
    for i in range(count):
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        cv2.putText(
            frame,
            f"subtitle line {i}",
            (300, 650),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (255, 255, 255),
            2,
            cv2.LINE_AA
        )
        frames.append(frame)
    return frames


def test_detect_region_from_bottom_roi_ocr():
    frames = _build_frames()
    timestamps = [i * 0.5 for i in range(len(frames))]
    detections = [
        [{"box": (220, 120, 980, 185), "text": f"hello {i}", "confidence": 0.95}]
        for i in range(len(frames))
    ]
    detector = SubtitleDetector(MockOCREngine(detections))
    anchors = detector.detect_subtitle_region(frames, timestamps)

    assert len(anchors) >= 1
    anchor = anchors[0]
    assert 0.55 < anchor.center_y < 0.98
    assert anchor.width > 0.3
    assert anchor.confidence > 0.6


def test_detect_region_falls_back_to_temporal_band():
    frames = _build_frames()
    timestamps = [i * 0.5 for i in range(len(frames))]
    detections = [[] for _ in range(len(frames) + 10)]
    detector = SubtitleDetector(MockOCREngine(detections))
    anchors = detector.detect_subtitle_region(frames, timestamps)

    assert len(anchors) >= 1
    assert anchors[0].center_y > 0.55
