# Deployment Script Setup Guide

This guide explains how to set up your deployment script for the cloud-sekureid project.

## Prerequisites

- Your deployment script (update.sh or similar)
- Tesseract OCR installed on Ubuntu host (see TESSERACT_SETUP.md)
- Docker and Docker Compose installed
- Git installed

## Configuration Files

Your deployment script uses three configuration files. They are now included in the repository:

### 1. `deployment_type.txt`
**Content**: `1`

This tells the script to **build locally from Git** (not pull from registry).

**Why 1?**
- `1` = Build locally (git pull + docker build)
- `0` = Pull from registry (ghcr.io, etc.)

### 2. `docker_context.txt`
**Content**: `.`

This is the directory containing the Dockerfile (the repository root).

### 3. `docker-compose.yml`
**Already configured** with:
- Local build context: `.`
- Image name: `cloud-sekureid:latest`
- Tesseract mounts from host

## Setup Instructions

### Step 1: Prepare Your Deployment Directory

Your directory structure should look like:

```
/home/ubuntu/deployments/cloud-sekureid/
├── update.sh                          # Your deployment script
├── repo/                              # Git repository (cloned here)
│   ├── .git/
│   ├── api_server.py
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── requirements.txt
│   ├── deployment_type.txt            # Value: 1
│   ├── docker_context.txt             # Value: .
│   └── ... (other files)
├── deployment_type.txt                # Symlink or copy from repo
└── docker_context.txt                 # Symlink or copy from repo
```

### Step 2: Install Tesseract on Host (One-time)

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng

# Verify
tesseract --version
```

### Step 3: Create Deployment Directory

```bash
# Create deployment directory
mkdir -p /home/ubuntu/deployments/cloud-sekureid
cd /home/ubuntu/deployments/cloud-sekureid

# Clone repository
git clone https://github.com/octacer/cloud_sekureid.git repo

# Create symlinks for config files
ln -s repo/deployment_type.txt deployment_type.txt
ln -s repo/docker_context.txt docker_context.txt

# Or copy them
cp repo/deployment_type.txt .
cp repo/docker_context.txt .
```

### Step 4: Prepare Your Update Script

If you have an existing `update.sh`, it should look like this:

```bash
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
cd "${SCRIPT_DIR}"
if docker compose version >/dev/null 2>&1; then
  docker compose -p "${PROJECT}" down
  docker compose -p "${PROJECT}" up -d
else
  docker-compose -p "${PROJECT}" down
  docker-compose -p "${PROJECT}" up -d
fi

echo "Update completed successfully!"
```

### Step 5: Make Script Executable

```bash
chmod +x /home/ubuntu/deployments/cloud-sekureid/update.sh
```

### Step 6: Test the Deployment

```bash
cd /home/ubuntu/deployments/cloud-sekureid

# Run the update script
./update.sh

# This will:
# 1. Git pull latest code
# 2. Docker build the image
# 3. Docker compose down (stop old container)
# 4. Docker compose up -d (start new container)

# Verify it's running
docker ps | grep cloud-sekureid
curl http://localhost:3003/health
```

## How The Script Works

### When You Call `./update.sh`:

1. **Read configuration**
   - `deployment_type.txt` → `1` (build locally)
   - `docker_context.txt` → `.` (current directory)

2. **Update code**
   - `cd repo`
   - `git pull` (gets latest from main branch)
   - `cd ..`

3. **Build Docker image**
   - `docker build -t cloud-sekureid:latest .`
   - Runs Dockerfile which:
     - Downloads Python base image
     - Installs system dependencies
     - Installs Python packages from requirements.txt
     - Does NOT include Tesseract binary (mounts from host)

4. **Restart containers**
   - `docker compose down` (stops old container)
   - `docker compose up -d` (starts new container with new image)
   - Mounts Tesseract from host system

5. **Done!**
   - Application is running with latest code
   - Tesseract automatically available via mounts

## What Gets Updated

When you run `./update.sh`:

✅ **Python code** (api_server.py, etc.)
✅ **Python dependencies** (from requirements.txt)
✅ **System dependencies** (Chromium, poppler, etc.)
✅ **Docker configuration**

❌ **Tesseract binary** (stays on host, just mounted)

## Testing After Deployment

```bash
# Check container is running
docker ps | grep cloud-sekureid

# View logs
docker logs -f cloud-sekureid

# Test health endpoint
curl http://localhost:3003/health

# Test API
curl http://localhost:3003/

# Test new text extraction feature
curl -X POST http://localhost:3003/extract-text \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
  }'
```

## Updating Tesseract on Host

If you need to install additional language packs:

```bash
# Update Tesseract on host (not in Docker)
sudo apt-get update
sudo apt-get install -y tesseract-ocr-spa  # Spanish
sudo apt-get install -y tesseract-ocr-fra  # French

# Container automatically uses new languages
# No Docker rebuild needed!

# Verify
docker exec cloud-sekureid tesseract --list-langs
```

## Reverting to Registry Builds

If you want to switch back to pulling from ghcr.io:

1. Change `deployment_type.txt` to `0`
2. Create `docker_image.txt` with: `ghcr.io/octacer/cloud-sekureid-prod:latest`
3. Update `docker-compose.yml` to use `image:` instead of `build:`

But for now, **local builds are recommended**.

## Troubleshooting

### Script fails: "docker build not found"

Make sure Docker is installed:
```bash
docker --version
docker-compose --version
```

### Script fails: "git command not found"

Install Git:
```bash
sudo apt-get install -y git
```

### Container won't start after update

Check logs:
```bash
docker logs cloud-sekureid
```

Check if Tesseract is accessible:
```bash
docker exec cloud-sekureid tesseract --version
```

### Port 3003 already in use

```bash
# Kill existing container
docker kill cloud-sekureid

# Run script again
./update.sh
```

### Build takes too long

First build is slow. Subsequent builds use cache. To force full rebuild:
```bash
# In the script or manually:
docker build --no-cache -t cloud-sekureid:latest .
```

## Security Notes

✅ Configuration files in repository (safe)
✅ Tesseract mounts are read-only (`:ro`)
✅ Container runs as non-root user
✅ No hardcoded passwords in image
✅ No registry credentials needed (local builds)

## File Locations on Ubuntu Server

```
/home/ubuntu/deployments/cloud-sekureid/
├── update.sh                    # Your deployment script
├── deployment_type.txt          # Config: 1 (local build)
├── docker_context.txt           # Config: . (current dir)
└── repo/                        # Git repository
    ├── api_server.py
    ├── Dockerfile
    ├── docker-compose.yml
    ├── requirements.txt
    └── ... (other project files)
```

## Next Steps

1. Ensure Tesseract is installed on host
2. Set up deployment directory structure
3. Test the update script: `./update.sh`
4. Verify application is running: `curl http://localhost:3003/health`
5. Test new text extraction feature

You're ready! 🚀
