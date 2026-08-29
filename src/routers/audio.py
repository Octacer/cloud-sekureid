"""Extract the audio track from a video (or re-encode audio) via ffmpeg."""

import os
import uuid
import shutil
import asyncio
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks
import requests

from src.config import DOWNLOADS_DIR, BASE_DOMAIN
from src.helpers import download_url_to_file, cleanup_directory
from src.ffmpeg_utils import AUDIO_CODECS, extract_audio, probe_duration
from src.models import AudioExtractionRequest, AudioExtractionResponse

router = APIRouter()


@router.post("/extract-audio", response_model=AudioExtractionResponse)
async def extract_audio(
    request_data: AudioExtractionRequest,
    background_tasks: BackgroundTasks,
):
    """
    Extract the audio track from a video file (or transcode an audio file) and
    return a URL to the resulting audio file.

    Parameters:
    - **url**: Publicly accessible URL to a video or audio file.
    - **output_format**: mp3 (default), wav, m4a, ogg, or flac.
    - **sample_rate**: Optional target sample rate in Hz (e.g. 16000 for
      speech/ASR pipelines). Omit to keep the source rate.
    - **mono**: Downmix to a single channel (default: false). Handy for
      transcription/diarization which expect mono.

    Returns:
    - JSON with a URL to the extracted audio, its format, size, and duration.
    """
    request_id = str(uuid.uuid4())
    work_dir = os.path.join(DOWNLOADS_DIR, f"audio_{request_id}")
    os.makedirs(work_dir, exist_ok=True)

    out_key = (request_data.output_format or "mp3").lower().lstrip(".")
    if out_key not in AUDIO_CODECS:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise HTTPException(
            status_code=400,
            detail=f"output_format must be one of: {', '.join(sorted(AUDIO_CODECS))}",
        )
    extension, codec_args = AUDIO_CODECS[out_key]

    if request_data.sample_rate is not None and request_data.sample_rate <= 0:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="sample_rate must be a positive integer")

    # No extension on the source — ffmpeg probes the container from content.
    src_path = os.path.join(work_dir, "source")

    try:
        print(f"[{request_id}] Extract-audio request: {request_data.url}")

        # Media files can be large, so use a longer download timeout than the
        # image/PDF endpoints.
        download_url_to_file(str(request_data.url), src_path, timeout=120)
        print(f"[{request_id}] Downloaded {os.path.getsize(src_path)} bytes")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_filename = f"{timestamp}_audio.{extension}"
        out_path = os.path.join(work_dir, out_filename)

        print(f"[{request_id}] Extracting audio → {out_key} "
              f"(sample_rate={request_data.sample_rate or 'source'}, mono={request_data.mono})")
        await asyncio.to_thread(
            extract_audio, src_path, out_path, codec_args,
            request_data.sample_rate, request_data.mono,
        )

        size_bytes = os.path.getsize(out_path)
        duration = probe_duration(out_path)
        print(f"[{request_id}] Done: {size_bytes} bytes, duration={duration}")

        # Remove the source video; keep only the extracted audio for serving.
        if os.path.exists(src_path):
            os.remove(src_path)

        # Schedule cleanup of the whole work dir after 1 hour.
        background_tasks.add_task(cleanup_directory, work_dir, 3600)

        return AudioExtractionResponse(
            url=f"{BASE_DOMAIN}/files/audio_{request_id}/{out_filename}",
            filename=out_filename,
            output_format=out_key,
            sample_rate=request_data.sample_rate,
            channels=1 if request_data.mono else None,
            duration=duration,
            size_bytes=size_bytes,
            request_id=request_id,
            generated_at=datetime.now().isoformat(),
            expires_in=3600,
        )

    except requests.RequestException as e:
        shutil.rmtree(work_dir, ignore_errors=True)
        print(f"[{request_id}] Download error: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to download media from URL: {str(e)}",
        )
    except HTTPException:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(work_dir, ignore_errors=True)
        print(f"[{request_id}] Audio extraction error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to extract audio: {str(e)}",
        )
