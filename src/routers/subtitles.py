"""Generate SRT / WebVTT subtitle files from an audio or video URL."""

import os
import uuid
import shutil
import asyncio
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks
import requests

from src.config import DOWNLOADS_DIR, TRANSCRIBE_TEMP_DIR, BASE_DOMAIN
from src.helpers import download_url_to_file, cleanup_file, cleanup_directory
from src.whisper_engine import WHISPER_MODEL_SIZE, VALID_TASKS, run_transcription
from src.subtitle_utils import segments_to_srt, segments_to_vtt
from src.models import (
    SubtitleRequest,
    SubtitleResponse,
    TranscriptionSegment,
)

router = APIRouter()

VALID_FORMATS = ("srt", "vtt", "both")


@router.post("/generate-subtitles", response_model=SubtitleResponse)
async def generate_subtitles(
    request_data: SubtitleRequest,
    background_tasks: BackgroundTasks,
):
    """
    Transcribe an audio/video file and return downloadable subtitle file(s).

    This runs the same Whisper decode as /transcribe, then formats the
    timestamped segments into SRT and/or WebVTT and serves them as files.

    Parameters:
    - **url**: Publicly accessible URL to an audio or video file. Audio is
      extracted automatically from video containers.
    - **language**: ISO code like 'en', 'ar' to force a language; omit to
      auto-detect.
    - **task**: 'transcribe' (keep original language) or 'translate' (to English).
    - **format**: 'srt' (default), 'vtt', or 'both'.
    - **include_segments**: include per-segment timestamps in the JSON response
      (default: true). The subtitle file is returned regardless.

    Returns:
    - JSON with URL(s) to the subtitle file(s), the full transcript, detected
      language, and duration.
    """
    request_id = str(uuid.uuid4())
    os.makedirs(TRANSCRIBE_TEMP_DIR, exist_ok=True)

    task = (request_data.task or "transcribe").lower()
    if task not in VALID_TASKS:
        raise HTTPException(
            status_code=400,
            detail=f"task must be one of: {', '.join(VALID_TASKS)}",
        )

    sub_format = (request_data.format or "srt").lower()
    if sub_format not in VALID_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"format must be one of: {', '.join(VALID_FORMATS)}",
        )

    # No extension — faster-whisper/PyAV probe the container from content.
    media_path = os.path.join(TRANSCRIBE_TEMP_DIR, f"{request_id}_media")
    work_dir = os.path.join(DOWNLOADS_DIR, f"subs_{request_id}")
    os.makedirs(work_dir, exist_ok=True)

    try:
        print(f"[{request_id}] Subtitle request: {request_data.url}")

        download_url_to_file(str(request_data.url), media_path, timeout=120)
        print(f"[{request_id}] Downloaded {os.path.getsize(media_path)} bytes")

        # Offload the CPU-bound transcription to a worker thread so it doesn't
        # block the event loop — long media can take minutes.
        print(
            f"[{request_id}] Transcribing "
            f"(task={task}, language={request_data.language or 'auto'}, format={sub_format})..."
        )
        segments, info = await asyncio.to_thread(
            run_transcription, media_path, request_data.language, task
        )

        full_text = " ".join(seg["text"] for seg in segments).strip()

        # Write the requested subtitle file(s) into the served work dir.
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        srt_url = None
        vtt_url = None

        if sub_format in ("srt", "both"):
            srt_name = f"{timestamp}_subtitles.srt"
            with open(os.path.join(work_dir, srt_name), "w", encoding="utf-8") as f:
                f.write(segments_to_srt(segments))
            srt_url = f"{BASE_DOMAIN}/files/subs_{request_id}/{srt_name}"

        if sub_format in ("vtt", "both"):
            vtt_name = f"{timestamp}_subtitles.vtt"
            with open(os.path.join(work_dir, vtt_name), "w", encoding="utf-8") as f:
                f.write(segments_to_vtt(segments))
            vtt_url = f"{BASE_DOMAIN}/files/subs_{request_id}/{vtt_name}"

        print(
            f"[{request_id}] Done: {len(segments)} segment(s), "
            f"lang={info.language}, srt={bool(srt_url)}, vtt={bool(vtt_url)}"
        )

        # Remove the downloaded media shortly after responding; keep the
        # subtitle work dir for an hour so the file URLs resolve.
        background_tasks.add_task(cleanup_file, media_path, 60)
        background_tasks.add_task(cleanup_directory, work_dir, 3600)

        segment_models = None
        if request_data.include_segments:
            segment_models = [TranscriptionSegment(**seg) for seg in segments]

        return SubtitleResponse(
            srt_url=srt_url,
            vtt_url=vtt_url,
            format=sub_format,
            text=full_text,
            language=info.language,
            language_probability=getattr(info, "language_probability", None),
            duration=getattr(info, "duration", None),
            task=task,
            model=WHISPER_MODEL_SIZE,
            segment_count=len(segments),
            segments=segment_models,
            request_id=request_id,
            generated_at=datetime.now().isoformat(),
            expires_in=3600,
        )

    except requests.RequestException as e:
        if os.path.exists(media_path):
            os.remove(media_path)
        shutil.rmtree(work_dir, ignore_errors=True)
        print(f"[{request_id}] Download error: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to download media from URL: {str(e)}",
        )
    except HTTPException:
        if os.path.exists(media_path):
            os.remove(media_path)
        shutil.rmtree(work_dir, ignore_errors=True)
        raise
    except Exception as e:
        if os.path.exists(media_path):
            os.remove(media_path)
        shutil.rmtree(work_dir, ignore_errors=True)
        import traceback
        print(f"[{request_id}] Subtitle error: {e}")
        print(f"[{request_id}] Full traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate subtitles: {str(e)}",
        )
