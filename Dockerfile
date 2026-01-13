# Use Python 3.11 slim as base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

# Stage 1: Update package lists
RUN apt-get update

# Stage 2: Install build tools (stable, rarely changes)
RUN apt-get install -y --no-install-recommends \
    build-essential \
    wget \
    curl \
    ca-certificates

# Stage 3: Install Chromium and dependencies (large, stable layer)
RUN apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils

# Stage 4: Install PDF processing (medium, stable layer)
RUN apt-get install -y --no-install-recommends \
    poppler-utils

# Stage 5: Install Tesseract OCR (medium, stable layer)
RUN apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng

# Stage 6: Install other utilities (small, stable layer)
RUN apt-get install -y --no-install-recommends \
    libmagic1

# Stage 7: Clean up apt cache (run once at the end)
RUN apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Create a non-root user (small layer - stays cached)
RUN useradd -m -u 1000 appuser && \
    mkdir -p /home/appuser/app /home/appuser/downloads /home/appuser/temp_reports /home/appuser/logs /home/appuser/temp_extract && \
    chown -R appuser:appuser /home/appuser

# Set working directory
WORKDIR /home/appuser/app

# Copy requirements first for better caching (requirements change less often)
COPY --chown=appuser:appuser requirements.txt .

# Install Python dependencies (medium layer - cached if requirements.txt unchanged)
RUN pip install --no-cache-dir --upgrade pip setuptools && \
    pip install --no-cache-dir --no-warn-script-location -r requirements.txt

# Copy application files (small layers - change frequently)
COPY --chown=appuser:appuser api_server.py .
COPY --chown=appuser:appuser sekureid_automation.py .
COPY --chown=appuser:appuser vollna_automation.py .

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application with uvicorn directly for better timeout control
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "300"]
