# Video Intelligence Roadmap

How the platform turns an **audio or video URL** into text, subtitles, and a
speaker- and language-aware transcript — what ships today, and what comes next.

Decisions locked for this roadmap (Aug 2026):

- **One pipeline for audio *and* video.** Video is just "extract audio first,
  then treat it as audio." The analysis stages are identical downstream.
- **The transcript must capture two kinds of "shift":**
  - **person shift** = speaker diarization ("who spoke when");
  - **language shift** = the recording switches language mid-way (e.g. en → ar).
  A new transcript block begins whenever **either** changes, and the response
  carries an explicit `shifts` list.
- **Chosen engine: Google `gemini-3.5-transcribe`** (a hosted multimodal STT
  model). One API call does transcription **+ diarization + language ID +
  timestamps**, so we do **not** self-host Whisper/pyannote/torch for the smart
  transcript. See [Phase 2](#phase-2--gemini-35-transcribe-chosen--next).
  - The existing self-hosted Whisper endpoints stay as a **local/offline**
    option (no data leaves the box). The self-hosted diarization design is kept
    as a [fallback](#appendix--self-hosted-alternative-not-chosen).
- **Named face recognition is explicitly later**, see
  [Phase 3](#phase-3--named-face-recognition-future-not-scheduled).

---

## The pipeline

```
audio URL ─┐
video URL ─┴─► (video only) POST /extract-audio  ✅ shipped  (ffmpeg → audio file)
                     │
                     ├─► POST /transcribe          ✅ shipped  (local Whisper → text)
                     ├─► POST /generate-subtitles  ✅ shipped  (local Whisper → .srt/.vtt)
                     │
                     └─► POST /analyze-media        🔜 Phase 2 (Gemini 3.5 Transcribe)
                             → transcript + speaker + language per segment + shifts
```

---

## Phase 1 — Media extraction & subtitles ✅ SHIPPED

All synchronous, all reusing the existing faster-whisper engine and the
`{BASE_DOMAIN}/files/...` file-serving convention (files auto-expire after 1h).

| Endpoint | Input | Output |
|---|---|---|
| `POST /transcribe` | audio/video URL | transcript + timestamped segments (JSON), local Whisper |
| `POST /extract-audio` | video/audio URL | URL to an extracted audio file (mp3/wav/m4a/ogg/flac) |
| `POST /generate-subtitles` | audio/video URL | URL(s) to `.srt` / `.vtt` files + transcript |

Implementation notes:

- **Shared engine** in [`src/whisper_engine.py`](../src/whisper_engine.py); both
  `/transcribe` and `/generate-subtitles` call `run_transcription()` so the model
  loads once per process.
- **Subtitle formatting** is pure-Python in
  [`src/subtitle_utils.py`](../src/subtitle_utils.py).
- **Audio extraction** shells out to `ffmpeg` (already in the image) — zero new
  Python deps. `sample_rate` + `mono` exist so we can down-convert before
  uploading to Gemini (smaller upload, faster).

---

## Phase 2 — Gemini 3.5 Transcribe (CHOSEN) ✅ SHIPPED

**Shipped as `POST /analyze-media`** ([src/routers/analyze.py](../src/routers/analyze.py)),
backed by [src/gemini_engine.py](../src/gemini_engine.py). Uses the
structured-output path (2b·B) to return per-segment `speaker` + `language` +
`text`, derives the `shifts` list, and renders a speaker/language-labelled SRT.
Set `GEMINI_API_KEY` to enable it; all other endpoints work without it.

`gemini-3.5-transcribe` (Google, released May 2026) is a dedicated speech-to-text
model that returns transcription **with speaker diarization, automatic language
identification, and word-level timestamps** in a single request. This collapses
the entire self-hosted diarization stack into one hosted API call — no torch, no
GPU, no gated HuggingFace download.

### 2a. What it gives us

- **Diarization** — up to 8 speakers (3+ marked experimental) → *person shift*.
- **Language ID** — auto-detects across 85+ locales; omit `language_codes` to
  auto-detect → *language shift*.
- **Timestamps** — word-level start/end offsets.
- Bonus: emotion detection, translation, summarization.

### 2b. How we call it

```
POST https://generativelanguage.googleapis.com/v1beta/interactions
Headers:
  x-goog-api-key: $GEMINI_API_KEY
  Content-Type: application/json
  Api-Revision: 2026-05-20
```

Audio delivery:

- **> a few seconds / > 20 MB → Files API.** Upload with `client.files.upload`,
  then reference the returned `uri` in the request. (Our clips will always use
  this path.)
- Inline base64 only for tiny (< 20 MB) payloads.

Two output strategies — we implement **(A)** and keep **(B)** as a fallback:

- **(A) Verbatim mode** — `mode: {type: "verbatim", diarization_mode: "speaker",
  timestamp_granularities: ["word"]}`. Word-level annotations come back in
  `interaction.steps[].content[].annotations[]` as `{type:"word_info", text,
  speaker, start_offset, end_offset}`. We group words into blocks, breaking on
  speaker change, and tag each block's language.
- **(B) Structured output** — pass a `response_format` JSON schema and prompt for
  `segments: [{start, end, speaker, language, text}]`. Most directly yields the
  exact shape below, including **per-segment `language`**, in one shot. Best when
  we need language cleanly attached to each block.

### 2c. Endpoint design (in our stack)

```
POST /analyze-media
  { "url": "...", "language_codes": null, "diarization": true, "translate": false }

→  (video? extract audio via ffmpeg) → upload to Files API → interactions call →
   parse → normalize to our shape → optionally render speaker/language SRT
```

Target response (a superset of `/transcribe`):

```jsonc
{
  "languages_detected": ["en", "ar"],
  "speakers_detected": ["Speaker 1", "Speaker 2"],
  "segments": [
    { "start": 0.0, "end": 8.2,  "speaker": "Speaker 1", "language": "en", "text": "..." },
    { "start": 8.2, "end": 14.7, "speaker": "Speaker 2", "language": "ar", "text": "..." }
  ],
  "shifts": [
    { "at": 8.2, "type": "speaker",  "from": "Speaker 1", "to": "Speaker 2" },
    { "at": 8.2, "type": "language", "from": "en",         "to": "ar" }
  ],
  "transcript_text": "...",
  "srt_url": "...",
  "model": "gemini-3.5-transcribe",
  "request_id": "...",
  "generated_at": "..."
}
```

### 2d. What you need to provide

- **`GEMINI_API_KEY`** — a free key from Google AI Studio
  (aistudio.google.com → *Get API key*). Passed to the container as an env var,
  never committed to git. This is the Gemini equivalent of the HF token, but
  simpler: no per-model "accept terms" step.
- **New Python dep:** `google-genai` (the official SDK — small, pure-Python, no
  torch). We *could* hand-roll the Files API + REST call with `requests` (already
  a dep) to add nothing, but the SDK handles resumable upload cleanly.

### 2e. Limits, cost & privacy (must-know)

- **Duration cap:** up to 1 hour normally, but **30 minutes when diarization or
  timestamps are enabled** — which we always are. For longer media we chunk the
  audio (ffmpeg segment) and stitch results, or fail fast with a clear message.
- **Cost:** audio is billed per second (~25–32 tokens/sec). Ballpark on the Flash
  tier ≈ **$0.03–0.04 per minute** of audio, so a 10-min clip ≈ **~$0.30–0.40**.
  Cheap, but it's per-request and metered — worth a usage note in the response.
- **Privacy:** audio is uploaded to Google. Fine for most internal content, but
  it **leaves the server** — for anything sensitive, use the local Whisper
  `/transcribe` instead. This is the core trade vs. the self-hosted appendix.
- **Sync vs async:** short clips can stay synchronous with a generous timeout.
  Keep the async job model (below) available for long/chunked media.

### 2f. Async job model (for long/chunked media)

Unchanged from the earlier plan — needed only when we chunk >30-min media:

```
POST /analyze-media?async=true ─► { job_id, status: "queued" }
GET  /jobs/{job_id}             ─► { status: "processing" | "done", result }
```

- In-process `Dict[str, Job]` job store in `src/config.py`, mirroring
  `file_registry` (not durable across restarts; back with Redis later if needed).
- A bounded worker; expire finished jobs + files after 1h via `cleanup_directory`.

### 2g. Speaker/language-aware subtitles

Extend [`subtitle_utils`](../src/subtitle_utils.py) so cues can be prefixed with
the speaker (and language when it changes), e.g. `Speaker 2 [ar]: ...`. Small
additive change to the formatters.

---

## Appendix — self-hosted alternative (NOT chosen)

Kept for the day cloud upload / data-egress is unacceptable and everything must
stay on the box.

- **Transcription:** faster-whisper (already shipped).
- **Diarization:** `pyannote.audio` 3.x → speaker turns; assign each Whisper
  segment to the overlapping speaker. Needs `HF_TOKEN` + accepting the gated
  `pyannote/speaker-diarization-3.1` terms, and pulls in **torch (~1–2 GB)**.
  On CPU it runs ~0.5–2× real-time (a 10-min clip ≈ 5–20 min) → would require the
  async job model as the default, not an option.
- **Language shift:** detect language per speaker turn (simple) or add a
  `speechbrain` VoxLingua107 language-ID pass for within-turn code-switching.
- **Lighter diarization:** `resemblyzer` + clustering (no gated model, lower
  accuracy).

This is strictly heavier and slower than Gemini for the same result; only pick it
for the privacy guarantee.

---

## Phase 3 — Named face recognition (future, not scheduled)

Out of scope for now (the ask was speaker/language shifts, not on-screen faces).
To name people *on screen* you would need: frame sampling (`ffmpeg`), face
detection + embeddings (`insightface`/`deepface`), a curated **known-faces
gallery** (names + reference photos), and nearest-neighbour matching → an
appearance timeline. Realistically wants a **GPU** and carries a biometric
consent/privacy dimension that needs explicit sign-off before building.

> Note: Gemini can already *describe* who/what is on screen from video frames in
> general terms, but **naming specific known individuals** still needs the
> gallery-matching pipeline above.

---

## Dependency & cost summary

| Phase | New deps | Image impact | Secret needed | Per-use cost |
|---|---|---|---|---|
| 1 (shipped) | none (ffmpeg present) | none | none | free (local) |
| 2 Gemini (chosen) | `google-genai` | tiny | `GEMINI_API_KEY` (free key) | ~$0.03–0.04 / audio-min |
| 2 self-hosted (appendix) | `pyannote.audio`, torch | **~1–2 GB** | `HF_TOKEN` + gated terms | free (local), slow on CPU |
| 3 face rec (future) | `insightface`/`deepface` | large | face gallery | wants GPU |
