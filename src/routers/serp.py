"""Google SERP scraping endpoint."""

import os
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException

from src.config import BASE_DOMAIN
from src.models import GoogleSerpRequest, GoogleSerpResponse
from google_serp_automation import GoogleSerpAutomation

router = APIRouter()


@router.post("/scrape-google-serp", response_model=GoogleSerpResponse)
async def scrape_google_serp(
    request_data: GoogleSerpRequest
):
    """
    Scrape Google Search Engine Results Page (SERP)

    Returns organic search results for a given query

    **Parameters:**
    - **query**: Search query string (required)
    - **num_results**: Number of results per page - must be 10, 20, 30, 50, or 100 (default: 10)
    - **page**: Page number between 1 and 10 (default: 1)
    - **language**: Language code like 'en', 'es', 'fr' (default: 'en')

    **Returns:**
    - JSON with organic search results including position, title, URL, and snippet
    - CAPTCHA detection will return HTTP 429 error

    **Note:** Web scraping Google may violate their Terms of Service.
    This is for educational/research purposes only.
    """
    request_id = str(uuid.uuid4())

    try:
        print(f"\n{'='*80}")
        print(f"Processing Google SERP scraping request")
        print(f"{'='*80}")
        print(f"→ Request ID: {request_id}")
        print(f"→ Query: {request_data.query}")
        print(f"→ Page: {request_data.page}")
        print(f"→ Number of results: {request_data.num_results}")
        print(f"→ Language: {request_data.language}")
        print(f"→ Timestamp: {datetime.now().isoformat()}\n")

        # Input validation
        if not request_data.query or len(request_data.query.strip()) == 0:
            raise HTTPException(
                status_code=400,
                detail="Query parameter is required and cannot be empty"
            )

        if request_data.num_results not in [10, 20, 30, 50, 100]:
            raise HTTPException(
                status_code=400,
                detail="num_results must be one of: 10, 20, 30, 50, 100"
            )

        if request_data.page < 1 or request_data.page > 10:
            raise HTTPException(
                status_code=400,
                detail="page must be between 1 and 10"
            )

        # Create debug directory if capture is enabled
        debug_dir = None
        debug_id = None
        if request_data.capture:
            debug_id = f"serp_{request_id[:8]}"
            debug_dir = os.path.join("downloads", f"debug_{debug_id}")
            os.makedirs(debug_dir, exist_ok=True)
            print(f"→ Debug directory created: {debug_dir}")

        # Initialize automation
        print("→ Initializing Google SERP automation...")
        automation = GoogleSerpAutomation()

        # Scrape SERP
        print("→ Starting SERP scraping...")
        serp_data = automation.scrape_serp(
            query=request_data.query,
            page=request_data.page,
            num_results=request_data.num_results,
            language=request_data.language,
            show_raw=request_data.show_raw,
            capture=request_data.capture,
            debug_dir=debug_dir
        )

        # Check for CAPTCHA (fail fast)
        if serp_data.get("captcha_detected"):
            print("\n{'='*80}")
            print("✗ CAPTCHA DETECTED")
            print(f"{'='*80}")
            print(f"→ Request ID: {request_id}")
            print(f"→ Query: {request_data.query}")
            print(f"→ Google has detected automated access")
            print(f"{'='*80}\n")

            raise HTTPException(
                status_code=429,
                detail="Google CAPTCHA detected. Please try again later or reduce request frequency."
            )

        scraped_at = datetime.now()

        # Calculate total pages
        total_results_count = serp_data.get("total_results_count")
        total_pages = None
        if total_results_count:
            import math
            total_pages = math.ceil(total_results_count / request_data.num_results)

        # Build screenshot URLs if captured
        screenshot_url = None
        page_source_url = None
        if request_data.capture and debug_id:
            if serp_data.get("screenshot_path"):
                screenshot_url = f"{BASE_DOMAIN}/files/debug_{debug_id}/serp_screenshot.png"
            if serp_data.get("page_source_path"):
                page_source_url = f"{BASE_DOMAIN}/files/debug_{debug_id}/serp_page_source.html"

        # Build response
        response = GoogleSerpResponse(
            query=request_data.query,
            page=request_data.page,
            total_results=serp_data.get("total_results"),
            total_results_count=total_results_count,
            total_pages=total_pages,
            organic_results=serp_data.get("organic_results", []),
            results_count=len(serp_data.get("organic_results", [])),
            request_id=request_id,
            scraped_at=scraped_at.isoformat(),
            raw_containers=serp_data.get("raw_containers") if request_data.show_raw else None,
            screenshot_url=screenshot_url,
            page_source_url=page_source_url,
            debug_id=debug_id
        )

        print(f"\n{'='*80}")
        print(f"✓ SERP scraping completed successfully")
        print(f"{'='*80}")
        print(f"→ Request ID: {request_id}")
        print(f"→ Query: {request_data.query}")
        print(f"→ Results found: {response.results_count}")
        print(f"→ Total results: {response.total_results}")
        print(f"→ Total pages: {response.total_pages}")
        if request_data.capture and screenshot_url:
            print(f"→ Screenshot: {screenshot_url}")
            print(f"→ Page source: {page_source_url}")
            print(f"→ Debug ID: {debug_id}")
        print(f"→ Response timestamp: {scraped_at.isoformat()}")
        print(f"{'='*80}\n")

        return response

    except HTTPException:
        raise

    except Exception as e:
        print(f"\n{'='*80}")
        print(f"✗ ERROR in Google SERP scraping")
        print(f"{'='*80}")
        print(f"→ Request ID: {request_id}")
        print(f"→ Query: {request_data.query if hasattr(request_data, 'query') else 'N/A'}")
        print(f"→ Error type: {type(e).__name__}")
        print(f"→ Error message: {str(e)}")
        print(f"→ Timestamp: {datetime.now().isoformat()}")
        print(f"{'='*80}\n")

        raise HTTPException(
            status_code=500,
            detail=f"Failed to scrape Google SERP: {str(e)}"
        )
