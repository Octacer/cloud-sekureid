#!/bin/bash

cd repo
git pull origin main
docker build -t cloud-sekureid:latest .
docker compose up
