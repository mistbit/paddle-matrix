<p align="center">
  <img src="logo.png" width="200" alt="Paddle Matrix Logo">
</p>

# Paddle Matrix - 视频字幕 OCR 服务

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License](https://img.shields.io/badge/License-Apache%202.0-green)
![Docker](https://img.shields.io/badge/Docker-Supported-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.95%2B-009688)
![PaddleOCR](https://img.shields.io/badge/PaddleOCR-v2.6%2B-000000)

[English](README.md)

> **Paddle Matrix** 是一个基于 [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) 的高性能 HTTP 服务，专为从视频中提取硬字幕并生成标准的 SRT 字幕文件而设计。它提供了强大的视频字幕提取 API，支持多种语言和主流视频格式。

![Web UI 界面](ui.png)

## 📚 目录

- [功能特性](#-功能特性)
- [快速开始](#-快速开始)
- [Web 界面](#-web-界面)
- [API 文档](#-api-文档)
- [核心技术与算法](#-核心技术与算法)
- [配置](#-%EF%B8%8F-配置)
- [贡献指南](#-贡献指南)
- [许可证](#-许可证)

## ✨ 功能特性

- **🎯 自动字幕检测**：智能识别视频帧中的字幕区域，无需手动指定位置。
- **🌍 多语言支持**：完美支持中文、英文、日文、韩文等多种语言。
- **📹 广泛的格式支持**：兼容 MP4、AVI、MOV、MKV、WebM、FLV、WMV 等主流视频格式。
- **📄 SRT 生成**：自动生成带有精确时间戳的标准 SubRip Subtitle (SRT) 字幕文件。
- **⚡ 同步/异步处理**：
  - **同步模式**：适用于短视频的实时处理。
  - **异步模式**：适用于长视频的后台任务处理，支持状态查询。
- **🔍 详细调试信息**：集成调试信息（原始 OCR 数据、内边距、原始框坐标）并直接在 Web UI 中展示，方便排查识别异常。
- **🐳 Docker 支持**：使用 Docker 和 Docker Compose 一键部署。
- **🖥️ Web 界面**：内置简单的 Web 界面，支持上传视频并带有交互式调试面板。

## 🚀 快速开始

### 🐳 使用 Docker (推荐)

使用 Docker Compose 是运行 Paddle Matrix 最简单的方式。

```bash
# 克隆仓库
git clone https://github.com/mistbit/paddle-matrix.git
cd paddle-matrix

# 启动服务
docker-compose up -d
```

服务启动后访问地址：`http://localhost:8000`。

### 🐍 本地安装

如果您更喜欢在本地直接运行：

**前置要求:**
- **Python**: 3.10 或更高版本
- **FFmpeg**: 用于视频抽帧。
  - **Ubuntu/Debian**: `sudo apt install ffmpeg`
  - **macOS**: `brew install ffmpeg`
  - **Windows**: 从 [FFmpeg 官网](https://ffmpeg.org/download.html) 下载并添加到 PATH 环境变量。

**安装步骤:**

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows 用户: .venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 启动服务
# 方式 A: 使用辅助脚本
chmod +x manage.sh
./manage.sh start

# 方式 B: 直接使用 Uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## 🖥️ Web 界面

访问内置的 Web 界面 `http://localhost:8000/`，您可以直接在浏览器中进行操作：

- **上传**: 拖拽或选择视频文件。
- **预览**: 实时预览字幕检测结果。
- **调试**: 查看检测框和 OCR 置信度。
- **下载**: 导出 SRT 字幕文件。

## 📖 API 文档

交互式 API 文档 (Swagger UI) 地址：`http://localhost:8000/docs`。

### 主要接口

1.  **同步提取**
    -   `POST /api/v1/subtitle/extract`
    -   上传视频并等待响应返回 SRT 内容。适合短视频。
    -   **参数**: `video` (文件), `language` (默认: auto), `sample_interval`。

2.  **异步提取**
    -   `POST /api/v1/subtitle/extract/async`
    -   上传视频并获取 `task_id`。适合长视频。

3.  **查询任务状态**
    -   `GET /api/v1/subtitle/status/{task_id}`

4.  **下载字幕**
    -   `GET /api/v1/subtitle/download/{task_id}`

### cURL 示例

```bash
# 同步提取 (中文)
curl -X POST "http://localhost:8000/api/v1/subtitle/extract" \
  -H "Content-Type: multipart/form-data" \
  -F "video=@my_video.mp4" \
  -F "language=ch" > output.srt
```

## 🧠 核心技术与算法

### 1. 智能字幕区域检测

Paddle Matrix 采用独创的 **"Anchor Discovery Mechanism" (锚点发现机制)** 自动定位字幕区域。

-   **多策略探测管线**:
    1.  **底部 ROI 优先**: 优先扫描视频底部 35% 区域。
    2.  **全局扫描**: 若底部未发现文本，切换至全帧扫描。
    3.  **时序波段检测**: 利用形态学操作和垂直投影分析。
-   **稳定性聚类与边距优化**:
    -   对检测结果进行 **Y 轴坐标聚类**。
    -   **动态边距增强**: 自动计算优化边距 (`x_pad: 8%`, `y_pad: 30%`)。

### 2. OCR 识别引擎

基于百度开源的 **PaddleOCR** 深度学习框架。

-   **模型与架构**: 使用 PP-OCRv3/v4 超轻量级模型。
-   **多语言动态加载**: 支持 `ch`, `en`, `japan`, `korean` 等按需加载。
-   **预处理优化**: 内置 OpenCV 图像预处理流水线。

### 3. 字幕序列合并算法

我们设计了 **SubtitleMerger** 算法将碎片化的 OCR 结果转化为流畅的 SRT 字幕。

-   **基于相似度的去重**: 相似度 > `0.8` 时合并文本。
-   **投票机制**: **"置信度 + 频率"** 加权投票选出最佳文本。
-   **时间轴平滑**: 自动合并微小断裂并估算结束时间。

## ⚙️ 配置

复制 `.env.example` 到 `.env` 即可开始配置。

| 变量名 | 描述 | 默认值 |
| :--- | :--- | :--- |
| `APP_NAME` | 应用名称 | Video Subtitle OCR Service |
| `DEBUG` | 开启调试模式 | `False` |
| `PADDLEOCR_LANG` | 默认 OCR 语言 | `ch` |
| `VIDEO_SAMPLE_INTERVAL` | 视频采样间隔 (秒) | `1.0` |
| `SUBTITLE_MERGE_THRESHOLD` | 文本合并相似度阈值 | `0.8` |

## 🤝 贡献指南

欢迎贡献代码！请遵循以下步骤：

1.  Fork 本仓库。
2.  创建新的分支 (`git checkout -b feature/amazing-feature`)。
3.  提交更改 (`git commit -m 'feat(core): add amazing feature'`)。
4.  推送到分支 (`git push origin feature/amazing-feature`)。
5.  提交 Pull Request。

## 📄 许可证

本项目采用 Apache License 2.0 许可证 - 详情请参阅 [LICENSE](LICENSE) 文件。
