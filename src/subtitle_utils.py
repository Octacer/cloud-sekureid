"""
Subtitle formatting: turn timestamped transcription segments into SRT / WebVTT.

Segments are the dicts produced by whisper_engine.run_transcription, i.e. each
has: id, start (seconds), end (seconds), text.

SRT and WebVTT differ only in a couple of details:
- the millisecond separator: SRT uses a comma (00:00:01,500), VTT uses a dot
  (00:00:01.500);
- VTT requires a "WEBVTT" header line and does not number cues (numbering is
  optional and omitted here).
"""


def _format_timestamp(seconds, sep: str) -> str:
    """
    Format a time offset in seconds as HH:MM:SS<sep>mmm.

    `sep` is ',' for SRT or '.' for WebVTT. Negative/None offsets are clamped to
    zero so a malformed segment can never produce an invalid cue.
    """
    if seconds is None or seconds < 0:
        seconds = 0.0

    # Decompose from a single millisecond total so the remainder is always
    # < 1000 (no risk of a "60" seconds or "1000" ms field from rounding).
    total_ms = int(round(seconds * 1000))
    hours, total_ms = divmod(total_ms, 3_600_000)
    minutes, total_ms = divmod(total_ms, 60_000)
    secs, millis = divmod(total_ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{sep}{millis:03d}"


def segments_to_srt(segments) -> str:
    """Render segments as an SRT document."""
    blocks = []
    for index, seg in enumerate(segments, start=1):
        start = _format_timestamp(seg["start"], ",")
        end = _format_timestamp(seg["end"], ",")
        text = (seg.get("text") or "").strip()
        blocks.append(f"{index}\n{start} --> {end}\n{text}\n")
    # Trailing newline; blank line already separates blocks.
    return "\n".join(blocks) + "\n" if blocks else ""


def segments_to_vtt(segments) -> str:
    """Render segments as a WebVTT document."""
    blocks = ["WEBVTT\n"]
    for seg in segments:
        start = _format_timestamp(seg["start"], ".")
        end = _format_timestamp(seg["end"], ".")
        text = (seg.get("text") or "").strip()
        blocks.append(f"{start} --> {end}\n{text}\n")
    return "\n".join(blocks) + "\n"


def diarized_segments_to_srt(segments) -> str:
    """
    Render speaker/language-tagged segments as an SRT document.

    Each cue's text is prefixed with the speaker and (when present) the language,
    e.g. `Speaker 2 [ar]: ...`, so the subtitle file carries the diarization and
    language-shift information, not just the words.
    """
    blocks = []
    for index, seg in enumerate(segments, start=1):
        start = _format_timestamp(seg["start"], ",")
        end = _format_timestamp(seg["end"], ",")
        text = (seg.get("text") or "").strip()
        speaker = (seg.get("speaker") or "").strip()
        language = (seg.get("language") or "").strip()
        prefix = speaker
        if language and language != "unknown":
            prefix = f"{prefix} [{language}]" if prefix else f"[{language}]"
        line = f"{prefix}: {text}" if prefix else text
        blocks.append(f"{index}\n{start} --> {end}\n{line}\n")
    return "\n".join(blocks) + "\n" if blocks else ""
