"""
Gemini-backed transcription with speaker diarization + language identification.

Uses Google's hosted `gemini-3.5-transcribe` model via the google-genai SDK's
Interactions API. A single request returns a transcript segmented by speaker and
language, which is exactly what /analyze-media needs to report "who spoke when"
(person shift) and "which language" (language shift).

We use the **structured-output** path (a JSON schema on `response_format`)
rather than the dedicated verbatim mode, because verbatim word annotations carry
a speaker but not a per-segment language — and per-segment language is required
for language-shift detection. The schema below asks the model to start a new
segment whenever the speaker OR the language changes.

The heavy work (upload + model call) is blocking, so callers run
transcribe_with_diarization() inside asyncio.to_thread.
"""

import json
import time
import threading

from src.config import GEMINI_API_KEY, GEMINI_TRANSCRIBE_MODEL

# JSON schema the model must fill in. Times are requested in seconds (numbers) so
# we don't have to parse "MM:SS" strings, though _parse_time() tolerates both.
_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "languages_detected": {"type": "array", "items": {"type": "string"}},
        "speakers_detected": {"type": "array", "items": {"type": "string"}},
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "number"},
                    "end": {"type": "number"},
                    "speaker": {"type": "string"},
                    "language": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["start", "end", "speaker", "language", "text"],
            },
        },
    },
    "required": ["languages_detected", "speakers_detected", "segments"],
}

_PROMPT = (
    "You are a precise transcription and diarization engine. Transcribe the "
    "attached audio verbatim. Identify distinct speakers and label them "
    "'Speaker 1', 'Speaker 2', and so on, consistently. Detect the spoken "
    "language of each part. Split the transcript into segments, starting a NEW "
    "segment whenever the speaker changes OR the spoken language changes. For "
    "each segment provide: start and end time in SECONDS as numbers, the "
    "speaker label, the language as a lowercase ISO 639-1 code (e.g. 'en', "
    "'ar', 'es'), and the text. Also return the full list of detected languages "
    "(ISO codes) and speaker labels. Return only the structured JSON."
)

_client = None
_client_lock = threading.Lock()


def _get_client():
    """Lazily construct the genai client. Raises if no API key is configured."""
    global _client
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Set it in the environment to use "
            "/analyze-media (get a free key at https://aistudio.google.com)."
        )
    if _client is None:
        with _client_lock:
            if _client is None:
                # Imported here so the app imports fine even if google-genai
                # isn't installed until this endpoint is first used.
                from google import genai

                _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def _parse_time(value):
    """
    Coerce a start/end value to float seconds.

    Accepts numbers, or strings like 'SS(.mmm)', 'MM:SS(.mmm)',
    'HH:MM:SS(.mmm)'. Returns 0.0 on anything unparseable so a single bad field
    can't break the whole response.
    """
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str) or not value.strip():
        return 0.0
    parts = value.strip().split(":")
    try:
        parts = [float(p) for p in parts]
    except ValueError:
        return 0.0
    seconds = 0.0
    for part in parts:  # left-to-right, each column is the next 60× up
        seconds = seconds * 60 + part
    return seconds


def _wait_until_active(client, uploaded, attempts: int = 30, delay: float = 2.0):
    """Poll the Files API until the upload finishes processing (best effort)."""
    for _ in range(attempts):
        state = str(getattr(uploaded, "state", "") or "")
        if state == "" or state.upper().endswith("ACTIVE"):
            return uploaded
        if state.upper().endswith("FAILED"):
            raise RuntimeError("Gemini rejected the uploaded audio (processing failed)")
        time.sleep(delay)
        uploaded = client.files.get(name=uploaded.name)
    return uploaded


def _extract_json(text: str) -> dict:
    """Parse the model's JSON, tolerating markdown fences / surrounding prose."""
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start:end + 1])
        raise


def transcribe_with_diarization(audio_path: str, language_codes=None) -> dict:
    """
    Transcribe `audio_path` with speaker diarization + language ID.

    `language_codes`: optional list of BCP-47/ISO codes to constrain detection;
    None/empty means auto-detect. Returns a normalized dict:
        {
          "languages_detected": [...],
          "speakers_detected": [...],
          "segments": [{start, end, speaker, language, text}, ...],
          "transcript_text": "...",
        }
    """
    client = _get_client()

    uploaded = client.files.upload(file=audio_path)
    uploaded = _wait_until_active(client, uploaded)

    prompt = _PROMPT
    if language_codes:
        prompt += (
            "\nThe audio is expected to be in these languages only: "
            + ", ".join(language_codes) + "."
        )

    interaction = client.interactions.create(
        model=GEMINI_TRANSCRIBE_MODEL,
        input=[
            {"type": "text", "text": prompt},
            {
                "type": "audio",
                "uri": uploaded.uri,
                "mime_type": uploaded.mime_type,
            },
        ],
        response_format=_RESPONSE_SCHEMA,
    )

    data = _extract_json(getattr(interaction, "output_text", "") or "")

    # Normalize segments: coerce times, drop empties, keep a stable shape.
    segments = []
    for seg in data.get("segments", []) or []:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        segments.append({
            "start": _parse_time(seg.get("start")),
            "end": _parse_time(seg.get("end")),
            "speaker": (seg.get("speaker") or "").strip() or "Speaker 1",
            "language": (seg.get("language") or "").strip().lower() or "unknown",
            "text": text,
        })
    segments.sort(key=lambda s: s["start"])

    # Prefer the model's lists, but fall back to deriving them from the segments
    # so the summary fields are never empty when segments exist.
    languages = data.get("languages_detected") or sorted(
        {s["language"] for s in segments if s["language"] != "unknown"}
    )
    speakers = data.get("speakers_detected") or sorted(
        {s["speaker"] for s in segments}
    )

    transcript_text = " ".join(s["text"] for s in segments).strip()

    return {
        "languages_detected": languages,
        "speakers_detected": speakers,
        "segments": segments,
        "transcript_text": transcript_text,
    }


def compute_shifts(segments):
    """
    Derive the list of speaker/language shifts from consecutive segments.

    A shift is emitted at a segment boundary whenever the speaker or the
    language differs from the previous segment. Speaker and language changes at
    the same boundary produce two separate entries.
    """
    shifts = []
    for prev, curr in zip(segments, segments[1:]):
        if curr["speaker"] != prev["speaker"]:
            shifts.append({
                "at": curr["start"],
                "type": "speaker",
                "from": prev["speaker"],
                "to": curr["speaker"],
            })
        if curr["language"] != prev["language"]:
            shifts.append({
                "at": curr["start"],
                "type": "language",
                "from": prev["language"],
                "to": curr["language"],
            })
    return shifts
