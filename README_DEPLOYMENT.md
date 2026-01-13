# Cloud Sekureid - Complete Deployment Guide

This README covers everything needed to deploy and maintain the cloud-sekureid application.

## Quick Reference

| File | Purpose |
|------|---------|
| `api_server.py` | FastAPI server with all endpoints |
| `requirements.txt` | Python dependencies (including pytesseract) |
| `Dockerfile` | Docker image build configuration |
| `docker-compose.yml` | Container orchestration and Tesseract mounts |
| `TESSERACT_SETUP.md` | Install Tesseract on Ubuntu host |
| `DEPLOYMENT_SCRIPT_SETUP.md` | Configure your update script |
| `DEPLOYMENT.md` | Day-to-day deployment & maintenance |
| `LOCAL_BUILD_INSTRUCTIONS.md` | Manual local build steps |

## Architecture Overview

```
Your Ubuntu Server
├── Tesseract OCR (installed via apt)
│   ├── /usr/bin/tesseract
│   ├── /usr/share/tesseract-ocr/
│   └── Shared libraries
│
└── Docker Container (cloud-sekureid)
    ├── Python 3.11
    ├── FastAPI application
    ├── Chromium browser
    ├── Image processing libs
    └── MOUNTS Tesseract from host (read-only)
```

**Key Benefit**: Tesseract is on the host, not in the Docker image → smaller image, faster builds

## Deployment Methods

### Method 1: Using Your Update Script (Recommended)

```bash
cd /path/to/cloud-sekureid
./update.sh
```

This:
1. Pulls latest code from Git
2. Builds Docker image locally
3. Restarts containers
4. Takes ~2-5 minutes first time, 30-60 seconds after

**Setup**: See `DEPLOYMENT_SCRIPT_SETUP.md`

### Method 2: Manual Docker Compose

```bash
cd /path/to/cloud-sekureid

# Update code
git pull origin main

# Build image
docker-compose build --no-cache

# Restart
docker-compose down
docker-compose up -d
```

### Method 3: Manual with Docker Commands

```bash
cd /path/to/cloud-sekureid
docker build -t cloud-sekureid:latest .
docker compose -p cloud-sekureid down
docker compose -p cloud-sekureid up -d
```

## Initial Setup (One-time)

### 1. Install Tesseract on Ubuntu Host

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng
tesseract --version  # Verify
```

See `TESSERACT_SETUP.md` for details.

### 2. Create Deployment Directory

```bash
mkdir -p /home/ubuntu/deployments/cloud-sekureid
cd /home/ubuntu/deployments/cloud-sekureid
git clone https://github.com/octacer/cloud_sekureid.git repo
```

### 3. Configure Update Script

```bash
# Create config files
echo "1" > deployment_type.txt
echo "." > docker_context.txt

# Copy your update.sh (or use the template in DEPLOYMENT_SCRIPT_SETUP.md)
cp /path/to/your/update.sh .
chmod +x update.sh
```

### 4. First Deployment

```bash
cd /path/to/cloud-sekureid
docker-compose build --no-cache
docker-compose up -d

# Verify
curl http://localhost:3003/health
```

## Configuration

### Environment Variables (in docker-compose.yml)

```yaml
environment:
  - SEKUREID_COMPANY_CODE=85
  - SEKUREID_USERNAME=hisham.octacer
  - SEKUREID_PASSWORD=P@ss1234
  - BASE_DOMAIN=https://sekureid.octacer.info
```

### Port Mapping

- Default: `3003:8000` (host:container)
- Change in `docker-compose.yml` if needed

### Resource Limits

```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 2G
    reservations:
      cpus: '1'
      memory: 1G
```

## Available Endpoints

### Report Generation
- `GET /get-report-default` - Generate today's report
- `POST /generate-report` - Generate report with custom params
- `GET /download/{file_id}` - Download generated report

### New: Text Extraction (OCR)
- `POST /extract-text` - Extract text from image/PDF via URL

### Utilities
- `POST /pdf-to-png` - Convert PDF to PNG images
- `GET /get-vollna-cookies` - Extract Vollna cookies

### System
- `GET /health` - Health check
- `GET /` - API info
- `GET /debug` - List debug sessions

## Testing the New Text Extraction Feature

```bash
# Test with PDF
curl -X POST http://localhost:3003/extract-text \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
  }'

# Response includes:
# - Extracted text
# - Language detected (eng)
# - Extraction method (Tesseract OCR)
# - Source type (pdf/image)
# - Total pages (for PDFs)
# - Timestamp and request ID
```

## Monitoring

### Check Status

```bash
# Running containers
docker ps | grep cloud-sekureid

# Container logs (real-time)
docker-compose logs -f app

# Last 100 lines
docker-compose logs app --tail=100

# Since 1 hour ago
docker-compose logs app --since 1h
```

### Health Checks

```bash
# Health endpoint
curl http://localhost:3003/health

# Full API info
curl http://localhost:3003/

# List all endpoints
curl http://localhost:3003/ | jq '.endpoints'
```

## Maintenance

### Regular Tasks

```bash
# View logs periodically
docker-compose logs app

# Check disk space
df -h

# Monitor resource usage
docker stats cloud-sekureid
```

### Stopping/Starting

```bash
# Stop services
docker-compose down

# Start services
docker-compose up -d

# Restart services
docker-compose restart

# Restart specific service
docker-compose restart app
```

### Updating

```bash
# Update code and restart
./update.sh

# Or manually
git pull origin main
docker-compose build --no-cache
docker-compose down
docker-compose up -d
```

### Cleaning Up

```bash
# Remove stopped containers
docker container prune

# Remove unused images
docker image prune

# Remove all images (will rebuild)
docker rmi cloud-sekureid:latest

# Clean old reports (optional)
rm -rf ./sekureId_downloads/*
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs app

# Restart Docker
sudo systemctl restart docker
docker-compose up -d

# Check Tesseract access
docker exec cloud-sekureid tesseract --version
```

### Text extraction not working

```bash
# Verify Tesseract on host
tesseract --version
which tesseract

# Verify in container
docker exec cloud-sekureid tesseract --version

# Check mounts
docker exec cloud-sekureid ls -la /usr/bin/tesseract
```

### Port 3003 in use

```bash
# Find what's using it
sudo lsof -i :3003

# Kill the process or change port in docker-compose.yml
docker-compose down
docker-compose up -d
```

### Out of disk space

```bash
# Check usage
df -h

# Clean Docker
docker system prune -a

# Clean old downloads
rm -rf ./sekureId_downloads/*
```

## File Locations on Server

```
/path/to/cloud-sekureid/
├── api_server.py              # FastAPI server
├── sekureid_automation.py      # Report generation
├── vollna_automation.py        # Vollna integration
├── requirements.txt            # Python packages
├── Dockerfile                  # Image definition
├── docker-compose.yml          # Container config
├── deployment_type.txt         # Config: 1 (local build)
├── docker_context.txt          # Config: . (current dir)
├── sekureId_downloads/         # Generated reports
├── sekureId_logs/              # Application logs
└── DEPLOYMENT_SCRIPT_SETUP.md  # (this guide)
```

## Useful Commands

```bash
# View all commands
docker-compose help

# Build image
docker-compose build

# Build without cache
docker-compose build --no-cache

# Start in background
docker-compose up -d

# Start in foreground (see logs)
docker-compose up

# Stop services
docker-compose down

# View logs
docker-compose logs -f app

# Execute command in container
docker exec cloud-sekureid <command>

# Run container shell
docker exec -it cloud-sekureid /bin/bash

# View network
docker network inspect cloud-sekureid_default
```

## Best Practices

✅ **Always pull latest code** before building: `git pull origin main`
✅ **Check logs** after deployment: `docker-compose logs app`
✅ **Test endpoints** after deployment: `curl http://localhost:3003/health`
✅ **Use --no-cache** for first build: `docker-compose build --no-cache`
✅ **Regular backups** of downloads: `tar -czf backup.tar.gz sekureId_downloads/`
✅ **Monitor disk space** regularly: `df -h`
✅ **Keep Tesseract updated**: `sudo apt-get upgrade tesseract-ocr`

## Performance Notes

- **First build**: 5-10 minutes (downloads images, installs packages)
- **Subsequent builds**: 30-60 seconds (uses cache)
- **Startup time**: 10-20 seconds
- **Memory usage**: ~500MB-1GB depending on load
- **Disk usage**: ~2GB for image + data

## Security

✅ Non-root container user
✅ Read-only Tesseract mounts
✅ No credentials in image
✅ No exposed debug ports
✅ Health checks enabled
✅ Resource limits defined

## Support & Documentation

- **Tesseract setup**: See `TESSERACT_SETUP.md`
- **Deployment script**: See `DEPLOYMENT_SCRIPT_SETUP.md`
- **Day-to-day operations**: See `DEPLOYMENT.md`
- **Local building**: See `LOCAL_BUILD_INSTRUCTIONS.md`

## Summary

This project is now set up for **local Docker builds on your Ubuntu server**:

1. Install Tesseract once on the host
2. Git clone the repository
3. Run `./update.sh` whenever you want to deploy
4. Application restarts with latest code

**No more GitHub Actions 502 errors!** ✅

---

**Last Updated**: 2026-01-13
**Version**: 1.0.0
**Status**: Ready for deployment
