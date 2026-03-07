# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Paddle Matrix is a FastAPI-based HTTP service that extracts hardcoded subtitles from videos using PaddleOCR. It automatically detects subtitle regions, performs OCR, and generates SRT subtitle files.

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server (with hot-reload)
./manage.sh dev
# OR
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Run production server (background)
./manage.sh start

# Stop server
./manage.sh stop

# Check service status
./manage.sh status

# View logs
./manage.sh logs

# Run tests
pytest tests/

# Run with Docker
docker-compose up -d
```

## Architecture

```
app/
├── main.py              # FastAPI app entry point, route registration
├── config.py            # Settings via pydantic-settings (loads from .env)
├── api/v1/subtitle.py   # REST endpoints: /extract, /extract/async, /status/{id}
├── services/
│   └── subtitle_service.py  # Orchestrates the extraction pipeline
├── core/
│   ├── video_processor.py   # OpenCV-based frame extraction
│   ├── ocr_engine.py        # PaddleOCR wrapper
│   ├── subtitle_detector.py # Anchor discovery mechanism
│   ├── subtitle_merger.py   # Deduplication, timeline smoothing, and debug data collection
│   └── srt_generator.py     # SRT format output
├── models/
│   ├── domain.py        # Dataclasses: SubtitleAnchor, Subtitle (w/ debug_info), DetectedText
│   └── schemas.py       # Pydantic models for API: SubtitleItem (w/ debug_info)
└── static/              # Web UI (index.html w/ debug panel)
```

## Key Algorithms

### Subtitle Region Detection (Anchor Discovery)
The `SubtitleDetector` class uses a multi-strategy pipeline:
1. **Bottom ROI Priority**: Scans bottom 35% of frames first (covers ~90% of cases)
2. **Global Scan**: Falls back to full-frame scanning if bottom ROI fails
3. **Temporal Band Detection**: Uses morphological operations (Top-hat/Black-hat) when OCR finds nothing
4. **Y-axis Clustering & Padding**: Groups detections by vertical position; applies enhanced padding (`x_pad: 8%`, `y_pad: 30%`) to the stable region.

### Subtitle Merging
The `SubtitleMerger` class:
- Uses `SequenceMatcher` for text similarity (threshold: 0.8)
- Implements confidence-weighted voting for text selection
- Performs timeline smoothing and gap merging
- Returns structured `debug_info` containing raw coordinates and processing metadata.

## Configuration

Environment variables (via `.env` file):
- `PADDLEOCR_LANG`: Default OCR language (`ch`, `en`, `korean`, `japan`)
- `VIDEO_SAMPLE_INTERVAL`: Frame sampling interval in seconds (default: 1.0)
- `SUBTITLE_MERGE_THRESHOLD`: Text similarity threshold (default: 0.8)
- `SUBTITLE_MIN_CONFIDENCE`: Minimum OCR confidence (default: 0.7)
- `DEBUG`: Enable debug mode with auto-reload

## Running Tests

Tests use pytest with mocked OCR engine. The main test file is `tests/test_subtitle_detector.py`.

```bash
pytest tests/ -v
```

## API Endpoints

- `POST /api/v1/subtitle/extract` - Synchronous extraction (for short videos)
- `POST /api/v1/subtitle/extract/async` - Async extraction (returns task_id)
- `GET /api/v1/subtitle/status/{task_id}` - Check async task status
- `GET /api/v1/subtitle/download/{task_id}` - Download SRT file
- `GET /docs` - Swagger API documentation