# Server Setup Checklist

Use this checklist to ensure your Ubuntu server is ready for cloud-sekureid deployment.

## ✅ System Requirements

- [ ] Ubuntu 20.04 or later (`lsb_release -a`)
- [ ] At least 2GB RAM available
- [ ] At least 5GB disk space
- [ ] Internet connectivity

## ✅ Step 1: Install System Dependencies

### Docker & Docker Compose

```bash
# Check if Docker is installed
docker --version

# If not, install Docker
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2

# Start Docker service
sudo systemctl start docker
sudo systemctl enable docker

# Verify
docker --version
docker compose version
```

### Git

```bash
# Check if Git is installed
git --version

# If not, install
sudo apt-get install -y git

# Verify
git --version
```

## ✅ Step 2: Install Tesseract OCR

**This is CRITICAL for the text extraction feature!**

```bash
# Install Tesseract
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng

# Verify installation
tesseract --version

# Check language data directory
ls /usr/share/tesseract-ocr/tessdata/

# Should see: eng.traineddata
```

### Optional: Install Additional Languages

```bash
# Spanish
sudo apt-get install -y tesseract-ocr-spa

# French
sudo apt-get install -y tesseract-ocr-fra

# Verify
tesseract --list-langs
```

## ✅ Step 3: Create Deployment Directory

```bash
# Create directory
mkdir -p /home/ubuntu/deployments/cloud-sekureid
cd /home/ubuntu/deployments/cloud-sekureid

# Clone repository
git clone https://github.com/octacer/cloud_sekureid.git repo

# Create config files
echo "1" > deployment_type.txt
echo "." > docker_context.txt

# List what we have
ls -la
# Should show:
# deployment_type.txt (contains: 1)
# docker_context.txt (contains: .)
# repo/ (the git repository)
```

## ✅ Step 4: Set Up Update Script

```bash
# Navigate to deployment directory
cd /home/ubuntu/deployments/cloud-sekureid

# Create update.sh (use template below or copy your existing one)
cat > update.sh << 'EOF'
#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="cloud-sekureid"

# Check deployment type
deployment_type="$(cat "${SCRIPT_DIR}/deployment_type.txt")"

if [ "${deployment_type}" = "1" ]; then
    echo "Updating from Git repository..."
    cd "${SCRIPT_DIR}/repo"
    git pull
    cd "${SCRIPT_DIR}"
    docker_context="$(cat "${SCRIPT_DIR}/docker_context.txt")"
    docker build -t "${PROJECT}:latest" "${docker_context}"
else
    echo "Pulling latest Docker image..."
    docker_image="$(cat "${SCRIPT_DIR}/docker_image.txt")"
    docker pull "${docker_image}"
fi

# Restart containers with new image
cd "${SCRIPT_DIR}/repo"
if docker compose version >/dev/null 2>&1; then
  docker compose -p "${PROJECT}" down
  docker compose -p "${PROJECT}" up -d
else
  docker-compose -p "${PROJECT}" down
  docker-compose -p "${PROJECT}" up -d
fi

echo "Update completed successfully!"
EOF

# Make it executable
chmod +x update.sh

# Verify
ls -la update.sh
# Should show: -rwxr-xr-x
```

## ✅ Step 5: First Deployment

```bash
# Go to deployment directory
cd /home/ubuntu/deployments/cloud-sekureid

# Run the update script
./update.sh

# This will:
# 1. git pull (get latest code)
# 2. docker build (create image - takes 5-10 min first time)
# 3. docker compose down (stop any old containers)
# 4. docker compose up -d (start new container)

# Wait for completion (look for "Update completed successfully!")
```

## ✅ Step 6: Verify Deployment

```bash
# Check if container is running
docker ps | grep cloud-sekureid
# Should show: cloud-sekureid (status: Up X seconds)

# View logs
docker logs -f cloud-sekureid
# Should show startup messages

# Test health endpoint (wait 10 seconds, then try)
sleep 10
curl http://localhost:3003/health

# Expected response:
# {"status":"healthy","timestamp":"2026-01-13T..."}
```

## ✅ Step 7: Test New Text Extraction Feature

```bash
# Test with a sample PDF
curl -X POST http://localhost:3003/extract-text \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
  }'

# Should return JSON with extracted text:
# {
#   "text": "...",
#   "language": "eng",
#   "extraction_method": "Tesseract OCR",
#   "source_type": "pdf",
#   "total_pages": 1,
#   "extracted_at": "2026-01-13T...",
#   "request_id": "..."
# }
```

## ✅ Step 8: Configure Application

Edit `/home/ubuntu/deployments/cloud-sekureid/repo/docker-compose.yml`:

```yaml
environment:
  - SEKUREID_COMPANY_CODE=85
  - SEKUREID_USERNAME=hisham.octacer
  - SEKUREID_PASSWORD=P@ss1234
  - BASE_DOMAIN=https://sekureid.octacer.info
```

Then restart:

```bash
cd /home/ubuntu/deployments/cloud-sekureid/repo
docker-compose down
docker-compose up -d
```

## ✅ Verification Commands

Run these commands to verify everything is set up correctly:

```bash
# 1. Docker is running
docker --version
docker compose version

# 2. Git is installed
git --version

# 3. Tesseract is installed on host
tesseract --version
which tesseract

# 4. Tesseract can be accessed from container
docker exec cloud-sekureid tesseract --version

# 5. API is responding
curl http://localhost:3003/health

# 6. All endpoints are available
curl http://localhost:3003/

# 7. Text extraction works
curl -X POST http://localhost:3003/extract-text \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"}'
```

## ✅ File Structure Verification

After setup, verify this structure exists:

```
/home/ubuntu/deployments/cloud-sekureid/
├── deployment_type.txt        ✓ Contains: 1
├── docker_context.txt         ✓ Contains: .
├── update.sh                  ✓ Executable script
└── repo/
    ├── .git/
    ├── api_server.py          ✓ Main API
    ├── docker-compose.yml     ✓ Container config
    ├── Dockerfile             ✓ Image definition
    ├── requirements.txt        ✓ Python deps
    ├── TESSERACT_SETUP.md
    ├── DEPLOYMENT_SCRIPT_SETUP.md
    ├── DEPLOYMENT.md
    ├── LOCAL_BUILD_INSTRUCTIONS.md
    ├── README_DEPLOYMENT.md
    └── SERVER_SETUP_CHECKLIST.md (this file)
```

## Troubleshooting Checklist

### Docker won't start
- [ ] Docker service is running: `sudo systemctl status docker`
- [ ] Docker daemon restarted: `sudo systemctl restart docker`
- [ ] User has Docker permissions: `docker ps`

### Tesseract not found in container
- [ ] Tesseract installed on host: `tesseract --version`
- [ ] Binary exists: `ls /usr/bin/tesseract`
- [ ] Check container mounts: `docker exec cloud-sekureid ls /usr/bin/tesseract`

### Build fails with "python not found"
- [ ] Docker daemon is running
- [ ] Internet connectivity exists
- [ ] Sufficient disk space: `df -h`
- [ ] Check Docker logs: `docker logs`

### Port 3003 already in use
- [ ] Find process: `sudo lsof -i :3003`
- [ ] Stop old container: `docker kill cloud-sekureid`
- [ ] Or change port in docker-compose.yml

### Git won't pull
- [ ] Internet connectivity
- [ ] SSH key configured (if private repo)
- [ ] Git credentials valid
- [ ] Check: `git -C repo status`

## Quick Commands Reference

```bash
# Navigate to deployment
cd /home/ubuntu/deployments/cloud-sekureid

# Run update script
./update.sh

# View logs
docker logs -f cloud-sekureid

# Stop application
docker-compose -p cloud-sekureid down

# Start application
docker-compose -p cloud-sekureid up -d

# Rebuild without cache
docker build --no-cache -t cloud-sekureid:latest repo

# Shell into container
docker exec -it cloud-sekureid /bin/bash

# Check status
docker ps | grep cloud-sekureid

# Test API
curl http://localhost:3003/health
```

## Next Steps

Once all items are checked:

1. ✅ Your Ubuntu server is ready for cloud-sekureid
2. ✅ Use `./update.sh` to deploy updates
3. ✅ Monitor with `docker logs -f cloud-sekureid`
4. ✅ Refer to `README_DEPLOYMENT.md` for day-to-day operations

## Support

If something doesn't work:

1. Check logs: `docker logs cloud-sekureid`
2. Read `README_DEPLOYMENT.md` troubleshooting section
3. Read `DEPLOYMENT_SCRIPT_SETUP.md` for script-specific issues
4. Read `TESSERACT_SETUP.md` for OCR issues

---

**Estimated Setup Time**: 10-15 minutes (first run takes 5-10 min to build)

**Status**: ✅ Ready when all items checked
