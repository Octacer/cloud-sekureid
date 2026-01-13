#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="cloud-sekureid"

echo "=========================================="
echo "Cloud Sekureid Deployment Script"
echo "=========================================="
echo "Script directory: ${SCRIPT_DIR}"
echo "Project: ${PROJECT}"
echo ""

# Check deployment type
deployment_type="$(cat "${SCRIPT_DIR}/deployment_type.txt")"
echo "Deployment type: ${deployment_type}"

if [ "${deployment_type}" = "1" ]; then
    echo ""
    echo "Step 1: Updating from Git repository..."
    cd "${SCRIPT_DIR}/repo"
    echo "Current branch before pull:"
    git branch
    echo ""
    echo "Pulling latest code..."
    git pull origin main
    echo "✓ Git pull completed"

    echo ""
    echo "Step 2: Building Docker image..."
    cd "${SCRIPT_DIR}"
    docker_context="$(cat "${SCRIPT_DIR}/docker_context.txt")"
    echo "Docker context: ${docker_context}"

    docker build -t "${PROJECT}:latest" "${docker_context}"
    echo "✓ Docker image built successfully"
else
    echo ""
    echo "Step 1: Pulling latest Docker image..."
    docker_image="$(cat "${SCRIPT_DIR}/docker_image.txt")"
    echo "Docker image: ${docker_image}"
    docker pull "${docker_image}"
    echo "✓ Docker image pulled successfully"
fi

echo ""
echo "Step 3: Restarting containers with new image..."
cd "${SCRIPT_DIR}/repo"

# Check Docker Compose version and restart
if docker compose version >/dev/null 2>&1; then
  echo "Using: docker compose (v2)"
  docker compose -p "${PROJECT}" down
  docker compose -p "${PROJECT}" up -d
else
  echo "Using: docker-compose (v1)"
  docker-compose -p "${PROJECT}" down
  docker-compose -p "${PROJECT}" up -d
fi
echo "✓ Containers restarted"

echo ""
echo "Step 4: Verifying deployment..."
sleep 3

# Check if container is running
if docker ps | grep -q "${PROJECT}"; then
    echo "✓ Container is running"
else
    echo "✗ Container is NOT running - checking logs..."
    docker logs "${PROJECT}" || true
    exit 1
fi

# Test health endpoint
echo ""
echo "Testing API health endpoint..."
max_attempts=10
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if curl -s http://localhost:3003/health > /dev/null 2>&1; then
        echo "✓ API is responding"
        curl -s http://localhost:3003/health | head -c 100
        echo ""
        break
    fi
    attempt=$((attempt + 1))
    echo "Waiting for API to start... (attempt $attempt/$max_attempts)"
    sleep 1
done

if [ $attempt -eq $max_attempts ]; then
    echo "✗ API did not respond in time"
    echo "Checking container logs:"
    docker logs "${PROJECT}" | tail -20
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ Update completed successfully!"
echo "=========================================="
echo ""
echo "Application Status:"
docker ps -f name="${PROJECT}" --format "table {{.Names}}\t{{.Status}}"

echo ""
echo "Quick Commands:"
echo "  View logs:     docker logs -f ${PROJECT}"
echo "  API health:    curl http://localhost:3003/health"
echo "  Stop:          docker-compose -p ${PROJECT} down"
echo "  Start:         docker-compose -p ${PROJECT} up -d"
echo ""
echo "Next Steps:"
echo "  1. Check logs: docker logs -f ${PROJECT}"
echo "  2. Test API:   curl http://localhost:3003/"
echo "  3. Test text extraction:"
echo "     curl -X POST http://localhost:3003/extract-text \\"
echo "       -H 'Content-Type: application/json' \\"
echo "       -d '{\"url\": \"https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf\"}'"
echo ""
