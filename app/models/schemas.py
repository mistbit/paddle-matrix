"""Pydantic schemas for API requests and responses"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Tuple
from enum import Enum


class LanguageEnum(str, Enum):
    """Language options"""
    CHINESE = "ch"
    ENGLISH = "en"
    KOREAN = "korean"
    JAPANESE = "japan"
    AUTO = "auto"


class SubtitleRequest(BaseModel):
    """Subtitle extraction request parameters"""
    language: LanguageEnum = Field(
        default=LanguageEnum.AUTO,
        description="Subtitle language, 'auto' for automatic detection"
    )
    sample_interval: Optional[float] = Field(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="Frame sampling interval in seconds"
    )
    merge_threshold: Optional[float] = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Subtitle merge similarity threshold"
    )
    detect_region: Optional[bool] = Field(
        default=True,
        description="Whether to automatically detect subtitle region"
    )
    roi_bottom_ratio: Optional[float] = Field(
        default=0.35,
        ge=0.1,
        le=0.5,
        description="Bottom ROI ratio (used when detect_region=False)"
    )


class SubtitleItem(BaseModel):
    """Single subtitle item"""
    index: int = Field(..., description="Subtitle sequence number")
    start_time: float = Field(..., description="Start time in seconds")
    end_time: float = Field(..., description="End time in seconds")
    text: str = Field(..., description="Subtitle text")
    confidence: float = Field(..., ge=0, le=1, description="Confidence score")
    box: Optional[Tuple[int, int, int, int]] = Field(
        default=None,
        description="Subtitle bounding box (x1, y1, x2, y2) in video pixels"
    )
    debug_info: Optional[dict] = Field(
        default=None,
        description="Debug information for bounding box calculation"
    )


class SubtitleAnchorItem(BaseModel):
    """Detected subtitle anchor region"""
    center_x: float = Field(..., ge=0, le=1, description="Anchor center X (normalized)")
    center_y: float = Field(..., ge=0, le=1, description="Anchor center Y (normalized)")
    width: float = Field(..., ge=0, le=1, description="Anchor width (normalized)")
    height: float = Field(..., ge=0, le=1, description="Anchor height (normalized)")
    confidence: float = Field(..., ge=0, le=1, description="Anchor confidence")
    language: str = Field(default="auto", description="Anchor language")


class SubtitleResponse(BaseModel):
    """Subtitle extraction response"""
    success: bool = Field(..., description="Whether extraction succeeded")
    message: str = Field(default="", description="Status message")
    subtitles: List[SubtitleItem] = Field(default_factory=list, description="Subtitle list")
    anchors: List[SubtitleAnchorItem] = Field(default_factory=list, description="Detected subtitle regions")
    srt_content: str = Field(default="", description="SRT format subtitle content")
    detected_language: Optional[str] = Field(default=None, description="Detected language")
    total_frames: int = Field(default=0, description="Total frames in video")
    processed_frames: int = Field(default=0, description="Processed frames")
    duration: float = Field(default=0.0, description="Video duration in seconds")


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    ocr_engine: str


class ErrorResponse(BaseModel):
    """Error response"""
    error: str
    detail: str
    code: int


class TaskStatus(str, Enum):
    """Async task status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AsyncTaskResponse(BaseModel):
    """Async task submission response"""
    task_id: str = Field(..., description="Task ID for status query")
    status: TaskStatus = Field(..., description="Current task status")
    message: str = Field(default="", description="Status message")


class AsyncTaskStatus(BaseModel):
    """Async task status response"""
    task_id: str = Field(..., description="Task ID")
    status: TaskStatus = Field(..., description="Current status")
    progress: int = Field(default=0, ge=0, le=100, description="Progress percentage")
    result: Optional[SubtitleResponse] = Field(default=None, description="Result when completed")
    error: Optional[str] = Field(default=None, description="Error message if failed")
