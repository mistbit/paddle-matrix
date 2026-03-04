"""Configuration management"""

from pydantic_settings import BaseSettings
from typing import List, Optional
import os


class Settings(BaseSettings):
    """Application settings"""

    # 应用配置
    APP_NAME: str = "Video Subtitle OCR Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # OCR配置
    PADDLEOCR_USE_ANGLE_CLS: bool = True
    PADDLEOCR_LANG: str = "ch"  # 支持多语言: ch, en, korean, japan等
    # Note: GPU usage is determined by the installed PaddlePaddle version:
    # - paddlepaddle: CPU only
    # - paddlepaddle-gpu: GPU acceleration
    PADDLEOCR_DET_DB_THRESH: float = 0.3
    PADDLEOCR_DET_DB_BOX_THRESH: float = 0.5

    # 视频处理配置
    VIDEO_SAMPLE_INTERVAL: float = 1.0  # 采样间隔(秒)
    VIDEO_MAX_DURATION: int = 3600      # 最大视频时长(秒)
    VIDEO_SUPPORTED_FORMATS: List[str] = [".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv", ".wmv"]

    # 字幕检测配置
    SUBTITLE_DETECTION_SAMPLE_RATE: int = 10  # 预检测采样帧数
    SUBTITLE_MIN_CONFIDENCE: float = 0.7      # 最小置信度
    SUBTITLE_ROI_BOTTOM_RATIO: float = 0.35    # 底部ROI区域比例
    SUBTITLE_MERGE_THRESHOLD: float = 0.8     # 文本相似度阈值
    SUBTITLE_TIME_TOLERANCE: float = 0.5      # 时间容差(秒)

    # 文件存储配置
    UPLOAD_DIR: str = "/tmp/uploads"
    OUTPUT_DIR: str = "/tmp/outputs"
    MAX_UPLOAD_SIZE: int = 500 * 1024 * 1024  # 500MB

    # 服务配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4

    class Config:
        env_file = ".env"
        case_sensitive = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 确保目录存在
        os.makedirs(self.UPLOAD_DIR, exist_ok=True)
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)


settings = Settings()