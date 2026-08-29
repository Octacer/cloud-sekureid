"""
Analyze an audio/video file into a speaker- and language-aware transcript.

Pipeline: download → (ffmpeg) down-convert to mono 16 kHz mp3 → upload to Gemini
→ gemini-3.5-transcribe (diarization + language ID) → normalized segments +
shifts + a speaker/language-labelled SRT.

This is the hosted counterpart to the local /transcribe endpoint: it adds "who
spoke" (person shift) and "which language" (language shift) at the cost of
sending the audio to Google. For sensitive media, use /transcribe instead.
"""

import os
import uuid
import shutil
import asyncio
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks
import requests

from src.config import (
    ANALYZE_TEMP_DIR, DOWNLOADS_DIR, BASE_DOMAIN,
    GEMINI_API_KEY, GEMINI_TRANSCRIBE_MODEL,
)
from src.helpers import download_url_to_file, cleanup_directory
from src.ffmpeg_utils import has_video_stream, to_mono_16k_mp3, probe_duration
from src.gemini_engine import transcribe_with_diarization, compute_shifts
from src.subtitle_utils import diarized_segments_to_srt
from src.models import AnalyzeMediaRequest, AnalyzeMediaResponse, AnalyzeSegment, MediaShift

router = APIRouter()


def _run_pipeline(src_path: str, audio_path: str, language_codes):
    """
    Blocking work — run in a worker thread via asyncio.to_thread.

    Probes the source, down-converts to a small mono mp3, then calls Gemini.
    """
    is_video = has_video_stream(src_path)
    to_mono_16k_mp3(src_path, audio_path)
    duration = probe_duration(audio_path)
    result = transcribe_with_diarization(audio_path, language_codes)
    return is_video, duration, result


@router.post("/analyze-media", response_model=AnalyzeMediaResponse)
async def analyze_media(
    request_data: AnalyzeMediaRequest,
    background_tasks: BackgroundTasks,
):
    """
    Transcribe an audio/video file with speaker diarization and language ID.

    Handles both audio and video (audio is extracted from video automatically).
    A new segment begins whenever the speaker or the spoken language changes, and
    those change points are returned in `shifts`.

    Parameters:
    - **url**: Publicly accessible URL to an audio or video file.
    - **language_codes**: Optional list of ISO/BCP-47 codes to constrain
      detection (e.g. ["en", "ar"]); omit to auto-detect across 85+ locales.
    - **include_segments**: include per-segment detail (default: true).
    - **generate_srt**: also produce a speaker/language-labelled .srt (default: true).

    Returns:
    - JSON with detected languages/speakers, per-segment transcript, the list of
      speaker/language shifts, the full transcript text, and an optional SRT URL.

    Note: this uploads the audio to Google's Gemini API. Requires GEMINI_API_KEY
    to be configured on the server.
    """
    # Fail fast (before downloading anything) if the key isn't configured.
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail=(
                "GEMINI_API_KEY is not configured on the server. Set it in the "
                "environment to use /analyze-media (free key: "
                "https://aistudio.google.com). For a fully local transcript, "
                "use /transcribe instead."
            ),
        )

    request_id = str(uuid.uuid4())
    temp_dir = os.path.join(ANALYZE_TEMP_DIR, request_id)
    os.makedirs(temp_dir, exist_ok=True)
    src_path = os.path.join(temp_dir, "source")
    audio_path = os.path.join(temp_dir, "audio.mp3")

    try:
        print(f"[{request_id}] Analyze-media request: {request_data.url}")

        download_url_to_file(str(request_data.url), src_path, timeout=120)
        print(f"[{request_id}] Downloaded {os.path.getsize(src_path)} bytes")

        print(f"[{request_id}] Extracting audio + calling Gemini "
              f"({GEMINI_TRANSCRIBE_MODEL}, langs={request_data.language_codes or 'auto'})...")
        is_video, duration, result = await asyncio.to_thread(
            _run_pipeline, src_path, audio_path, request_data.language_codes
        )

        segments = result["segments"]
        shifts = compute_shifts(segments)
        print(f"[{request_id}] Done: {len(segments)} segment(s), "
              f"speakers={result['speakers_detected']}, langs={result['languages_detected']}, "
              f"{len(shifts)} shift(s)")

        # Optionally render a speaker/language-labelled SRT into a served dir.
        srt_url = None
        if request_data.generate_srt and segments:
            dl_dir = os.path.join(DOWNLOADS_DIR, f"analyze_{request_id}")
            os.makedirs(dl_dir, exist_ok=True)
            srt_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_diarized.srt"
            with open(os.path.join(dl_dir, srt_name), "w", encoding="utf-8") as f:
                f.write(diarized_segments_to_srt(segments))
            srt_url = f"{BASE_DOMAIN}/files/analyze_{request_id}/{srt_name}"
            background_tasks.add_task(cleanup_directory, dl_dir, 3600)

        # Remove the intermediate download/audio shortly after responding.
        background_tasks.add_task(cleanup_directory, temp_dir, 60)

        segment_models = None
        if request_data.include_segments:
            segment_models = [AnalyzeSegment(**seg) for seg in segments]

        return AnalyzeMediaResponse(
            languages_detected=result["languages_detected"],
            speakers_detected=result["speakers_detected"],
            segments=segment_models,
            shifts=[MediaShift(**shift) for shift in shifts],
            transcript_text=result["transcript_text"],
            srt_url=srt_url,
            source_type="video" if is_video else "audio",
            duration=duration,
            model=GEMINI_TRANSCRIBE_MODEL,
            request_id=request_id,
            generated_at=datetime.now().isoformat(),
            expires_in=3600,
        )

    except requests.RequestException as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"[{request_id}] Download error: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to download media from URL: {str(e)}",
        )
    except HTTPException:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        import traceback
        print(f"[{request_id}] Analyze error: {e}")
        print(f"[{request_id}] Full traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=502,
            detail=f"Failed to analyze media: {str(e)}",
        )
