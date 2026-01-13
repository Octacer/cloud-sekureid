# Tesseract OCR Setup Guide

This document explains how to set up Tesseract OCR on your Ubuntu server and mount it into the Docker container.

## Prerequisites

- Ubuntu 20.04 or later
- Docker and Docker Compose installed
- Root or sudo access

## Installation Steps

### 1. Install Tesseract on Ubuntu Host

```bash
# Update package manager
sudo apt-get update

# Install Tesseract OCR with English language data
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng

# Verify installation
tesseract --version
```

### 2. Verify Library Paths

The docker-compose.yml mounts these files from your host:

```bash
# Check if Tesseract binary exists
ls -la /usr/bin/tesseract

# Check if language data exists
ls -la /usr/share/tesseract-ocr/

# Check required libraries
ls -la /usr/lib/x86_64-linux-gnu/libtesseract.so.5
ls -la /usr/lib/x86_64-linux-gnu/liblept.so.5
```

If any files don't exist, they may be in a different location. Run:

```bash
# Find Tesseract files
find /usr -name "tesseract*" 2>/dev/null
find /usr -name "libtesseract*" 2>/dev/null
find /usr -name "liblept*" 2>/dev/null
```

Then update the mount paths in `docker-compose.yml` accordingly.

### 3. Install Runtime Libraries in Container

The Dockerfile includes the minimal Tesseract runtime libraries:
- `libtesseract5` - Tesseract runtime library
- `libleptonica-dev` - Leptonica image processing library

These will be installed during the Docker build.

### 4. Build and Run the Container

```bash
# Build the image (smaller now, no Tesseract included)
docker-compose build --no-cache

# Run the container
docker-compose up -d

# Verify Tesseract is accessible in the container
docker exec cloud-sekureid tesseract --version

# Test OCR endpoint
curl -X POST "http://localhost:3003/extract-text" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"}'
```

## How It Works

### Mount Configuration

The `docker-compose.yml` mounts:

1. **Tesseract binary**: `/usr/bin/tesseract` → `/usr/bin/tesseract`
2. **Language data**: `/usr/share/tesseract-ocr` → `/usr/share/tesseract-ocr`
3. **Required libraries**: Tesseract and Leptonica shared objects

All mounts are **read-only** (`:ro`) for security.

### Benefits

✅ **Smaller Docker image** - No Tesseract binaries in image (~500MB+ saved)
✅ **Faster builds** - Quicker GitHub Actions builds
✅ **Easy updates** - Update Tesseract on host without rebuilding image
✅ **Shared resources** - Host and container share the same Tesseract installation
✅ **Security** - Read-only mounts prevent accidental modifications

## Troubleshooting

### Error: "tesseract: command not found"

Make sure Tesseract is installed on the Ubuntu host:
```bash
sudo apt-get install -y tesseract-ocr
```

### Error: "cannot open shared object file"

The library paths may differ on your system. Find the correct paths:
```bash
find /usr/lib -name "libtesseract*"
find /usr/lib -name "liblept*"
```

Update `docker-compose.yml` with the correct paths.

### Error: "No language data found"

Ensure language data is installed:
```bash
sudo apt-get install -y tesseract-ocr-eng
ls /usr/share/tesseract-ocr/tessdata/
```

### Container can't access mounted files

Check file permissions:
```bash
ls -la /usr/bin/tesseract
ls -la /usr/share/tesseract-ocr/
```

Files should be readable by your user.

## Adding More Languages

To add support for additional languages (e.g., Spanish, French):

```bash
# Install language packs on host
sudo apt-get install -y tesseract-ocr-spa tesseract-ocr-fra

# Verify installation
ls /usr/share/tesseract-ocr/tessdata/
```

The container will automatically have access to newly installed languages via the mount.

## API Usage

Once set up, use the `/extract-text` endpoint:

```bash
# Extract text from PDF
curl -X POST "http://localhost:3003/extract-text" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/document.pdf"
  }'

# Response
{
  "text": "Extracted text...",
  "language": "eng",
  "extraction_method": "Tesseract OCR",
  "source_type": "pdf",
  "total_pages": 5,
  "extracted_at": "2026-01-13T12:34:56.789123",
  "request_id": "uuid-string"
}
```

## Notes

- Tesseract installation on host is a one-time setup
- The Docker image size is significantly reduced
- Docker builds will be much faster
- No Tesseract updates needed in the Docker image; host updates automatically apply
