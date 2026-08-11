"""Image resize / format-conversion endpoint."""

import os
import shutil
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks
import requests
from PIL import Image, ImageOps

from src.config import DOWNLOADS_DIR, BASE_DOMAIN
from src.helpers import download_url_to_file, cleanup_directory
from src.models import ImageResizeRequest, ImageResizeResponse

router = APIRouter()

# Register the HEIF/HEIC opener with Pillow so .heic inputs (iPhone photos)
# can be opened just like PNG/JPEG/WEBP. Optional dependency — if it isn't
# installed the endpoint still handles every other format.
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIC_SUPPORTED = True
except Exception as heif_error:  # pragma: no cover - depends on runtime env
    HEIC_SUPPORTED = False
    print(f"pillow-heif not available, HEIC input disabled: {heif_error}")

# Accepted output formats → canonical PIL format name.
OUTPUT_FORMATS = {
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "png": "PNG",
    "webp": "WEBP",
}
# File extension to write for each canonical PIL format.
EXTENSION_FOR = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}


def _target_size(orig_w, orig_h, width, height, mode):
    """
    Compute the output (width, height).

    - fit:   treat width/height as a bounding box; scale down preserving aspect
             ratio, never upscaling. Missing dimension defaults to the original.
    - exact: force the requested dimensions. If only one is given, the other is
             derived proportionally (so it scales rather than distorts).
    """
    if mode == "fit":
        box_w = width or orig_w
        box_h = height or orig_h
        scale = min(box_w / orig_w, box_h / orig_h, 1.0)  # never upscale
        return max(1, round(orig_w * scale)), max(1, round(orig_h * scale))

    # mode == "exact"
    if width and height:
        return width, height
    if width and not height:
        return width, max(1, round(orig_h * (width / orig_w)))
    if height and not width:
        return max(1, round(orig_w * (height / orig_h))), height
    # Neither provided: keep original.
    return orig_w, orig_h


@router.post("/resize-image", response_model=ImageResizeResponse)
async def resize_image(
    request_data: ImageResizeRequest,
    background_tasks: BackgroundTasks
):
    """
    Resize and/or convert an image.

    Accepts common raster formats (PNG, JPG/JPEG, WEBP, GIF, BMP, TIFF, and
    HEIC/HEIF when pillow-heif is installed) and returns a URL to the converted
    image.

    Parameters:
    - url: Publicly accessible URL to the source image
    - width / height: Target dimensions in pixels (either or both, optional)
    - mode: 'fit' (keep aspect ratio within the box, default) or 'exact'
    - output_format: jpeg | jpg | png | webp (default: jpeg)
    - quality: Encoder quality 1-100 for lossy formats (default: 90)
    """
    request_id = str(uuid.uuid4())
    work_dir = os.path.join(DOWNLOADS_DIR, f"img_{request_id}")
    os.makedirs(work_dir, exist_ok=True)

    # --- Validate parameters -------------------------------------------------
    mode = (request_data.mode or "fit").lower()
    if mode not in ("fit", "exact"):
        shutil.rmtree(work_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="mode must be 'fit' or 'exact'")

    out_key = (request_data.output_format or "jpeg").lower().lstrip(".")
    if out_key not in OUTPUT_FORMATS:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise HTTPException(
            status_code=400,
            detail=f"output_format must be one of: {', '.join(sorted(OUTPUT_FORMATS))}"
        )
    pil_format = OUTPUT_FORMATS[out_key]

    if not 1 <= request_data.quality <= 100:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="quality must be between 1 and 100")

    for dim_name, dim_val in (("width", request_data.width), ("height", request_data.height)):
        if dim_val is not None and dim_val <= 0:
            shutil.rmtree(work_dir, ignore_errors=True)
            raise HTTPException(status_code=400, detail=f"{dim_name} must be a positive integer")

    try:
        print(f"[{request_id}] Resize request: {request_data.url}")

        # --- Download --------------------------------------------------------
        raw_path = os.path.join(work_dir, "source")
        download_url_to_file(str(request_data.url), raw_path, timeout=30)
        print(f"[{request_id}] Downloaded {os.path.getsize(raw_path)} bytes")

        # --- Open & normalize orientation -----------------------------------
        try:
            image = Image.open(raw_path)
            image.load()
        except Exception as open_error:
            raise HTTPException(
                status_code=400,
                detail=f"Could not read image (unsupported or corrupt): {open_error}"
            )

        source_format = image.format  # e.g. 'HEIF', 'PNG', 'JPEG'
        # Respect EXIF orientation (phone photos / HEIC are often rotated).
        image = ImageOps.exif_transpose(image)
        orig_w, orig_h = image.size
        print(f"[{request_id}] Source: {source_format} {orig_w}x{orig_h} mode={image.mode}")

        # --- Resize ----------------------------------------------------------
        new_w, new_h = _target_size(orig_w, orig_h, request_data.width,
                                    request_data.height, mode)
        if (new_w, new_h) != (orig_w, orig_h):
            image = image.resize((new_w, new_h), Image.LANCZOS)
        print(f"[{request_id}] Target: {new_w}x{new_h} (mode={mode})")

        # --- Format-specific conversion -------------------------------------
        save_kwargs = {}
        if pil_format == "JPEG":
            # JPEG has no alpha channel — flatten onto white.
            if image.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", image.size, (255, 255, 255))
                rgba = image.convert("RGBA")
                background.paste(rgba, mask=rgba.split()[-1])
                image = background
            elif image.mode != "RGB":
                image = image.convert("RGB")
            save_kwargs = {"quality": request_data.quality, "optimize": True}
        elif pil_format == "WEBP":
            save_kwargs = {"quality": request_data.quality}
        elif pil_format == "PNG":
            save_kwargs = {"optimize": True}

        # --- Save ------------------------------------------------------------
        extension = EXTENSION_FOR[pil_format]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_filename = f"{timestamp}_{new_w}x{new_h}.{extension}"
        out_path = os.path.join(work_dir, out_filename)
        image.save(out_path, pil_format, **save_kwargs)
        size_bytes = os.path.getsize(out_path)
        print(f"[{request_id}] Saved {pil_format} {size_bytes} bytes -> {out_filename}")

        # Remove the source; keep only the converted output for serving.
        if os.path.exists(raw_path):
            os.remove(raw_path)

        # Schedule cleanup of the whole work dir after 1 hour.
        background_tasks.add_task(cleanup_directory, work_dir, 3600)

        generated_at = datetime.now()
        return ImageResizeResponse(
            url=f"{BASE_DOMAIN}/files/img_{request_id}/{out_filename}",
            filename=out_filename,
            source_format=source_format,
            output_format=pil_format,
            original_width=orig_w,
            original_height=orig_h,
            new_width=new_w,
            new_height=new_h,
            size_bytes=size_bytes,
            mode=mode,
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
            detail=f"Failed to download image from URL: {str(e)}"
        )
    except Exception as e:
        shutil.rmtree(work_dir, ignore_errors=True)
        print(f"[{request_id}] Resize error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to resize image: {str(e)}"
        )
