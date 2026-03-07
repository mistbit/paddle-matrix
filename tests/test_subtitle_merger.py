from app.core.subtitle_merger import SubtitleMerger
from app.models.domain import DetectedText


def test_adjust_time_boundaries_no_negative_duration():
    merger = SubtitleMerger(similarity_threshold=0.95, time_tolerance=0.5, min_duration=0.5)
    detections = [
        DetectedText(text="第一句", confidence=0.9, box=(0, 0, 10, 10), timestamp=10.0, frame_index=1),
        DetectedText(text="第二句", confidence=0.9, box=(0, 0, 10, 10), timestamp=10.4, frame_index=2),
        DetectedText(text="第三句", confidence=0.9, box=(0, 0, 10, 10), timestamp=10.8, frame_index=3),
    ]
    subtitles = merger.merge_detected_texts(detections)
    assert len(subtitles) == 3
    for i, sub in enumerate(subtitles):
        assert sub.end_time > sub.start_time
        if i > 0:
            assert subtitles[i - 1].end_time <= sub.start_time


def test_deduplicate_merges_contained_texts():
    merger = SubtitleMerger(similarity_threshold=0.8, time_tolerance=0.5, min_duration=0.5)
    subtitles = merger.merge_detected_texts([
        DetectedText(text="妖怪", confidence=0.8, box=(0, 0, 1, 1), timestamp=1.0, frame_index=1),
        DetectedText(text="妖怪滚回家去", confidence=0.9, box=(0, 0, 1, 1), timestamp=1.3, frame_index=2),
        DetectedText(text="下一句", confidence=0.9, box=(0, 0, 1, 1), timestamp=3.0, frame_index=3),
    ])
    dedup = merger.deduplicate_similar(subtitles)
    assert len(dedup) == 2
    assert "妖怪滚回家去" in dedup[0].text


def test_merge_detected_texts_keeps_subtitle_box():
    merger = SubtitleMerger(similarity_threshold=0.8, time_tolerance=0.5, min_duration=0.5)
    subtitles = merger.merge_detected_texts([
        DetectedText(text="hello world", confidence=0.91, box=(100, 600, 540, 660), timestamp=2.0, frame_index=10),
        DetectedText(text="hello world", confidence=0.96, box=(120, 602, 700, 666), timestamp=2.4, frame_index=11),
        DetectedText(text="next line", confidence=0.88, box=(130, 590, 520, 650), timestamp=4.0, frame_index=20),
    ])
    assert len(subtitles) == 2
    x1, y1, x2, y2 = subtitles[0].box
    assert 95 <= x1 <= 115
    assert 585 <= y1 <= 605
    assert 620 <= x2 <= 640
    assert 662 <= y2 <= 680
    assert subtitles[1].box == (130, 590, 520, 650)
