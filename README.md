<p align="center">
  <img src="docs/images/logo.png" width="200" alt="Paddle Matrix Logo">
</p>

# Paddle Matrix - Video Subtitle OCR Service

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License](https://img.shields.io/badge/License-Apache%202.0-green)
![Docker](https://img.shields.io/badge/Docker-Supported-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.95%2B-009688)
![PaddleOCR](https://img.shields.io/badge/PaddleOCR-v2.6%2B-000000)

[中文文档](README_CN.md)

> **Paddle Matrix** is a high-performance HTTP service powered by [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) designed to extract hardcoded subtitles from videos and generate standard SRT subtitle files. It provides a robust API for video subtitle extraction with support for multiple languages and video formats.

## 📚 Table of Contents

- [Features](#-features)
- [Quick Start](#-quick-start)
- [Web Interface](#-web-interface)
- [API Documentation](#-api-documentation)
- [Algorithm & Technical Details](#-algorithm--technical-details)
- [Configuration](#-%EF%B8%8F-configuration)
- [Contributing](#-contributing)
- [License](#-license)

## ✨ Features

- **🎯 Auto Subtitle Detection**: Intelligently identifies subtitle regions within video frames without manual specification.
- **🌍 Multi-language Support**: Robust support for Chinese, English, Japanese, Korean, and more.
- **📹 Wide Format Support**: Compatible with MP4, AVI, MOV, MKV, WebM, FLV, WMV, and other mainstream video formats.
- **📄 SRT Generation**: Automatically generates standard SubRip Subtitle (SRT) files with precise timestamps.
- **⚡ Sync/Async Processing**:
  - **Synchronous**: Real-time processing for short videos.
  - **Asynchronous**: Background task processing for long videos with status polling.
- **🔍 Detailed Debug Info**: Integrated debug info (raw OCR data, padding, original boxes) displayed in the Web UI for troubleshooting.
- **🐳 Docker Ready**: One-click deployment using Docker and Docker Compose.
- **🖥️ Web UI**: Includes a simple built-in web interface for file uploads and testing with interactive debug panel.
- **🍎 macOS Standalone App**: Build a native macOS application with bundled Python runtime and OCR models.

## 🚀 Quick Start

### 🐳 Using Docker (Recommended)

The easiest way to run Paddle Matrix is using Docker Compose.

```bash
# Clone the repository
git clone https://github.com/mistbit/paddle-matrix.git
cd paddle-matrix

# Start the service
docker-compose up -d
```

The service will be available at `http://localhost:8000`.

### 🍎 macOS Standalone App

For macOS users, you can build a standalone application that runs without installing Python or any dependencies.

**Prerequisites:**
- Python 3.10 (for building only)
- Homebrew OpenSSL: `brew install openssl@3`

**Build & Run:**

```bash
# Build the macOS app
./build_app.sh

# Run the app
open "dist/Paddle Matrix.app"

# Or install to Applications
cp -r "dist/Paddle Matrix.app" /Applications/
```

The app includes:
- ✅ Python 3.10 runtime
- ✅ All dependencies (FastAPI, PaddleOCR, OpenCV, etc.)
- ✅ Pre-bundled OCR models (no download on first run)
- ✅ Native desktop window

### 🐍 Local Installation

If you prefer running it locally without Docker:

**Prerequisites:**
- **Python**: 3.10 or higher
- **FFmpeg**: Required for video frame extraction.
  - **Ubuntu/Debian**: `sudo apt install ffmpeg`
  - **macOS**: `brew install ffmpeg`
  - **Windows**: Download from [FFmpeg website](https://ffmpeg.org/download.html) and add to PATH.

**Installation Steps:**

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the service
# Option A: Using helper script
chmod +x manage.sh
./manage.sh start

# Option B: Using Uvicorn directly
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## 🖥️ Web Interface

![Web UI Interface](docs/images/web-ui-preview.png)

Access the built-in web UI at `http://localhost:8000/` to upload videos and test the extraction directly from your browser.

- **Upload**: Drag and drop video files.
- **Preview**: Real-time preview of detection results.
- **Debug**: View bounding boxes and OCR confidence scores.
- **Download**: Export results as SRT files.

## 📖 API Documentation

Interactive API documentation (Swagger UI) is available at `http://localhost:8000/docs`.

### Key Endpoints

1.  **Synchronous Extraction**
    -   `POST /api/v1/subtitle/extract`
    -   Upload a video and wait for the SRT content. Best for short clips.
    -   **Params**: `video` (file), `language` (default: auto), `sample_interval`.

2.  **Asynchronous Extraction**
    -   `POST /api/v1/subtitle/extract/async`
    -   Upload a video and get a `task_id`. Suitable for long videos.

3.  **Check Task Status**
    -   `GET /api/v1/subtitle/status/{task_id}`

4.  **Download Subtitles**
    -   `GET /api/v1/subtitle/download/{task_id}`

### cURL Example

```bash
# Synchronous extraction (Chinese)
curl -X POST "http://localhost:8000/api/v1/subtitle/extract" \
  -H "Content-Type: multipart/form-data" \
  -F "video=@my_video.mp4" \
  -F "language=ch" > output.srt
```

## 🧠 Algorithm & Technical Details

### 1. Intelligent Subtitle Region Detection

Paddle Matrix uses a proprietary **"Anchor Discovery Mechanism"** to automatically locate subtitle regions without manual ROI (Region of Interest) specification.

-   **Multi-Strategy Detection Pipeline**:
    1.  **Bottom ROI Priority**: Scans the bottom 35% of the video first, covering 90% of subtitle scenarios.
    2.  **Global Scan**: Falls back to full-frame scanning if no text is found in the bottom region.
    3.  **Temporal Subtitle Bands**: Utilizes morphological operations and vertical projection analysis.
-   **Stability Clustering & Optimized Padding**:
    -   Performs **Y-axis coordinate clustering** on detection results.
    -   **Enhanced Dynamic Padding**: Automatically calculates optimized padding (`x_pad: 8%`, `y_pad: 30%`) to ensure text integrity.

### 2. OCR Engine Integration

Powered by Baidu's open-source **PaddleOCR** deep learning framework.

-   **Models & Architecture**: Uses PP-OCRv3/v4 ultra-lightweight models.
-   **Dynamic Multi-Language Loading**: Supports on-demand loading of language models (`ch`, `en`, `japan`, `korean`, etc.).
-   **Preprocessing Optimization**: Built-in OpenCV image preprocessing pipeline (BGR -> RGB, enhancement).

### 3. Subtitle Sequence Merger Algorithm

We designed the **SubtitleMerger** algorithm to transform fragmented OCR results into smooth SRT subtitles.

-   **Similarity-Based Deduplication**: Uses `SequenceMatcher` to merge text when similarity > `0.8`.
-   **Voting Mechanism**: **"Confidence + Frequency"** weighted voting system selects the best text content.
-   **Timeline Smoothing**: Automatically merges micro-gaps and estimates reasonable end times.

## ⚙️ Configuration

Copy `.env.example` to `.env` to configure the application.

| Variable | Description | Default |
| :--- | :--- | :--- |
| `APP_NAME` | Application Name | Video Subtitle OCR Service |
| `DEBUG` | Enable debug mode | `False` |
| `PADDLEOCR_LANG` | Default OCR Language | `ch` |
| `VIDEO_SAMPLE_INTERVAL` | Frame sampling interval (sec) | `1.0` |
| `SUBTITLE_MERGE_THRESHOLD` | Text similarity threshold | `0.8` |

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1.  Fork the repository.
2.  Create a new branch (`git checkout -b feature/amazing-feature`).
3.  Commit your changes (`git commit -m 'feat(core): add amazing feature'`).
4.  Push to the branch (`git push origin feature/amazing-feature`).
5.  Open a Pull Request.

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.
