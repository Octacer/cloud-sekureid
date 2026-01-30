# Quick Setup Guide for Your Server

Since you already have a repo at `/var/www/projects/cloud-sekureid/repo`, here's how to set everything up quickly.

## Prerequisites Check

Before you start, verify these are installed on your Ubuntu server:

```bash
# Docker
docker --version
# Should output: Docker version 20.x or higher

# Docker Compose
docker compose version
# Should output: Docker Compose version 2.x or higher

# Git
git --version
# Should output: git version 2.x or higher

# Tesseract (CRITICAL!)
tesseract --version
# Should output: tesseract 5.x or higher
# If not installed, run: sudo apt-get install -y tesseract-ocr tesseract-ocr-eng
```

## Step 1: Prepare Your Deployment Directory

```bash
# Go to your deployment directory
cd /var/www/projects/cloud-sekureid

# Make sure repo is up to date
cd repo
git pull origin main
cd ..

# Create config files (if they don't exist)
echo "1" > deployment_type.txt
echo "./repo" > docker_context.txt

# Copy the new update.sh (it's now in the repo)
cp repo/update.sh .
chmod +x update.sh

# Verify the files
ls -la
# Should show:
# deployment_type.txt
# docker_context.txt
# update.sh (executable)
# repo/
```

## Step 2: Verify Configuration

Check your docker-compose.yml is correct:

```bash
cd /var/www/projects/cloud-sekureid/repo

# View the file
cat docker-compose.yml | head -30

# Should show:
# - build context: .
# - image: cloud-sekureid:latest
# - Tesseract mounts from host
```

## Step 3: First Deployment

```bash
# Go to deployment directory
cd /var/www/projects/cloud-sekureid

# Run the update script
./update.sh

# This will:
# 1. Pull latest code
# 2. Build Docker image (takes 5-10 minutes first time)
# 3. Start containers
# 4. Test the API
```

## Step 4: Verify It Works

```bash
# Check container is running
docker ps | grep cloud-sekureid

# Test health endpoint
curl http://localhost:3003/health

# Should return: {"status":"healthy","timestamp":"..."}

# Test the new text extraction feature
curl -X POST http://localhost:3003/extract-text \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
  }'

# Should return JSON with extracted text
```

## Step 5: Customize Configuration (Optional)

Edit docker-compose.yml to customize:

```bash
cd /var/www/projects/cloud-sekureid/repo

# Edit the file
sudo nano docker-compose.yml

# Update these environment variables:
environment:
  - SEKUREID_COMPANY_CODE=85
  - SEKUREID_USERNAME=hisham.octacer
  - SEKUREID_PASSWORD=P@ss1234
  - BASE_DOMAIN=https://sekureid.octacer.info  # Your domain

# Save and restart
cd ..
./update.sh
```

## Daily Operations

### Deploy Updates

```bash
cd /var/www/projects/cloud-sekureid
./update.sh
```

This pulls the latest code and restarts everything automatically.

### View Logs

```bash
# Real-time logs
docker logs -f cloud-sekureid

# Last 100 lines
docker logs cloud-sekureid --tail=100

# Logs from last hour
docker logs cloud-sekureid --since 1h
```

### Stop/Start Application

```bash
# Stop
docker-compose -p cloud-sekureid down

# Start
cd /var/www/projects/cloud-sekureid/repo
docker-compose -p cloud-sekureid up -d

# Restart
docker-compose -p cloud-sekureid restart
```

### Check Status

```bash
# Container status
docker ps | grep cloud-sekureid

# Full API info
curl http://localhost:3003/

# Health check
curl http://localhost:3003/health
```

## File Structure After Setup

```
/var/www/projects/cloud-sekureid/
├── deployment_type.txt        Contains: 1
├── docker_context.txt         Contains: ./repo
├── update.sh                  Deployment script (make executable)
└── repo/
    ├── api_server.py
    ├── sekureid_automation.py
    ├── vollna_automation.py
    ├── Dockerfile
    ├── docker-compose.yml
    ├── requirements.txt
    ├── deployment_type.txt
    ├── docker_context.txt
    └── (other files...)
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker logs cloud-sekureid

# Common issues:
# - Port 3003 already in use
# - Tesseract not installed on host
# - Docker daemon not running
```

### Tesseract not found

```bash
# Verify on host
tesseract --version
which tesseract

# Check in container
docker exec cloud-sekureid tesseract --version

# If not found, install on host:
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng
```

### Build takes too long

First build takes 5-10 minutes. Subsequent builds are faster (30-60 seconds) due to Docker caching.

To force full rebuild:
```bash
cd /var/www/projects/cloud-sekureid/repo
docker build --no-cache -t cloud-sekureid:latest .
```

### API not responding

```bash
# Wait a few seconds after deployment
sleep 10

# Check if container is running
docker ps | grep cloud-sekureid

# Check logs
docker logs -f cloud-sekureid

# Test again
curl http://localhost:3003/health
```

## Environment Variables

You can customize these in docker-compose.yml:

```yaml
environment:
  - SEKUREID_COMPANY_CODE=85           # Company code for login
  - SEKUREID_USERNAME=hisham.octacer   # Username
  - SEKUREID_PASSWORD=P@ss1234         # Password
  - BASE_DOMAIN=https://sekureid.octacer.info  # Base URL for responses
```

After changing, restart:
```bash
cd /var/www/projects/cloud-sekureid
./update.sh
```

## What The Update Script Does

```
./update.sh
  ↓
1. Read deployment_type.txt (value: 1)
  ↓
2. cd repo && git pull origin main
  ↓
3. docker build -t cloud-sekureid:latest ./repo
  ↓
4. docker compose -p cloud-sekureid down
  ↓
5. docker compose -p cloud-sekureid up -d
  ↓
6. Wait for container to start
  ↓
7. Test API health endpoint
  ↓
8. Show status and logs
```

## Quick Commands Reference

```bash
# Deploy
cd /var/www/projects/cloud-sekureid && ./update.sh

# View logs
docker logs -f cloud-sekureid

# Stop
docker-compose -p cloud-sekureid down

# Start
cd /var/www/projects/cloud-sekureid/repo && docker-compose -p cloud-sekureid up -d

# Health check
curl http://localhost:3003/health

# API info
curl http://localhost:3003/

# Test text extraction
curl -X POST http://localhost:3003/extract-text \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"}'

# Shell into container
docker exec -it cloud-sekureid /bin/bash

# Check Tesseract in container
docker exec cloud-sekureid tesseract --version
```

## Summary

1. ✅ Run `./update.sh` to deploy
2. ✅ Check logs with `docker logs -f cloud-sekureid`
3. ✅ Test with `curl http://localhost:3003/health`
4. ✅ View API at `http://localhost:3003/`

That's it! Your cloud-sekureid is ready to use. 🚀
