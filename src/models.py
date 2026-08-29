"""
Pydantic request/response models for the Sekure-ID API.
"""

from pydantic import BaseModel, HttpUrl, Field, ConfigDict
from typing import Optional, List


class ReportRequest(BaseModel):
    company_code: str = "85"
    username: str = "hisham.octacer"
    password: str = "P@ss1234"
    report_date: Optional[str] = None  # Format: YYYY-MM-DD


class ReportResponse(BaseModel):
    report_url: str
    file_id: str
    report_date: str
    generated_at: str
    expires_in: int  # seconds


class PdfToImageRequest(BaseModel):
    pdf_url: HttpUrl  # Publicly accessible PDF URL


class MarkdownToPdfRequest(BaseModel):
    # --- Input (provide exactly one) -------------------------------------
    markdown: Optional[str] = None          # Raw markdown text
    markdown_url: Optional[HttpUrl] = None  # Public URL to a .md file to fetch

    # --- Document options ------------------------------------------------
    title: Optional[str] = None             # Document title (header + PDF metadata + filename)
    page_size: str = "A4"                   # A4 | Letter | Legal
    orientation: str = "portrait"           # portrait | landscape
    filename: Optional[str] = None          # Desired output filename (without needing .pdf)

    # --- Branding (applied only when branding=True) ----------------------
    branding: bool = True                   # Master toggle: header, footer, brand colors
    company_name: str = "Octacer"           # Wordmark shown in the header
    logo_url: Optional[HttpUrl] = None      # Optional logo image for the header (falls back to wordmark)
    brand_color: str = "#0B5CAD"            # Accent colour for headings, links, rules, table headers
    footer_text: Optional[str] = None       # Extra text on the left of the footer (default: company_name)
    show_page_numbers: bool = True          # 'Page X of Y' on the right of the footer

    # --- Watermark (independent of branding; off unless set) -------------
    watermark: Optional[str] = None         # Faint diagonal watermark text, e.g. 'CONFIDENTIAL'


class MarkdownToPdfResponse(BaseModel):
    url: str                                # URL to the generated PDF
    filename: str
    branding: bool                          # Whether branded chrome was applied
    watermarked: bool                       # Whether a watermark was rendered
    page_size: str                          # 'A4' | 'Letter' | 'Legal'
    orientation: str                        # 'portrait' | 'landscape'
    total_pages: Optional[int]              # Page count (None if it could not be determined)
    size_bytes: int
    request_id: str
    generated_at: str                       # ISO timestamp
    expires_in: int                         # seconds


class VollnaCookiesRequest(BaseModel):
    email: str
    password: str
    final_url: str = "https://www.vollna.com/dashboard/filter/22703"


class VollnaCookiesResponse(BaseModel):
    cookies: str
    cookie_count: int
    extracted_at: str


class ImageInfo(BaseModel):
    page: int
    url: str
    filename: str


class PdfToImageResponse(BaseModel):
    images: List[ImageInfo]
    total_pages: int
    conversion_id: str
    generated_at: str
    expires_in: int  # seconds


class TextExtractionRequest(BaseModel):
    url: HttpUrl  # Publicly accessible URL to image or PDF


class TextExtractionResponse(BaseModel):
    text: str
    language: str
    extraction_method: str
    source_type: str  # 'image', 'pdf', 'spreadsheet', or 'document'
    total_pages: int  # For PDFs, number of pages processed
    extracted_at: str
    request_id: str


class ImageResizeRequest(BaseModel):
    url: HttpUrl  # Publicly accessible URL to the source image
    width: Optional[int] = None  # Target width in pixels
    height: Optional[int] = None  # Target height in pixels
    mode: str = "fit"  # 'fit' (keep aspect, bounding box) or 'exact' (force dimensions)
    output_format: str = "jpeg"  # jpeg | jpg | png | webp
    quality: int = 90  # Encoder quality for lossy formats (jpeg/webp), 1-100


class ImageResizeResponse(BaseModel):
    url: str
    filename: str
    source_format: Optional[str]  # Detected input format (e.g. 'HEIF', 'PNG')
    output_format: str  # Output format actually written (e.g. 'JPEG')
    original_width: int
    original_height: int
    new_width: int
    new_height: int
    size_bytes: int
    mode: str
    request_id: str
    generated_at: str
    expires_in: int  # seconds


class TranscriptionRequest(BaseModel):
    url: HttpUrl  # Publicly accessible URL to an audio or video file
    language: Optional[str] = None  # ISO code (e.g. 'en', 'ar'); None = auto-detect
    task: str = "transcribe"  # 'transcribe' (keep language) or 'translate' (to English)
    include_segments: bool = True  # Include per-segment timestamps in the response


class TranscriptionSegment(BaseModel):
    id: int
    start: float  # Segment start time in seconds
    end: float  # Segment end time in seconds
    text: str


class TranscriptionResponse(BaseModel):
    text: str  # Full transcript
    language: str  # Detected (or forced) language code
    language_probability: Optional[float]  # Confidence when auto-detected
    duration: Optional[float]  # Duration of audio processed, in seconds
    task: str  # 'transcribe' or 'translate'
    model: str  # Whisper model size used
    segments: Optional[List[TranscriptionSegment]]  # Present when include_segments=true
    request_id: str
    transcribed_at: str  # ISO timestamp


class AudioExtractionRequest(BaseModel):
    url: HttpUrl  # Publicly accessible URL to a video or audio file
    output_format: str = "mp3"  # mp3 | wav | m4a | ogg | flac
    sample_rate: Optional[int] = None  # Target sample rate in Hz (e.g. 16000); None = keep source
    mono: bool = False  # Downmix to a single channel


class AudioExtractionResponse(BaseModel):
    url: str  # URL to the extracted audio file
    filename: str
    output_format: str  # Format actually written (e.g. 'mp3')
    sample_rate: Optional[int]  # Requested sample rate, if any
    channels: Optional[int]  # 1 when mono was requested, else None (source channels kept)
    duration: Optional[float]  # Audio duration in seconds (via ffprobe), if available
    size_bytes: int
    request_id: str
    generated_at: str
    expires_in: int  # seconds


class SubtitleRequest(BaseModel):
    url: HttpUrl  # Publicly accessible URL to an audio or video file
    language: Optional[str] = None  # ISO code (e.g. 'en', 'ar'); None = auto-detect
    task: str = "transcribe"  # 'transcribe' (keep language) or 'translate' (to English)
    format: str = "srt"  # 'srt', 'vtt', or 'both'
    include_segments: bool = True  # Include per-segment timestamps in the JSON response


class SubtitleResponse(BaseModel):
    srt_url: Optional[str]  # URL to the .srt file (when format is 'srt' or 'both')
    vtt_url: Optional[str]  # URL to the .vtt file (when format is 'vtt' or 'both')
    format: str  # 'srt', 'vtt', or 'both'
    text: str  # Full transcript
    language: str  # Detected (or forced) language code
    language_probability: Optional[float]  # Confidence when auto-detected
    duration: Optional[float]  # Duration of audio processed, in seconds
    task: str  # 'transcribe' or 'translate'
    model: str  # Whisper model size used
    segment_count: int  # Number of subtitle cues
    segments: Optional[List[TranscriptionSegment]]  # Present when include_segments=true
    request_id: str
    generated_at: str  # ISO timestamp
    expires_in: int  # seconds


class AnalyzeMediaRequest(BaseModel):
    url: HttpUrl  # Publicly accessible URL to an audio or video file
    language_codes: Optional[List[str]] = None  # Constrain to these ISO/BCP-47 codes; None = auto-detect
    include_segments: bool = True  # Include per-segment detail in the response
    generate_srt: bool = True  # Also render a speaker/language-labelled .srt file


class AnalyzeSegment(BaseModel):
    start: float  # Segment start time in seconds
    end: float  # Segment end time in seconds
    speaker: str  # Diarized speaker label, e.g. 'Speaker 1'
    language: str  # Detected language (ISO 639-1), e.g. 'en', 'ar', or 'unknown'
    text: str


class MediaShift(BaseModel):
    # 'from' is a Python keyword, so the field is named from_ and aliased to
    # 'from' for both input (compute_shifts emits 'from') and output.
    model_config = ConfigDict(populate_by_name=True)

    at: float  # Time of the shift in seconds (segment boundary)
    type: str  # 'speaker' or 'language'
    from_: str = Field(alias="from")  # Previous speaker/language
    to: str  # New speaker/language


class AnalyzeMediaResponse(BaseModel):
    languages_detected: List[str]  # All languages detected across the media
    speakers_detected: List[str]  # All speaker labels detected
    segments: Optional[List[AnalyzeSegment]]  # Present when include_segments=true
    shifts: List[MediaShift]  # Speaker/language change points
    transcript_text: str  # Full transcript (all segments joined)
    srt_url: Optional[str]  # URL to the speaker/language-labelled .srt (when generate_srt=true)
    source_type: str  # 'audio' or 'video'
    duration: Optional[float]  # Audio duration in seconds, if available
    model: str  # Gemini model used
    request_id: str
    generated_at: str  # ISO timestamp
    expires_in: int  # seconds


class GoogleSerpRequest(BaseModel):
    query: str  # Required: search query
    num_results: int = 10  # Results per page: 10, 20, 30, 50, or 100
    page: int = 1  # Page number (1-10)
    language: str = "en"  # Language code
    show_raw: bool = False  # Include raw HTML of result containers for debugging
    capture: bool = False  # Capture screenshot of the search results page


class OrganicResult(BaseModel):
    position: int
    title: str
    url: str
    display_url: str
    snippet: str


class RawContainer(BaseModel):
    index: int
    html: str
    parsed: bool  # Whether this container was successfully parsed
    skip_reason: Optional[str] = None  # Why it was skipped (if not parsed)
    has_h3: Optional[bool] = None  # Debug: Does it have h3 tag
    has_url: Optional[bool] = None  # Debug: Does it have URL


class GoogleSerpResponse(BaseModel):
    query: str
    page: int
    total_results: Optional[str]  # "About X results"
    total_results_count: Optional[int]  # Numeric count extracted from total_results
    total_pages: Optional[int]  # Estimated total pages (total_results_count / num_results)
    organic_results: List[OrganicResult]
    results_count: int  # Number of results returned
    request_id: str
    scraped_at: str  # ISO timestamp
    raw_containers: Optional[List[RawContainer]] = None  # Raw HTML when show_raw=true
    screenshot_url: Optional[str] = None  # Screenshot URL when capture=true
    page_source_url: Optional[str] = None  # Page source URL when capture=true
    debug_id: Optional[str] = None  # Debug session ID when capture=true
