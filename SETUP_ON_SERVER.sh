#!/bin/bash
set -euo pipefail

# This script sets up cloud-sekureid on your Ubuntu server
# Run this on your server: bash SETUP_ON_SERVER.sh

echo "=========================================="
echo "Cloud Sekureid - Server Setup Script"
echo "=========================================="
echo ""

DEPLOYMENT_DIR="/var/www/projects/cloud-sekureid"
REPO_DIR="${DEPLOYMENT_DIR}/repo"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "This script needs to be run with sudo or as root"
    echo "Run: sudo bash SETUP_ON_SERVER.sh"
    exit 1
fi

echo "Step 1: Checking prerequisites..."
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed"
    echo "Install with: sudo apt-get install -y docker.io"
    exit 1
fi
echo "✓ Docker is installed: $(docker --version)"

# Check Docker Compose
if ! docker compose version &> /dev/null && ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed"
    echo "Install with: sudo apt-get install -y docker-compose-v2"
    exit 1
fi
echo "✓ Docker Compose is installed"

# Check Git
if ! command -v git &> /dev/null; then
    echo "❌ Git is not installed"
    echo "Install with: sudo apt-get install -y git"
    exit 1
fi
echo "✓ Git is installed: $(git --version | head -1)"

# Check Tesseract
if ! command -v tesseract &> /dev/null; then
    echo "❌ Tesseract is not installed"
    echo "Install with: sudo apt-get install -y tesseract-ocr tesseract-ocr-eng"
    exit 1
fi
echo "✓ Tesseract is installed: $(tesseract --version | head -1)"

echo ""
echo "Step 2: Creating deployment directory structure..."
echo ""

# Create deployment directories if they don't exist
if [ ! -d "${DEPLOYMENT_DIR}" ]; then
    echo "Creating ${DEPLOYMENT_DIR}..."
    mkdir -p "${DEPLOYMENT_DIR}"
    echo "✓ Directory created"
else
    echo "✓ Directory already exists: ${DEPLOYMENT_DIR}"
fi

# Navigate to deployment directory
cd "${DEPLOYMENT_DIR}"

# Check if repo already exists
if [ -d "${REPO_DIR}" ]; then
    echo "✓ Repository already exists at ${REPO_DIR}"
    echo "Updating repository..."
    cd "${REPO_DIR}"
    git pull origin main
    echo "✓ Repository updated"
else
    echo "Cloning repository..."
    git clone https://github.com/octacer/cloud_sekureid.git repo
    echo "✓ Repository cloned"
fi

cd "${DEPLOYMENT_DIR}"

echo ""
echo "Step 3: Creating configuration files..."
echo ""

# Create deployment_type.txt
if [ ! -f "deployment_type.txt" ]; then
    echo "1" > deployment_type.txt
    echo "✓ Created deployment_type.txt (value: 1 = local build)"
else
    echo "✓ deployment_type.txt already exists"
    echo "  Value: $(cat deployment_type.txt)"
fi

# Create docker_context.txt
if [ ! -f "docker_context.txt" ]; then
    echo "./repo" > docker_context.txt
    echo "✓ Created docker_context.txt (value: ./repo)"
else
    echo "✓ docker_context.txt already exists"
    echo "  Value: $(cat docker_context.txt)"
fi

echo ""
echo "Step 4: Setting up update.sh script..."
echo ""

# Copy update.sh from repo if it exists
if [ -f "${REPO_DIR}/update.sh" ]; then
    cp "${REPO_DIR}/update.sh" "${DEPLOYMENT_DIR}/update.sh"
    chmod +x "${DEPLOYMENT_DIR}/update.sh"
    echo "✓ update.sh copied and made executable"
else
    echo "⚠ update.sh not found in repo"
    echo "  Creating basic update script..."
    cat > "${DEPLOYMENT_DIR}/update.sh" << 'SCRIPT_EOF'
#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="cloud-sekureid"

deployment_type="$(cat "${SCRIPT_DIR}/deployment_type.txt")"

if [ "${deployment_type}" = "1" ]; then
    cd "${SCRIPT_DIR}/repo"
    git pull origin main
    cd "${SCRIPT_DIR}"
    docker_context="$(cat "${SCRIPT_DIR}/docker_context.txt")"
    docker build -t "${PROJECT}:latest" "${docker_context}"
fi

cd "${SCRIPT_DIR}/repo"
if docker compose version >/dev/null 2>&1; then
  docker compose -p "${PROJECT}" down
  docker compose -p "${PROJECT}" up -d
else
  docker-compose -p "${PROJECT}" down
  docker-compose -p "${PROJECT}" up -d
fi

echo "✅ Update completed successfully!"
SCRIPT_EOF
    chmod +x "${DEPLOYMENT_DIR}/update.sh"
    echo "✓ Basic update.sh created"
fi

echo ""
echo "Step 5: Verifying file structure..."
echo ""

# Check all required files
required_files=(
    "deployment_type.txt"
    "docker_context.txt"
    "update.sh"
    "repo/Dockerfile"
    "repo/docker-compose.yml"
    "repo/api_server.py"
    "repo/requirements.txt"
)

all_good=true
for file in "${required_files[@]}"; do
    if [ -f "${DEPLOYMENT_DIR}/${file}" ]; then
        echo "✓ ${file}"
    else
        echo "❌ ${file} - NOT FOUND"
        all_good=false
    fi
done

if [ "$all_good" = false ]; then
    echo ""
    echo "⚠ Some files are missing. Please check the repo directory."
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ Server setup completed successfully!"
echo "=========================================="
echo ""
echo "Configuration Summary:"
echo "  Deployment directory: ${DEPLOYMENT_DIR}"
echo "  Repository: ${REPO_DIR}"
echo "  Docker project: cloud-sekureid"
echo "  API port: 3003"
echo ""
echo "Next Steps:"
echo "  1. Review configuration in docker-compose.yml:"
echo "     cd ${DEPLOYMENT_DIR}/repo"
echo "     nano docker-compose.yml"
echo ""
echo "  2. Run the first deployment:"
echo "     cd ${DEPLOYMENT_DIR}"
echo "     ./update.sh"
echo ""
echo "  3. Check the application is running:"
echo "     curl http://localhost:3003/health"
echo ""
echo "  4. View logs:"
echo "     docker logs -f cloud-sekureid"
echo ""
echo "To deploy future updates:"
echo "  cd ${DEPLOYMENT_DIR}"
echo "  ./update.sh"
echo ""
