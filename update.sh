#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$SCRIPT_DIR/repo"
sudo git pull
docker build --no-cache -t cloud-sekureid:latest .
cd "$SCRIPT_DIR"
docker compose down
docker compose up -d
