"""
Shared faster-whisper engine: lazy model singleton + transcription.

Both the /transcribe and /generate-subtitles endpoints run the same underlying
Whisper decode, so the heavy WhisperModel (ctranslate2 + downloaded weights) is
constructed once per process and reused here rather than loaded separately per
router.

The model size / device / precision are read from the environment so the same
image can run a tiny model on a small box or a larger one where accuracy
matters, without any code change.
"""

import os
import threading

WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL", "base")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
# int8 is the fastest/lightest on CPU; use float16 on a GPU.
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

VALID_TASKS = ("transcribe", "translate")

# The model is expensive to construct and downloads weights on first use, so it
# is built once (lazily) and reused across requests. The lock guards that
# first-time construction against concurrent requests racing to build it.
_model = None
_model_lock = threading.Lock()


def get_model():
    """Lazily construct and cache the WhisperModel singleton."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                # Imported here so importing this module (and the whole app)
                # doesn't pull in ctranslate2 until transcription is first used.
                from faster_whisper import WhisperModel

                print(
                    f"Loading Whisper model '{WHISPER_MODEL_SIZE}' "
                    f"(device={WHISPER_DEVICE}, compute_type={WHISPER_COMPUTE_TYPE})..."
                )
                _model = WhisperModel(
                    WHISPER_MODEL_SIZE,
                    device=WHISPER_DEVICE,
                    compute_type=WHISPER_COMPUTE_TYPE,
                )
                print("Whisper model loaded")
    return _model


def run_transcription(media_path: str, language, task: str):
    """
    Blocking transcription — intended to be executed in a worker thread via
    asyncio.to_thread.

    faster-whisper returns a lazy generator of segments; the actual decoding
    happens as it is consumed, so it is materialized here (inside the worker
    thread) rather than back on the event loop.

    Returns a tuple of (segments, info) where segments is a list of dicts with
    keys: id, start, end, text.
    """
    model = get_model()
    segments_gen, info = model.transcribe(
        media_path,
        language=language,   # None → auto-detect
        task=task,
        beam_size=5,
        vad_filter=True,     # skip long silences → faster, cleaner output
    )
    segments = [
        {"id": i, "start": s.start, "end": s.end, "text": s.text.strip()}
        for i, s in enumerate(segments_gen)
    ]
    return segments, info
