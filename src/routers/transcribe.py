"""Audio/video → text transcription endpoint (faster-whisper)."""

import os
import uuid
import asyncio
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks
import requests

from src.config import TRANSCRIBE_TEMP_DIR
from src.helpers import download_url_to_file, cleanup_file
from src.whisper_engine import WHISPER_MODEL_SIZE, VALID_TASKS, run_transcription
from src.models import (
    TranscriptionRequest,
    TranscriptionResponse,
    TranscriptionSegment,
)

router = APIRouter()


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe(
    request_data: TranscriptionRequest,
    background_tasks: BackgroundTasks,
):
    """
    Transcribe an audio or video file to text using Whisper (faster-whisper).

    Parameters:
    - **url**: Publicly accessible URL to an audio or video file
      (mp3, wav, m4a, ogg, flac, mp4, mov, webm, ...). Audio is extracted
      automatically from video containers.
    - **language**: ISO code like 'en', 'es', 'ar' to force a language; omit to
      auto-detect.
    - **task**: 'transcribe' (keep original language) or 'translate' (to English).
    - **include_segments**: include per-segment timestamps (default: true).

    Returns:
    - JSON with the full transcript, detected language, duration, and optional
      timestamped segments.
    """
    request_id = str(uuid.uuid4())
    os.makedirs(TRANSCRIBE_TEMP_DIR, exist_ok=True)

    task = (request_data.task or "transcribe").lower()
    if task not in VALID_TASKS:
        raise HTTPException(
            status_code=400,
            detail=f"task must be one of: {', '.join(VALID_TASKS)}",
        )

    # No extension — faster-whisper/PyAV probe the container from content.
    media_path = os.path.join(TRANSCRIBE_TEMP_DIR, f"{request_id}_media")

    try:
        print(f"[{request_id}] Transcription request: {request_data.url}")

        # Media files can be large, so use a longer download timeout than the
        # image/PDF endpoints.
        download_url_to_file(str(request_data.url), media_path, timeout=120)
        print(f"[{request_id}] Downloaded {os.path.getsize(media_path)} bytes")

        # Offload the CPU-bound transcription to a worker thread so it doesn't
        # block the event loop — long media can take minutes.
        print(
            f"[{request_id}] Transcribing "
            f"(task={task}, language={request_data.language or 'auto'})..."
        )
        segments, info = await asyncio.to_thread(
            run_transcription, media_path, request_data.language, task
        )

        full_text = " ".join(seg["text"] for seg in segments).strip()
        print(
            f"[{request_id}] Done: {len(segments)} segment(s), "
            f"lang={info.language}, {len(full_text)} chars"
        )

        # Remove the downloaded media shortly after responding.
        background_tasks.add_task(cleanup_file, media_path, 60)

        segment_models = None
        if request_data.include_segments:
            segment_models = [TranscriptionSegment(**seg) for seg in segments]

        return TranscriptionResponse(
            text=full_text,
            language=info.language,
            language_probability=getattr(info, "language_probability", None),
            duration=getattr(info, "duration", None),
            task=task,
            model=WHISPER_MODEL_SIZE,
            segments=segment_models,
            request_id=request_id,
            transcribed_at=datetime.now().isoformat(),
        )

    except requests.RequestException as e:
        if os.path.exists(media_path):
            os.remove(media_path)
        print(f"[{request_id}] Download error: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to download media from URL: {str(e)}",
        )
    except HTTPException:
        if os.path.exists(media_path):
            os.remove(media_path)
        raise
    except Exception as e:
        if os.path.exists(media_path):
            os.remove(media_path)
        import traceback
        print(f"[{request_id}] Transcription error: {e}")
        print(f"[{request_id}] Full traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to transcribe media: {str(e)}",
        )
