"""Subtitle API endpoints"""

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Form
from fastapi.responses import PlainTextResponse
from typing import Optional
import tempfile
import os
from pathlib import Path
import logging
import uuid

from app.models.schemas import (
    SubtitleRequest, SubtitleResponse, SubtitleItem, SubtitleAnchorItem,
    HealthResponse, AsyncTaskResponse, AsyncTaskStatus, TaskStatus
)
from app.services.subtitle_service import SubtitleService
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Store task results (production should use Redis)
task_results = {}


@router.post("/extract", response_model=SubtitleResponse)
async def extract_subtitles(
    video: UploadFile = File(..., description="Video file"),
    language: str = Form(default="auto"),
    sample_interval: float = Form(default=1.0),
    merge_threshold: float = Form(default=0.8),
    detect_region: bool = Form(default=True),
    roi_bottom_ratio: float = Form(default=0.35)
):
    """
    Extract subtitles from video (synchronous)

    - **video**: Video file
    - **language**: Language (auto/ch/en/korean/japan)
    - **sample_interval**: Frame sampling interval in seconds
    - **merge_threshold**: Subtitle merge similarity threshold
    - **detect_region**: Whether to auto-detect subtitle region
    - **roi_bottom_ratio**: Bottom ROI ratio (when detect_region=False)
    """
    # Validate file format
    file_ext = Path(video.filename).suffix.lower()
    if file_ext not in settings.VIDEO_SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported video format: {file_ext}. "
                  f"Supported: {settings.VIDEO_SUPPORTED_FORMATS}"
        )

    # Check file size
    content = await video.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {settings.MAX_UPLOAD_SIZE / 1024 / 1024}MB"
        )

    # Save to temporary file
    temp_dir = tempfile.mkdtemp()
    temp_video_path = os.path.join(temp_dir, f"input{file_ext}")

    try:
        with open(temp_video_path, 'wb') as f:
            f.write(content)

        # Extract subtitles
        service = SubtitleService()
        result = service.extract_subtitles(
            video_path=temp_video_path,
            language=language,
            sample_interval=sample_interval,
            detect_region=detect_region,
            roi_bottom_ratio=roi_bottom_ratio,
            merge_threshold=merge_threshold
        )

        # Generate SRT
        srt_content = service.generate_srt(result)

        # Build response
        subtitle_items = [
            SubtitleItem(
                index=sub.index,
                start_time=sub.start_time,
                end_time=sub.end_time,
                text=sub.text,
                confidence=sub.confidence,
                box=sub.box
            )
            for sub in result.subtitles
        ]
        anchor_items = [
            SubtitleAnchorItem(
                center_x=anchor.center_x,
                center_y=anchor.center_y,
                width=anchor.width,
                height=anchor.height,
                confidence=anchor.confidence,
                language=anchor.language.value
            )
            for anchor in result.anchors
        ]

        return SubtitleResponse(
            success=True,
            message="Subtitles extracted successfully",
            subtitles=subtitle_items,
            anchors=anchor_items,
            srt_content=srt_content,
            detected_language=result.language.value,
            total_frames=result.total_frames,
            processed_frames=result.processed_frames,
            duration=result.duration
        )

    except Exception as e:
        logger.exception("Subtitle extraction failed")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # Cleanup temporary files
        if os.path.exists(temp_video_path):
            os.remove(temp_video_path)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)


@router.post("/extract/async", response_model=AsyncTaskResponse)
async def extract_subtitles_async(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    language: str = Form(default="auto"),
    sample_interval: float = Form(default=1.0),
    merge_threshold: float = Form(default=0.8),
    detect_region: bool = Form(default=True),
    roi_bottom_ratio: float = Form(default=0.35)
):
    """
    Extract subtitles asynchronously (for large files)

    Returns task_id for status query via /status/{task_id}
    """
    # Validate file format
    file_ext = Path(video.filename).suffix.lower()
    if file_ext not in settings.VIDEO_SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported video format: {file_ext}"
        )

    task_id = str(uuid.uuid4())

    # Save uploaded file
    temp_dir = tempfile.mkdtemp()
    temp_video_path = os.path.join(temp_dir, f"input{file_ext}")

    content = await video.read()
    with open(temp_video_path, 'wb') as f:
        f.write(content)

    # Initialize task status
    task_results[task_id] = {
        'status': TaskStatus.PENDING,
        'progress': 0,
        'result': None,
        'error': None
    }

    # Background task
    def process_video():
        try:
            task_results[task_id]['status'] = TaskStatus.PROCESSING
            task_results[task_id]['progress'] = 10

            service = SubtitleService()
            result = service.extract_subtitles(
                video_path=temp_video_path,
                language=language,
                sample_interval=sample_interval,
                detect_region=detect_region,
                roi_bottom_ratio=roi_bottom_ratio,
                merge_threshold=merge_threshold
            )

            task_results[task_id]['progress'] = 90

            srt_content = service.generate_srt(result)

            subtitle_items = [
                SubtitleItem(
                    index=sub.index,
                    start_time=sub.start_time,
                    end_time=sub.end_time,
                    text=sub.text,
                    confidence=sub.confidence,
                    box=sub.box
                )
                for sub in result.subtitles
            ]
            anchor_items = [
                SubtitleAnchorItem(
                    center_x=anchor.center_x,
                    center_y=anchor.center_y,
                    width=anchor.width,
                    height=anchor.height,
                    confidence=anchor.confidence,
                    language=anchor.language.value
                )
                for anchor in result.anchors
            ]

            task_results[task_id]['status'] = TaskStatus.COMPLETED
            task_results[task_id]['progress'] = 100
            task_results[task_id]['result'] = SubtitleResponse(
                success=True,
                message="Subtitles extracted successfully",
                subtitles=subtitle_items,
                anchors=anchor_items,
                srt_content=srt_content,
                detected_language=result.language.value,
                total_frames=result.total_frames,
                processed_frames=result.processed_frames,
                duration=result.duration
            )

        except Exception as e:
            logger.exception("Async subtitle extraction failed")
            task_results[task_id]['status'] = TaskStatus.FAILED
            task_results[task_id]['error'] = str(e)

        finally:
            # Cleanup
            if os.path.exists(temp_video_path):
                os.remove(temp_video_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)

    background_tasks.add_task(process_video)

    return AsyncTaskResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        message="Task submitted. Use /status/{task_id} to check progress."
    )


@router.get("/status/{task_id}", response_model=AsyncTaskStatus)
async def get_task_status(task_id: str):
    """
    Query async task status

    - **task_id**: Task ID returned from /extract/async
    """
    if task_id not in task_results:
        raise HTTPException(status_code=404, detail="Task not found")

    task = task_results[task_id]
    return AsyncTaskStatus(
        task_id=task_id,
        status=task['status'],
        progress=task['progress'],
        result=task.get('result'),
        error=task.get('error')
    )


@router.get("/download/{task_id}", response_class=PlainTextResponse)
async def download_srt(task_id: str):
    """
    Download SRT file

    - **task_id**: Task ID from completed async extraction
    """
    if task_id not in task_results:
        raise HTTPException(status_code=404, detail="Task not found")

    task = task_results[task_id]
    if task['status'] != TaskStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Task status: {task['status']}"
        )

    result = task.get('result')
    if not result:
        raise HTTPException(status_code=404, detail="No result available")

    return result.srt_content


@router.delete("/task/{task_id}")
async def delete_task(task_id: str):
    """
    Delete task result

    - **task_id**: Task ID to delete
    """
    if task_id not in task_results:
        raise HTTPException(status_code=404, detail="Task not found")

    del task_results[task_id]
    return {"message": "Task deleted successfully"}
