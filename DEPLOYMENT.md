# Deployment Guide

This guide explains how to deploy the cloud-sekureid application on your Ubuntu server.

## Prerequisites

- Ubuntu 20.04 or later
- Docker and Docker Compose installed
- Git installed
- Tesseract OCR installed (see `TESSERACT_SETUP.md`)
- SSH access to your server

## Setup (One-time)

### 1. Install Tesseract on Ubuntu Host

See `TESSERACT_SETUP.md` for complete instructions:

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng

# Verify
tesseract --version
```

### 2. Clone or Update Repository

```bash
# Clone (if first time)
git clone https://github.com/octacer/cloud_sekureid.git
cd cloud_sekureid

# Or update (if already cloned)
cd /path/to/cloud_sekureid
git pull origin main
```

### 3. Build Docker Image

```bash
# Build the image (includes Tesseract runtime libraries)
docker-compose build --no-cache

# This will:
# - Download base Python image
# - Install system dependencies (Chromium, poppler, etc.)
# - Install Python packages from requirements.txt
# - Create non-root user
# Note: Tesseract binary is mounted from host, not included in image
```

### 4. Start Services

```bash
# Start the application
docker-compose up -d

# Verify it's running
docker-compose ps

# Check logs
docker-compose logs -f app
```

### 5. Test the Application

```bash
# Test health endpoint
curl http://localhost:3003/health

# Expected response:
# {"status":"healthy","timestamp":"2026-01-13T..."}

# Test Tesseract access
docker exec cloud-sekureid tesseract --version

# Expected output:
# tesseract 5.x.x
# (...)
```

## Updating the Application

### When Code Changes (via Git)

```bash
cd /path/to/cloud_sekureid

# 1. Pull latest code
git pull origin main

# 2. Rebuild image
docker-compose build --no-cache

# 3. Restart services
docker-compose down
docker-compose up -d

# 4. Check status
docker-compose logs -f app
```

### When Dependencies Change (requirements.txt)

```bash
cd /path/to/cloud_sekureid

# Pull latest
git pull origin main

# Rebuild and restart
docker-compose build --no-cache
docker-compose down
docker-compose up -d
```

### When Tesseract Updates

```bash
# Update Tesseract on host
sudo apt-get update
sudo apt-get install -y --upgrade tesseract-ocr

# Container automatically picks up new version
# No Docker rebuild needed!

# Verify in container
docker exec cloud-sekureid tesseract --version
```

## Monitoring

### Check Application Status

```bash
# View running containers
docker-compose ps

# View logs (real-time)
docker-compose logs -f app

# View logs for specific time period
docker-compose logs --since 30m app

# View only errors
docker-compose logs app | grep -i error
```

### Health Checks

```bash
# Simple health check
curl http://localhost:3003/health

# Check API endpoints
curl http://localhost:3003/

# Test report generation
curl -X POST http://localhost:3003/generate-report \
  -H "Content-Type: application/json" \
  -d '{
    "company_code": "85",
    "username": "hisham.octacer",
    "password": "P@ss1234"
  }'

# Test text extraction
curl -X POST http://localhost:3003/extract-text \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
  }'
```

## Maintenance

### Stop Services

```bash
docker-compose down

# Or gracefully stop
docker-compose stop
```

### Restart Services

```bash
docker-compose restart

# Or full restart
docker-compose down
docker-compose up -d
```

### Clean Up

```bash
# Remove stopped containers
docker-compose down

# Remove images (will rebuild on next start)
docker rmi cloud-sekureid:latest

# Remove all stopped containers (system-wide)
docker container prune

# Remove unused images (system-wide)
docker image prune
```

### View Logs

```bash
# Real-time logs
docker-compose logs -f app

# Last 100 lines
docker-compose logs app --tail=100

# Since 1 hour ago
docker-compose logs app --since 1h
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs app

# Check Docker resources
docker stats

# Restart Docker daemon
sudo systemctl restart docker
docker-compose up -d
```

### Tesseract not found in container

```bash
# Verify Tesseract is installed on host
tesseract --version
which tesseract

# Verify mounts in container
docker exec cloud-sekureid ls -la /usr/bin/tesseract
docker exec cloud-sekureid tesseract --version
```

### Port already in use

```bash
# Find what's using port 3003
sudo lsof -i :3003

# Either kill the process or change port in docker-compose.yml
# Then restart
docker-compose down
docker-compose up -d
```

### Out of disk space

```bash
# Check disk usage
df -h

# Clean up old Docker data
docker system prune -a

# Remove old reports/logs
rm -rf ./sekureId_downloads/*
rm -rf ./sekureId_logs/*
```

## Environment Variables

Edit `docker-compose.yml` to customize:

```yaml
environment:
  - SEKUREID_COMPANY_CODE=85
  - SEKUREID_USERNAME=hisham.octacer
  - SEKUREID_PASSWORD=P@ss1234
  - BASE_DOMAIN=https://sekureid.octacer.info
```

## Performance Tuning

In `docker-compose.yml`, adjust resources:

```yaml
deploy:
  resources:
    limits:
      cpus: '2'        # Max 2 CPU cores
      memory: 2G       # Max 2GB RAM
    reservations:
      cpus: '1'        # Reserve 1 CPU core
      memory: 1G       # Reserve 1GB RAM
```

## Backup

### Backup Downloaded Reports

```bash
# Backup to external location
tar -czf reports-backup.tar.gz ./sekureId_downloads/
cp reports-backup.tar.gz /backup/location/
```

### Backup Configuration

```bash
# Backup docker-compose.yml
cp docker-compose.yml docker-compose.yml.backup
```

## File Locations

- **Application**: `/path/to/cloud_sekureid/`
- **Downloaded reports**: `/path/to/cloud_sekureid/sekureId_downloads/`
- **Logs**: `/path/to/cloud_sekureid/sekureId_logs/`
- **Docker config**: `/path/to/cloud_sekureid/docker-compose.yml`

## Getting Help

- Check logs: `docker-compose logs app`
- See TESSERACT_SETUP.md for OCR-related issues
- Check if Tesseract is available: `docker exec cloud-sekureid tesseract --version`
- Review DEBUGGING_QUICK_REFERENCE.md for common issues
