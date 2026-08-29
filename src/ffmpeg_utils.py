"""
Shared ffmpeg/ffprobe helpers.

ffmpeg ships in the image already (used by faster-whisper), so these add no new
Python dependency. Used by /extract-audio and by /analyze-media (which
down-converts to a small mono 16 kHz mp3 before uploading to Gemini).
"""

import json
import subprocess

# output_format → (file extension, ffmpeg audio-codec args).
AUDIO_CODECS = {
    "mp3": ("mp3", ["-c:a", "libmp3lame", "-q:a", "2"]),
    "wav": ("wav", ["-c:a", "pcm_s16le"]),
    "m4a": ("m4a", ["-c:a", "aac", "-b:a", "192k"]),
    "ogg": ("ogg", ["-c:a", "libvorbis", "-q:a", "5"]),
    "flac": ("flac", ["-c:a", "flac"]),
}


def probe_duration(path: str):
    """Return media duration in seconds via ffprobe, or None if unavailable."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_format", path,
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            fmt = json.loads(result.stdout).get("format", {})
            return float(fmt["duration"]) if "duration" in fmt else None
    except Exception as probe_error:  # ffprobe missing / unparsable → best effort
        print(f"ffprobe duration probe failed: {probe_error}")
    return None


def has_video_stream(path: str) -> bool:
    """
    True if the file contains a video stream (i.e. it's a video, not bare audio).

    Best effort: album-art thumbnails can register as a video stream, but that
    edge case only mislabels source_type and doesn't affect processing.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_streams", path,
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            streams = json.loads(result.stdout).get("streams", [])
            return any(s.get("codec_type") == "video" for s in streams)
    except Exception as probe_error:
        print(f"ffprobe stream probe failed: {probe_error}")
    return False


def extract_audio(src_path: str, out_path: str, codec_args, sample_rate=None, mono=False):
    """
    Extract/transcode the audio stream of `src_path` into `out_path`.

    Blocking — run in a worker thread via asyncio.to_thread. -vn drops any video
    stream so only audio is written. Raises RuntimeError with the ffmpeg stderr
    tail on failure.
    """
    cmd = ["ffmpeg", "-y", "-i", src_path, "-vn"]
    if mono:
        cmd += ["-ac", "1"]
    if sample_rate:
        cmd += ["-ar", str(sample_rate)]
    cmd += list(codec_args) + [out_path]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        tail = (result.stderr or "").strip()[-800:]
        raise RuntimeError(f"ffmpeg failed (exit {result.returncode}): {tail}")


def to_mono_16k_mp3(src_path: str, out_path: str):
    """
    Convenience: down-convert any audio/video to a small mono 16 kHz mp3.

    Gemini downsamples audio to mono 16 kbps internally, so this both minimises
    the upload size and normalises the container to a format it accepts.
    """
    extract_audio(src_path, out_path, AUDIO_CODECS["mp3"][1], sample_rate=16000, mono=True)
