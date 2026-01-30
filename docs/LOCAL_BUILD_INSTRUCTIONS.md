# Local Build Instructions

Since GitHub Container Registry has connectivity issues, we've switched to **local builds on your Ubuntu server**.

## Why This Approach?

✅ **No GitHub Actions timeout issues**
✅ **Tesseract is already on your server**
✅ **Faster iteration and testing**
✅ **Full control over deployment**
✅ **Docker image is smaller**

## Quick Start (Ubuntu Server)

### Step 1: Install Tesseract (One-time)

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng
tesseract --version  # Verify installation
```

### Step 2: Pull Code and Build

```bash
cd /path/to/cloud_sekureid

# Get latest code
git pull origin main

# Build Docker image
docker-compose build --no-cache

# Check it built successfully
docker images | grep cloud-sekureid
```

### Step 3: Start the Application

```bash
# Start services
docker-compose up -d

# Verify it's running
docker-compose ps

# Test it works
curl http://localhost:3003/health
```

### Step 4: Test New Features

```bash
# Test text extraction endpoint
curl -X POST http://localhost:3003/extract-text \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
  }'
```

## GitHub Actions Workflow

When you push code to GitHub:

1. GitHub Actions runs a simple notification job
2. You see a summary of changed files
3. You manually pull and rebuild on your server

**This is intentional** - it gives you full control over deployment timing.

## Updating After Code Changes

```bash
cd /path/to/cloud_sekureid

# 1. Get latest code
git pull origin main

# 2. Rebuild image (only if Dockerfile or requirements.txt changed)
docker-compose build --no-cache

# 3. Restart
docker-compose down
docker-compose up -d

# 4. Verify
curl http://localhost:3003/health
```

## What's Different From GitHub Actions?

| Aspect | GitHub Actions | Local Build |
|--------|---|---|
| **Build location** | ❌ ghcr.io (had 502 errors) | ✅ Your Ubuntu server |
| **Tesseract** | ❌ In Docker image | ✅ Mounted from host |
| **Image size** | Larger | **Smaller** |
| **Update frequency** | Automatic | Manual (controlled) |
| **Debugging** | Harder to debug | Easier to test locally |

## File Structure

```
cloud_sekureid/
├── api_server.py                 # FastAPI server with new /extract-text endpoint
├── requirements.txt              # Python dependencies (includes pytesseract)
├── Dockerfile                    # Docker image (no Tesseract binary, just libs)
├── docker-compose.yml            # Mounts Tesseract from host
├── DEPLOYMENT.md                 # Complete deployment guide
├── TESSERACT_SETUP.md            # Tesseract installation guide
├── LOCAL_BUILD_INSTRUCTIONS.md   # This file
└── .github/workflows/
    └── docker-build.yml          # Simple notification workflow
```

## Environment Variables

In `docker-compose.yml`, you can customize:

```yaml
environment:
  - SEKUREID_COMPANY_CODE=85
  - SEKUREID_USERNAME=hisham.octacer
  - SEKUREID_PASSWORD=P@pass1234
  - BASE_DOMAIN=https://sekureid.octacer.info  # For URLs in responses
```

## Common Commands

```bash
# View real-time logs
docker-compose logs -f app

# Stop services
docker-compose down

# Restart services
docker-compose restart

# View running containers
docker-compose ps

# Execute command in container
docker exec cloud-sekureid tesseract --version

# Rebuild without cache
docker-compose build --no-cache
```

## Monitoring & Maintenance

See `DEPLOYMENT.md` for:
- Health checks
- Log monitoring
- Troubleshooting
- Backup procedures
- Resource tuning

## Testing the New Text Extraction Feature

### Test with PDF URL

```bash
curl -X POST http://localhost:3003/extract-text \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
  }'
```

### Test with Image URL

```bash
curl -X POST http://localhost:3003/extract-text \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/document.png"
  }'
```

### Expected Response

```json
{
  "text": "Extracted text from document...",
  "language": "eng",
  "extraction_method": "Tesseract OCR",
  "source_type": "pdf",
  "total_pages": 5,
  "extracted_at": "2026-01-13T12:34:56.789123",
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

## Issues & Support

### Tesseract command not found

```bash
# Install on host
sudo apt-get install -y tesseract-ocr

# Verify in container
docker exec cloud-sekureid tesseract --version
```

### Docker image still too large

The image should now be **significantly smaller** because Tesseract binary isn't included. If still too large:
- Check disk space: `df -h`
- Clean up old images: `docker image prune -a`
- Check build output: `docker-compose build`

### Can't connect on port 3003

- Change port in `docker-compose.yml`: `"YOUR_PORT:8000"`
- Restart: `docker-compose down && docker-compose up -d`

## Next Steps

1. **Install Tesseract** on your Ubuntu server (see TESSERACT_SETUP.md)
2. **Clone/pull** the repository
3. **Build** the Docker image
4. **Start** services with docker-compose
5. **Test** the endpoints
6. **Monitor** with `docker-compose logs -f app`

You're all set! 🚀
