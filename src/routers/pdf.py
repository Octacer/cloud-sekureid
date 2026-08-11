"""PDF-to-PNG conversion endpoint."""

import os
import shutil
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks
import requests
from pdf2image import convert_from_path

from src.config import PDF_TEMP_DIR, DOWNLOADS_DIR, BASE_DOMAIN
from src.helpers import download_url_to_file, cleanup_directory
from src.models import PdfToImageRequest, PdfToImageResponse, ImageInfo

router = APIRouter()


@router.post("/pdf-to-png", response_model=PdfToImageResponse)
async def pdf_to_png(
    request: PdfToImageRequest,
    background_tasks: BackgroundTasks
):
    """
    Convert PDF to PNG images

    Parameters:
    - pdf_url: Publicly accessible URL to the PDF file

    Returns:
    - JSON with list of PNG image URLs, one per page
    """
    conversion_id = str(uuid.uuid4())
    temp_pdf_dir = os.path.join(PDF_TEMP_DIR, conversion_id)
    os.makedirs(temp_pdf_dir, exist_ok=True)

    try:
        print(f"Processing PDF conversion request: {conversion_id}")
        print(f"→ PDF URL: {request.pdf_url}")

        # Download PDF file
        pdf_path = os.path.join(temp_pdf_dir, "input.pdf")
        print(f"→ Downloading PDF...")

        download_url_to_file(str(request.pdf_url), pdf_path, timeout=30)

        print(f"→ PDF downloaded: {os.path.getsize(pdf_path)} bytes")

        # Convert PDF to images
        print(f"→ Converting PDF to PNG images...")
        images = convert_from_path(
            pdf_path,
            dpi=200,  # High quality
            fmt='png'
        )

        total_pages = len(images)
        print(f"→ Converted {total_pages} pages")

        # Save images to downloads directory
        conversion_dir = os.path.join(DOWNLOADS_DIR, f"pdf_{conversion_id}")
        os.makedirs(conversion_dir, exist_ok=True)

        image_list = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for i, image in enumerate(images, start=1):
            image_filename = f"{timestamp}_page_{i}.png"
            image_path = os.path.join(conversion_dir, image_filename)
            image.save(image_path, 'PNG')

            image_url = f"{BASE_DOMAIN}/files/pdf_{conversion_id}/{image_filename}"
            image_list.append(ImageInfo(
                page=i,
                url=image_url,
                filename=image_filename
            ))
            print(f"→ Saved page {i}/{total_pages}: {image_filename}")

        # Cleanup temp directory
        shutil.rmtree(temp_pdf_dir, ignore_errors=True)

        # Schedule cleanup after 1 hour
        background_tasks.add_task(cleanup_directory, conversion_dir, 3600)

        generated_at = datetime.now()

        print(f"→ Conversion complete: {conversion_id}\n")

        return PdfToImageResponse(
            images=image_list,
            total_pages=total_pages,
            conversion_id=conversion_id,
            generated_at=generated_at.isoformat(),
            expires_in=3600  # 1 hour
        )

    except requests.RequestException as e:
        # Cleanup temp directory
        shutil.rmtree(temp_pdf_dir, ignore_errors=True)
        print(f"Error downloading PDF: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to download PDF from URL: {str(e)}"
        )

    except Exception as e:
        # Cleanup temp directory
        shutil.rmtree(temp_pdf_dir, ignore_errors=True)
        print(f"Error converting PDF: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to convert PDF to PNG: {str(e)}"
        )
