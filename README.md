# Video Subtitle OCR Service

基于 PaddleOCR 的视频字幕 OCR 识别 HTTP 服务，自动从视频中提取硬字幕并生成 SRT 字幕文件。

## 功能特性

- 🔍 **自动字幕区域检测**：智能识别字幕出现的位置
- 📝 **多语言支持**：支持中文、英文、日文、韩文等
- 🎬 **视频格式支持**：MP4、AVI、MOV、MKV、WebM 等主流格式
- 📄 **SRT 字幕生成**：自动生成标准 SRT 格式字幕文件
- 🚀 **同步/异步处理**：支持小文件同步处理和大文件异步处理
- 🐳 **Docker 支持**：一键容器化部署

## 系统要求

- Python 3.10+
- FFmpeg (用于视频处理)

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动服务

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Docker 部署

```bash
docker-compose up -d
```

## API 文档

启动服务后访问：http://localhost:8000/docs

### 主要接口

#### 1. 同步提取字幕

```
POST /api/v1/subtitle/extract
Content-Type: multipart/form-data

参数：
- video: 视频文件
- language: 语言 (auto/ch/en/korean/japan)
- sample_interval: 采样间隔(秒)，默认 1.0
- merge_threshold: 合并阈值，默认 0.8
- detect_region: 是否自动检测字幕区域，默认 true
```

#### 2. 异步提取字幕

```
POST /api/v1/subtitle/extract/async
Content-Type: multipart/form-data

返回 task_id 用于查询进度
```

#### 3. 查询任务状态

```
GET /api/v1/subtitle/status/{task_id}
```

#### 4. 下载 SRT 文件

```
GET /api/v1/subtitle/download/{task_id}
```

## 使用示例

### cURL

```bash
# 同步提取
curl -X POST "http://localhost:8000/api/v1/subtitle/extract" \
  -H "Content-Type: multipart/form-data" \
  -F "video=@test.mp4" \
  -F "language=ch"

# 异步提取
curl -X POST "http://localhost:8000/api/v1/subtitle/extract/async" \
  -H "Content-Type: multipart/form-data" \
  -F "video=@large_video.mp4"

# 查询状态
curl "http://localhost:8000/api/v1/subtitle/status/{task_id}"

# 下载 SRT
curl "http://localhost:8000/api/v1/subtitle/download/{task_id}" -o output.srt
```

### Python

```python
import requests

# 上传视频并提取字幕
with open('video.mp4', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/api/v1/subtitle/extract',
        files={'video': f},
        data={'language': 'ch', 'sample_interval': 1.0}
    )

result = response.json()
print(result['srt_content'])

# 保存 SRT 文件
with open('output.srt', 'w', encoding='utf-8') as f:
    f.write(result['srt_content'])
```

## 配置说明

环境变量配置（参考 `.env.example`）：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| PADDLEOCR_USE_GPU | 是否使用 GPU | false |
| PADDLEOCR_LANG | 默认语言 | ch |
| VIDEO_SAMPLE_INTERVAL | 默认采样间隔(秒) | 1.0 |
| VIDEO_MAX_DURATION | 最大视频时长(秒) | 3600 |
| SUBTITLE_MIN_CONFIDENCE | 最小置信度阈值 | 0.7 |
| MAX_UPLOAD_SIZE | 最大上传文件大小 | 500MB |

## 处理流程

```
视频输入
    ↓
视频解码 (OpenCV/FFmpeg)
    ↓
预检测 (锚点发现)
    ├── 均匀采样 N 帧
    ├── OCR 检测文本区域
    └── 聚类确定字幕位置
    ↓
主检测 (采样 + OCR)
    ├── 按时间间隔采样
    ├── 在字幕区域进行 OCR
    └── 收集识别结果
    ↓
字幕合并
    ├── 文本相似度合并
    ├── 时间边界调整
    └── 置信度过滤
    ↓
SRT 生成
```

## 项目结构

```
paddle-matrix/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 配置管理
│   ├── api/v1/subtitle.py   # API 端点
│   ├── core/
│   │   ├── video_processor.py   # 视频处理
│   │   ├── subtitle_detector.py # 字幕区域检测
│   │   ├── ocr_engine.py        # OCR 引擎
│   │   ├── subtitle_merger.py   # 字幕合并
│   │   └── srt_generator.py     # SRT 生成
│   ├── models/
│   │   ├── domain.py        # 领域模型
│   │   └── schemas.py       # API 模型
│   └── services/
│       └── subtitle_service.py  # 业务逻辑
├── tests/
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## 开发

### 运行测试

```bash
pytest tests/
```

### 本地开发模式

```bash
uvicorn app.main:app --reload --debug
```

## License

Apache License 2.0