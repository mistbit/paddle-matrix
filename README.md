<p align="center">
  <img src="logo.png" width="200" alt="Paddle Matrix Logo">
</p>

# Paddle Matrix - Video Subtitle OCR Service

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License](https://img.shields.io/badge/License-Apache%202.0-green)
![Docker](https://img.shields.io/badge/Docker-Supported-blue)

[中文文档](README_CN.md)

![Web UI Interface](ui.png)

**Paddle Matrix** is a high-performance HTTP service powered by [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) designed to extract hardcoded subtitles from videos and generate standard SRT subtitle files. It provides a robust API for video subtitle extraction with support for multiple languages and video formats.

## ✨ Features

- **🎯 Auto Subtitle Detection**: Intelligently identifies subtitle regions within video frames without manual specification.
- **🌍 Multi-language Support**: robust support for Chinese, English, Japanese, Korean, and more.
- **📹 Wide Format Support**: Compatible with MP4, AVI, MOV, MKV, WebM, FLV, WMV, and other mainstream video formats.
- **📄 SRT Generation**: Automatically generates standard SubRip Subtitle (SRT) files with precise timestamps.
- **⚡ Sync/Async Processing**:
  - **Synchronous**: Real-time processing for short videos.
  - **Asynchronous**: Background task processing for long videos with status polling.
- **🔍 Detailed Debug Info**: Integrated debug info (raw OCR data, padding, original boxes) displayed in the Web UI for troubleshooting.
- **🐳 Docker Ready**: One-click deployment using Docker and Docker Compose.
- **🖥️ Web UI**: Includes a simple built-in web interface for file uploads and testing with interactive debug panel.

## 🧠 Algorithm & Technical Details

### 1. Intelligent Subtitle Region Detection

Paddle Matrix uses a proprietary **"Anchor Discovery Mechanism"** to automatically locate subtitle regions without manual ROI (Region of Interest) specification.

-   **Multi-Strategy Detection Pipeline**:
    1.  **Bottom ROI Priority**: Scans the bottom 35% of the video first, covering 90% of subtitle scenarios.
    2.  **Global Scan**: Falls back to full-frame scanning if no text is found in the bottom region.
    3.  **Temporal Subtitle Bands**: Utilizes morphological operations (Top-hat/Black-hat transforms) and vertical projection analysis to identify spatiotemporal bands with "subtitle characteristics."
-   **Stability Clustering & Optimized Padding**:
    -   Performs **Y-axis coordinate clustering** on detection results from sampled frames.
    -   Analyzes text box frequency and positional stability to lock onto the most probable "Subtitle Anchor."
    -   **Enhanced Dynamic Padding**: Automatically calculates optimized padding (`x_pad: 8%`, `y_pad: 30%` of width/height) around the median box to ensure all text characters are fully captured without being clipped.
    -   Automatically filters out transient text (e.g., bullet comments, signs), preserving only stable subtitle streams.

### 2. OCR Engine Integration

Powered by Baidu's open-source **PaddleOCR** deep learning framework, delivering industrial-grade text recognition capabilities.

-   **Models & Architecture**: Uses PP-OCRv3/v4 ultra-lightweight models to optimize inference speed while maintaining high accuracy.
-   **Dynamic Multi-Language Loading**: Supports on-demand loading of language models (`ch`, `en`, `japan`, `korean`, etc.) based on request parameters, saving GPU/CPU memory.
-   **Preprocessing Optimization**: Built-in OpenCV image preprocessing pipeline handles color space conversion (BGR -> RGB) and image enhancement to boost OCR recognition rates.

### 3. Subtitle Sequence Merger Algorithm

Raw frame-by-frame OCR results are fragmented and contain redundancy. We designed the **SubtitleMerger** algorithm to transform them into smooth SRT subtitles.

-   **Similarity-Based Deduplication**:
    -   Uses `SequenceMatcher` to calculate text similarity between adjacent frames.
    -   Merges text when similarity > `SUBTITLE_MERGE_THRESHOLD` (default 0.8) and the time gap is within tolerance.
-   **Voting Mechanism**: For multiple detections of the same subtitle line, a **"Confidence + Frequency"** weighted voting system selects the best text content, effectively removing random OCR noise characters.
-   **Timeline Smoothing & Debug Data Aggregation**:
    -   Automatically merges micro-gaps in time and estimates reasonable end times based on text length, generating a seamless timeline.
    -   **Full Traceability**: Aggregates raw detection coordinates, confidence scores, and selection counts into a `debug_info` object for each merged subtitle, providing transparent insights into the merging process.

## 🛠️ System Requirements

- **Python**: 3.10 or higher
- **FFmpeg**: Required for video frame extraction and processing.
- **OS**: Linux, macOS, or Windows

## 🚀 Quick Start

### 1. Installation

#### Install FFmpeg

- **Ubuntu/Debian**:
  ```bash
  sudo apt update && sudo apt install ffmpeg
  ```
- **macOS**:
  ```bash
  brew install ffmpeg
  ```
- **Windows**: Download from [FFmpeg website](https://ffmpeg.org/download.html) and add to PATH.

#### Install Python Dependencies

```bash
git clone https://github.com/yourusername/paddle-matrix.git
cd paddle-matrix
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Running the Service

#### Using Uvicorn (Development)

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Using Helper Script

```bash
chmod +x manage.sh
./manage.sh start
```

#### Using Docker (Recommended for Production)

```bash
docker-compose up -d
```

The service will be available at `http://localhost:8000`.

## 📖 Usage

### Web Interface

Access the built-in web UI at `http://localhost:8000/` to upload videos and test the extraction directly from your browser.

### API Documentation

Interactive API documentation (Swagger UI) is available at `http://localhost:8000/docs`.

#### Key Endpoints

1.  **Synchronous Extraction**
    -   **Endpoint**: `POST /api/v1/subtitle/extract`
    -   **Description**: Upload a video and wait for the SRT content in response. Best for short clips.
    -   **Parameters**:
        -   `video`: Video file (multipart/form-data)
        -   `language`: `ch` (Chinese), `en` (English), `japan` (Japanese), `korean` (Korean), `auto`.
        -   `sample_interval`: Frame sampling interval in seconds (default: 1.0).

2.  **Asynchronous Extraction**
    -   **Endpoint**: `POST /api/v1/subtitle/extract/async`
    -   **Description**: Upload a video and get a `task_id`. Suitable for long videos.
    -   **Response**: `{"task_id": "uuid..."}`

3.  **Check Task Status**
    -   **Endpoint**: `GET /api/v1/subtitle/status/{task_id}`
    -   **Response**: Status (`pending`, `processing`, `completed`, `failed`) and progress.

4.  **Download Subtitles**
    -   **Endpoint**: `GET /api/v1/subtitle/download/{task_id}`
    -   **Description**: Download the generated SRT file for a completed task.

### Example: Extract Subtitles with cURL

```bash
# Synchronous extraction (Chinese)
curl -X POST "http://localhost:8000/api/v1/subtitle/extract" \
  -H "Content-Type: multipart/form-data" \
  -F "video=@my_video.mp4" \
  -F "language=ch" > output.srt

# Asynchronous extraction
curl -X POST "http://localhost:8000/api/v1/subtitle/extract/async" \
  -H "Content-Type: multipart/form-data" \
  -F "video=@movie.mkv"
```

## ⚙️ Configuration

You can configure the application using environment variables or a `.env` file. Copy `.env.example` to `.env` to get started.

| Variable | Description | Default |
| :--- | :--- | :--- |
| `APP_NAME` | Application Name | Video Subtitle OCR Service |
| `DEBUG` | Enable debug mode | `False` |
| `PADDLEOCR_LANG` | Default OCR Language | `ch` |
| `VIDEO_SAMPLE_INTERVAL` | Frame sampling interval (sec) | `1.0` |
| `SUBTITLE_MERGE_THRESHOLD` | Text similarity threshold for merging | `0.8` |
| `UPLOAD_DIR` | Directory for temp uploads | `/tmp/uploads` |
| `OUTPUT_DIR` | Directory for generated SRTs | `/tmp/outputs` |

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1.  Fork the repository.
2.  Create a new branch (`git checkout -b feature/amazing-feature`).
3.  Commit your changes (`git commit -m 'feat(core): add amazing feature'`).
4.  Push to the branch (`git push origin feature/amazing-feature`).
5.  Open a Pull Request.

Please adhere to the [Conventional Commits](https://www.conventionalcommits.org/) specification for commit messages.

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.
