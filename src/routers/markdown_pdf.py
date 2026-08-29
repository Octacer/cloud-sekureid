"""Markdown-to-PDF conversion endpoint.

Renders Markdown to a styled PDF, with an optional Octacer-branded layout
(header logo/wordmark, page-numbered footer, brand-coloured typography) and an
optional diagonal watermark.

Engine: Markdown -> HTML (pure-Python ``markdown``) -> PDF via headless
Chromium's DevTools ``Page.printToPDF``. Chromium + chromium-driver already
ship in the container image (used by the SERP/Vollna endpoints), so this adds
no new system dependency — only the ``markdown`` package. Using Chrome gives
full CSS fidelity plus native running headers/footers with ``pageNumber`` /
``totalPages`` placeholders.
"""

import os
import re
import base64
import shutil
import uuid
import time
from pathlib import Path
from string import Template
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
import requests
import markdown as md
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from src.config import DOWNLOADS_DIR, BASE_DOMAIN
from src.helpers import cleanup_directory
from src.models import MarkdownToPdfRequest, MarkdownToPdfResponse

router = APIRouter()

# Paper dimensions in inches (portrait), keyed by lowercase name.
PAGE_SIZES = {
    "a4": (8.27, 11.69),
    "letter": (8.5, 11.0),
    "legal": (8.5, 14.0),
}

# Markdown extensions: 'extra' bundles tables, fenced code, footnotes, etc.
MD_EXTENSIONS = ["extra", "sane_lists", "toc", "admonition", "nl2br"]


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _slugify(text: str, default: str = "document") -> str:
    """Turn an arbitrary string into a safe filename stem."""
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:60] or default


def _hex_to_rgb(hex_color: str):
    """Parse '#RRGGBB' / 'RRGGBB' / '#RGB' into an (r, g, b) tuple.

    Falls back to the default brand blue on anything unparseable so a bad
    ``brand_color`` never breaks rendering.
    """
    value = (hex_color or "").strip().lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    try:
        r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
        return r, g, b
    except (ValueError, IndexError):
        return 11, 92, 173  # #0B5CAD


def _fetch_markdown(url: str) -> str:
    """Fetch raw markdown text from a URL (raises requests.RequestException)."""
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    # Prefer the server-declared encoding; fall back to UTF-8.
    response.encoding = response.encoding or "utf-8"
    return response.text


def _fetch_logo_data_uri(url: str) -> Optional[str]:
    """Download a logo and return it as a base64 ``data:`` URI.

    Returns None on any failure — the header simply falls back to the wordmark,
    so a broken logo URL never fails the whole request.
    """
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if not content_type.startswith("image/"):
            ext = os.path.splitext(url.split("?")[0])[1].lstrip(".").lower()
            content_type = f"image/{ext}" if ext in ("png", "jpeg", "jpg", "gif", "webp", "svg+xml") else "image/png"
        encoded = base64.b64encode(response.content).decode("ascii")
        return f"data:{content_type};base64,{encoded}"
    except Exception as logo_error:  # pragma: no cover - network dependent
        print(f"Could not fetch logo ({url}): {logo_error}")
        return None


# ---------------------------------------------------------------------------
# HTML / CSS assembly
# ---------------------------------------------------------------------------

_CSS = Template("""
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font-family: -apple-system, 'Liberation Sans', 'Segoe UI', Arial, sans-serif;
  font-size: 11pt; line-height: 1.55; color: #1a1a1a;
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
.content { padding: 2mm 0 0; }
h1, h2, h3, h4, h5, h6 { color: ${heading}; line-height: 1.25; margin: 1.2em 0 0.5em; font-weight: 700; }
h1 { font-size: 22pt; border-bottom: 2px solid ${rule}; padding-bottom: 0.2em; }
h2 { font-size: 17pt; border-bottom: 1px solid ${ruleLight}; padding-bottom: 0.15em; }
h3 { font-size: 14pt; }
h4 { font-size: 12pt; }
p { margin: 0.6em 0; }
a { color: ${link}; text-decoration: none; }
ul, ol { margin: 0.5em 0 0.5em 1.4em; padding: 0; }
li { margin: 0.25em 0; }
blockquote { margin: 0.8em 0; padding: 0.4em 1em; border-left: 4px solid ${accent}; background: ${accentTint}; color: #333; }
code { font-family: 'Liberation Mono', 'Courier New', monospace; font-size: 9.5pt; background: #f2f4f7; padding: 1px 4px; border-radius: 3px; }
pre { background: #f6f8fa; border: 1px solid #e2e6ea; border-radius: 6px; padding: 12px; overflow: auto; page-break-inside: avoid; }
pre code { background: none; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 0.8em 0; font-size: 10pt; page-break-inside: avoid; }
th, td { border: 1px solid #d0d7de; padding: 6px 10px; text-align: left; vertical-align: top; }
th { background: ${accentTint}; color: ${heading}; font-weight: 700; }
tr:nth-child(even) td { background: #fafbfc; }
img { max-width: 100%; }
hr { border: 0; border-top: 1px solid ${ruleLight}; margin: 1.2em 0; }
.watermark {
  position: fixed; top: 50%; left: 50%;
  transform: translate(-50%, -50%) rotate(-45deg);
  font-size: 110px; font-weight: 800; letter-spacing: 10px;
  color: rgba(120, 120, 120, 0.16); z-index: 9999;
  pointer-events: none; white-space: nowrap; text-transform: uppercase;
}
""")


def _build_css(req: MarkdownToPdfRequest) -> str:
    """Compose the stylesheet, deriving accent tints from the brand colour."""
    if req.branding:
        r, g, b = _hex_to_rgb(req.brand_color)
        subs = {
            "heading": req.brand_color,
            "rule": req.brand_color,
            "ruleLight": f"rgba({r}, {g}, {b}, 0.35)",
            "link": req.brand_color,
            "accent": req.brand_color,
            "accentTint": f"rgba({r}, {g}, {b}, 0.08)",
        }
    else:
        # Neutral, un-branded styling.
        subs = {
            "heading": "#111827",
            "rule": "#111827",
            "ruleLight": "#d0d7de",
            "link": "#0b5cad",
            "accent": "#6b7280",
            "accentTint": "#f3f4f6",
        }
    return _CSS.substitute(subs)


def _build_html(body_html: str, req: MarkdownToPdfRequest) -> str:
    """Wrap rendered markdown in a full HTML document."""
    title = (req.title or "Document").strip()
    watermark_html = ""
    if req.watermark and req.watermark.strip():
        # markdown() already escaped nothing here; escape the watermark text.
        safe = (req.watermark.strip()
                .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        watermark_html = f'<div class="watermark">{safe}</div>'
    safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en"><head><meta charset="utf-8">\n'
        f"<title>{safe_title}</title>\n"
        f"<style>{_build_css(req)}</style>\n"
        "</head><body>\n"
        f"{watermark_html}\n"
        f'<main class="content">{body_html}</main>\n'
        "</body></html>"
    )


def _header_footer_templates(req: MarkdownToPdfRequest, logo_data_uri: Optional[str]):
    """Build the Chrome header/footer HTML templates (branded mode only).

    Chrome renders these in the page margins on every page. They need inline
    styles (the page stylesheet does not apply) and support the special
    ``pageNumber`` / ``totalPages`` classes which Chrome fills in.
    """
    company = (req.company_name or "Octacer").strip()
    company_esc = company.replace("&", "&amp;").replace("<", "&lt;")
    title_esc = (req.title or "").strip().replace("&", "&amp;").replace("<", "&lt;")

    if logo_data_uri:
        brand_block = (
            f'<img src="{logo_data_uri}" style="height:22px; margin-right:8px; vertical-align:middle;"/>'
            f'<span style="font-size:11px; font-weight:700; color:{req.brand_color}; vertical-align:middle;">{company_esc}</span>'
        )
    else:
        brand_block = f'<span style="font-size:12px; font-weight:700; color:{req.brand_color};">{company_esc}</span>'

    header = (
        '<div style="font-size:9px; width:100%; box-sizing:border-box; '
        'padding:3px 14mm 0; color:#666; -webkit-print-color-adjust:exact; '
        'display:flex; align-items:center; justify-content:space-between;">'
        f'<div style="display:flex; align-items:center;">{brand_block}</div>'
        f'<div style="text-align:right;">{title_esc}</div>'
        "</div>"
    )

    footer_left = (req.footer_text or company).strip()
    footer_left_esc = footer_left.replace("&", "&amp;").replace("<", "&lt;")
    page_block = (
        'Page <span class="pageNumber"></span> of <span class="totalPages"></span>'
        if req.show_page_numbers else ""
    )
    footer = (
        '<div style="font-size:9px; width:100%; box-sizing:border-box; '
        'padding:0 14mm 3px; color:#888; -webkit-print-color-adjust:exact; '
        'display:flex; align-items:center; justify-content:space-between;">'
        f'<div>{footer_left_esc}</div>'
        f'<div>{page_block}</div>'
        "</div>"
    )
    return header, footer


# ---------------------------------------------------------------------------
# Headless-Chrome rendering
# ---------------------------------------------------------------------------

def _build_driver():
    """Start a headless Chromium suited to server/container environments."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-extensions")
    options.add_argument("--hide-scrollbars")
    options.add_argument("--window-size=1200,1600")
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(60)
    return driver


def _render_pdf(html_path: str, req: MarkdownToPdfRequest,
                logo_data_uri: Optional[str]) -> bytes:
    """Load the HTML in Chrome and return printed PDF bytes via CDP."""
    width, height = PAGE_SIZES[req.page_size.lower()]

    params = {
        "landscape": req.orientation.lower() == "landscape",
        "printBackground": True,
        "paperWidth": width,
        "paperHeight": height,
        "marginLeft": 0.6,
        "marginRight": 0.6,
        "preferCSSPageSize": False,
    }

    if req.branding:
        header, footer = _header_footer_templates(req, logo_data_uri)
        params.update({
            "displayHeaderFooter": True,
            "headerTemplate": header,
            "footerTemplate": footer,
            "marginTop": 0.75,
            "marginBottom": 0.6,
        })
    else:
        params.update({
            "displayHeaderFooter": False,
            "headerTemplate": "<span></span>",
            "footerTemplate": "<span></span>",
            "marginTop": 0.55,
            "marginBottom": 0.55,
        })

    driver = _build_driver()
    try:
        driver.get(Path(html_path).as_uri())
        # Give remote images / web fonts a brief moment to settle.
        time.sleep(0.4)
        result = driver.execute_cdp_cmd("Page.printToPDF", params)
        return base64.b64decode(result["data"])
    finally:
        driver.quit()


def _count_pdf_pages(pdf_path: str) -> Optional[int]:
    """Best-effort page count via poppler's pdfinfo; None if unavailable."""
    try:
        from pdf2image import pdfinfo_from_path
        info = pdfinfo_from_path(pdf_path)
        return int(info.get("Pages")) if info.get("Pages") is not None else None
    except Exception as info_error:  # pragma: no cover - depends on poppler
        print(f"Could not determine page count: {info_error}")
        return None


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/markdown-to-pdf", response_model=MarkdownToPdfResponse)
async def markdown_to_pdf(
    request_data: MarkdownToPdfRequest,
    background_tasks: BackgroundTasks
):
    """
    Convert Markdown to a styled PDF.

    Provide the content as either raw `markdown` text or a `markdown_url`
    (exactly one). The output can be Octacer-branded or plain.

    **Input (exactly one):**
    - **markdown**: Raw markdown text
    - **markdown_url**: Public URL to a `.md` file

    **Document options:**
    - **title**: Document title (header, PDF metadata, and default filename)
    - **page_size**: `A4` (default), `Letter`, or `Legal`
    - **orientation**: `portrait` (default) or `landscape`
    - **filename**: Desired output filename

    **Branding** (`branding: true` by default):
    - **company_name**: Header wordmark (default: `Octacer`)
    - **logo_url**: Optional header logo image (falls back to the wordmark)
    - **brand_color**: Accent hex colour for headings/links/rules (default: `#0B5CAD`)
    - **footer_text**: Left-side footer text (default: company name)
    - **show_page_numbers**: `Page X of Y` in the footer (default: true)

    Set `branding: false` for a clean, neutral-styled PDF with no header/footer.

    **Watermark** (independent of branding, off unless set):
    - **watermark**: Faint diagonal text, e.g. `CONFIDENTIAL`

    **Returns:** JSON with a URL to the generated PDF (valid for 1 hour).
    """
    request_id = str(uuid.uuid4())

    # --- Validate input ------------------------------------------------------
    has_text = bool(request_data.markdown and request_data.markdown.strip())
    has_url = bool(request_data.markdown_url)
    if has_text == has_url:
        raise HTTPException(
            status_code=400,
            detail="Provide exactly one of 'markdown' (text) or 'markdown_url'."
        )

    page_size = (request_data.page_size or "A4").lower()
    if page_size not in PAGE_SIZES:
        raise HTTPException(
            status_code=400,
            detail=f"page_size must be one of: {', '.join(sorted(s.upper() for s in PAGE_SIZES))}"
        )

    orientation = (request_data.orientation or "portrait").lower()
    if orientation not in ("portrait", "landscape"):
        raise HTTPException(status_code=400, detail="orientation must be 'portrait' or 'landscape'")

    work_dir = os.path.join(DOWNLOADS_DIR, f"md_{request_id}")
    os.makedirs(work_dir, exist_ok=True)

    try:
        print(f"[{request_id}] Markdown-to-PDF: branding={request_data.branding} "
              f"size={page_size} orientation={orientation}")

        # --- Resolve markdown source ----------------------------------------
        if has_url:
            print(f"[{request_id}] Fetching markdown: {request_data.markdown_url}")
            markdown_text = _fetch_markdown(str(request_data.markdown_url))
        else:
            markdown_text = request_data.markdown

        if not markdown_text.strip():
            raise HTTPException(status_code=400, detail="Markdown content is empty.")

        # --- Markdown -> HTML -----------------------------------------------
        body_html = md.markdown(markdown_text, extensions=MD_EXTENSIONS, output_format="html5")

        # --- Optional logo for branded header -------------------------------
        logo_data_uri = None
        if request_data.branding and request_data.logo_url:
            logo_data_uri = _fetch_logo_data_uri(str(request_data.logo_url))

        # --- Full HTML document ---------------------------------------------
        html_doc = _build_html(body_html, request_data)
        html_path = os.path.join(work_dir, "input.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_doc)

        # --- Render PDF via headless Chrome ---------------------------------
        print(f"[{request_id}] Rendering PDF via headless Chromium...")
        pdf_bytes = _render_pdf(html_path, request_data, logo_data_uri)

        # --- Persist output --------------------------------------------------
        stem = _slugify(request_data.filename or request_data.title or "document")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_filename = f"{timestamp}_{stem}.pdf"
        out_path = os.path.join(work_dir, out_filename)
        with open(out_path, "wb") as f:
            f.write(pdf_bytes)

        # The HTML is only an intermediate artifact — drop it.
        if os.path.exists(html_path):
            os.remove(html_path)

        size_bytes = os.path.getsize(out_path)
        total_pages = _count_pdf_pages(out_path)
        print(f"[{request_id}] Wrote {out_filename} ({size_bytes} bytes, "
              f"{total_pages} pages)")

        # Schedule cleanup of the whole work dir after 1 hour.
        background_tasks.add_task(cleanup_directory, work_dir, 3600)

        generated_at = datetime.now()
        return MarkdownToPdfResponse(
            url=f"{BASE_DOMAIN}/files/md_{request_id}/{out_filename}",
            filename=out_filename,
            branding=request_data.branding,
            watermarked=bool(request_data.watermark and request_data.watermark.strip()),
            page_size=page_size.upper(),
            orientation=orientation,
            total_pages=total_pages,
            size_bytes=size_bytes,
            request_id=request_id,
            generated_at=generated_at.isoformat(),
            expires_in=3600
        )

    except HTTPException:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise
    except requests.RequestException as e:
        shutil.rmtree(work_dir, ignore_errors=True)
        print(f"[{request_id}] Download error: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to fetch markdown from URL: {str(e)}"
        )
    except Exception as e:
        shutil.rmtree(work_dir, ignore_errors=True)
        print(f"[{request_id}] Conversion error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to convert markdown to PDF: {str(e)}"
        )
