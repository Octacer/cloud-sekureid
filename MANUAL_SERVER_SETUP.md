# Manual Server Setup Instructions

For your server at: `/var/www/projects/cloud-sekureid/`

## Prerequisites

Make sure these are installed:

```bash
tesseract --version
docker --version
docker compose version
git --version
```

If Tesseract is missing:
```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng
```

## Setup Steps

### 1. Update Your Repository

```bash
cd /var/www/projects/cloud-sekureid/repo
git pull origin main
cd ..
```

### 2. Create Configuration Files

```bash
cd /var/www/projects/cloud-sekureid

# Create deployment_type.txt (tells script to build locally)
echo "1" > deployment_type.txt

# Create docker_context.txt (path to Dockerfile)
echo "./repo" > docker_context.txt

# Verify
cat deployment_type.txt    # Should show: 1
cat docker_context.txt     # Should show: ./repo
```

### 3. Copy the New Update Script

```bash
cd /var/www/projects/cloud-sekureid

# Copy from repo
cp repo/update.sh ./update.sh

# Make executable
chmod +x update.sh

# Verify
ls -la update.sh
# Should show: -rwxr-xr-x
```

### 4. First Deployment

```bash
cd /var/www/projects/cloud-sekureid

# Run the update script
./update.sh

# Output should show:
# ==========================================
# Cloud Sekureid Deployment Script
# ==========================================
# [steps 1-4 with progress markers]
# ✅ Update completed successfully!
# ==========================================
```

### 5. Verify Deployment

```bash
# Check if container is running
docker ps | grep cloud-sekureid
# Should show: cloud-sekureid ... Up X seconds

# Test the API
curl http://localhost:3003/health
# Should return: {"status":"healthy","timestamp":"..."}

# View logs
docker logs cloud-sekureid | head -20
```

## Using the Update Script

Every time you want to deploy:

```bash
cd /var/www/projects/cloud-sekureid
./update.sh
```

The script will:
1. ✓ Pull latest code from Git
2. ✓ Build Docker image
3. ✓ Restart containers
4. ✓ Test the API is responding
5. ✓ Show status

## Testing the Text Extraction Feature

```bash
# Extract text from a PDF
curl -X POST http://localhost:3003/extract-text \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
  }'

# Response should include:
# {
#   "text": "...extracted text...",
#   "language": "eng",
#   "extraction_method": "Tesseract OCR",
#   "source_type": "pdf",
#   "total_pages": 1,
#   "extracted_at": "2026-01-13T...",
#   "request_id": "..."
# }
```

## Directory Structure

After setup, verify this structure:

```
/var/www/projects/cloud-sekureid/
├── deployment_type.txt      ← You created this (value: 1)
├── docker_context.txt       ← You created this (value: ./repo)
├── update.sh                ← You copied from repo (executable)
└── repo/
    ├── .git/
    ├── api_server.py
    ├── Dockerfile
    ├── docker-compose.yml
    ├── requirements.txt
    ├── update.sh
    ├── deployment_type.txt
    ├── docker_context.txt
    └── [other files]
```

## What's in the New Update Script

The new `update.sh` includes:

✅ Detailed progress output
✅ Step-by-step logging
✅ Error checking
✅ API health verification
✅ Docker Compose v1 & v2 support
✅ Helpful next-steps recommendations

Sample output:
```
==========================================
Cloud Sekureid Deployment Script
==========================================
Script directory: /var/www/projects/cloud-sekureid
Project: cloud-sekureid

Step 1: Updating from Git repository...
✓ Git pull completed

Step 2: Building Docker image...
✓ Docker image built successfully

Step 3: Restarting containers with new image...
✓ Containers restarted

Step 4: Verifying deployment...
✓ Container is running
✓ API is responding

✅ Update completed successfully!
```

## Commands for Daily Use

```bash
# Deploy updates
cd /var/www/projects/cloud-sekureid && ./update.sh

# View logs
docker logs -f cloud-sekureid

# Stop application
docker-compose -p cloud-sekureid down

# Start application
cd /var/www/projects/cloud-sekureid/repo
docker-compose -p cloud-sekureid up -d

# Check status
docker ps | grep cloud-sekureid

# Health check
curl http://localhost:3003/health

# View API endpoints
curl http://localhost:3003/

# Shell access
docker exec -it cloud-sekureid /bin/bash

# Tesseract version
docker exec cloud-sekureid tesseract --version
```

## Environment Variables

To customize credentials and settings:

```bash
# Edit docker-compose.yml
nano /var/www/projects/cloud-sekureid/repo/docker-compose.yml

# Update environment section:
environment:
  - SEKUREID_COMPANY_CODE=85
  - SEKUREID_USERNAME=your_username
  - SEKUREID_PASSWORD=your_password
  - BASE_DOMAIN=https://your-domain.com

# Save and deploy
cd /var/www/projects/cloud-sekureid
./update.sh
```

## File Permissions

If you get permission errors:

```bash
# Make update.sh executable
chmod +x /var/www/projects/cloud-sekureid/update.sh

# Fix directory permissions
sudo chown -R $USER:$USER /var/www/projects/cloud-sekureid

# Fix Docker group (if you get "permission denied")
sudo usermod -aG docker $USER
# Then restart shell: exec $SHELL
```

## Docker Commands Reference

### View Logs
```bash
# Real-time
docker logs -f cloud-sekureid

# Last 50 lines
docker logs cloud-sekureid --tail=50

# From last hour
docker logs cloud-sekureid --since 1h
```

### Container Management
```bash
# List running containers
docker ps

# Stop container
docker stop cloud-sekureid

# Start container
docker start cloud-sekureid

# Restart container
docker restart cloud-sekureid

# Remove container
docker rm cloud-sekureid
```

### Image Management
```bash
# List images
docker images | grep cloud-sekureid

# Remove image
docker rmi cloud-sekureid:latest

# Build image
docker build -t cloud-sekureid:latest /var/www/projects/cloud-sekureid/repo

# Build without cache
docker build --no-cache -t cloud-sekureid:latest /var/www/projects/cloud-sekureid/repo
```

## Troubleshooting

### "docker: command not found"
Docker is not installed. Install it:
```bash
sudo apt-get install -y docker.io
sudo systemctl start docker
```

### "docker compose: command not found"
Docker Compose is not installed. Install it:
```bash
sudo apt-get install -y docker-compose-v2
```

### "tesseract: command not found in container"
Tesseract is not installed on host. Install it:
```bash
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng
# Then restart the container
docker-compose -p cloud-sekureid restart
```

### Container won't start
```bash
# Check logs
docker logs cloud-sekureid

# Restart Docker daemon
sudo systemctl restart docker

# Try again
./update.sh
```

### Port 3003 already in use
```bash
# Find what's using it
sudo lsof -i :3003

# Kill the process
sudo kill -9 <PID>

# Or change port in docker-compose.yml
nano repo/docker-compose.yml
# Change: "3003:8000" to "3004:8000" or another port
# Then: ./update.sh
```

### Build fails
```bash
# Check Docker daemon
docker ps

# Check disk space
df -h

# Force rebuild
cd /var/www/projects/cloud-sekureid
docker build --no-cache -t cloud-sekureid:latest ./repo

# Or use update script
./update.sh
```

## Next Steps

1. ✅ Run `./update.sh` once to deploy
2. ✅ Check logs: `docker logs -f cloud-sekureid`
3. ✅ Test API: `curl http://localhost:3003/health`
4. ✅ Use `./update.sh` for future deployments

---

**Ready to deploy!** 🚀

Just run:
```bash
cd /var/www/projects/cloud-sekureid
./update.sh
```
