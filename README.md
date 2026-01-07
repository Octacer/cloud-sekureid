# Sekure-ID Cloud Report Generator API

Automated report generation and download system for Sekure-ID Cloud attendance system. This tool automates the process of logging in, generating reports, and downloading Excel files through a REST API.

## Features

- Automated login to Sekure-ID Cloud portal
- Automated daily attendance report generation
- Excel file download
- REST API endpoint for easy integration
- Configurable date range
- Automatic cleanup of temporary files
- **Fully headless operation** - Perfect for AWS EC2, cloud servers, and SSH-only environments
- **No display/GUI required** - Runs completely in the background

## Prerequisites

### Using Docker (Recommended)
- **Docker** and **Docker Compose** installed
- No other dependencies required! Everything is containerized.

### Using Python Directly
1. **Python 3.8+**
2. **Chrome or Chromium browser** installed
3. **ChromeDriver** (compatible with your Chrome version)

## Installation & Usage

### Option 1: Run with Docker (Recommended - Zero Setup!)

This is the easiest way to run the application. Everything including Chromium browser is included in the container. **Chrome runs in native headless mode** - perfect for AWS servers, cloud instances, or any environment without a display.

**Quick Start:**

1. Clone or navigate to this directory:
```bash
cd /mnt/c/git/octacer/cloud_sekureid
```

2. Build and start the container:
```bash
docker-compose up -d
```

3. The API is now running at `http://localhost:8000`

4. Test the API:
```bash
curl -X POST http://localhost:8000/generate-report \
  -H "Content-Type: application/json" \
  -d '{}' \
  --output report.xlsx
```

**Docker Commands:**

```bash
# Start the container
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the container
docker-compose down

# Rebuild after code changes
docker-compose up -d --build

# Check container status
docker-compose ps

# Access container shell for debugging
docker exec -it sekureid-report-generator /bin/bash
```

**Building Docker Image Manually:**

```bash
# Build the image
docker build -t sekureid-api .

# Run the container
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/downloads:/home/appuser/downloads \
  --shm-size=2g \
  --name sekureid-api \
  sekureid-api
```

**Environment Variables with Docker:**

You can pass credentials via environment variables:

```bash
docker run -d \
  -p 8000:8000 \
  -e SEKUREID_COMPANY_CODE=85 \
  -e SEKUREID_USERNAME=your_username \
  -e SEKUREID_PASSWORD=your_password \
  --shm-size=2g \
  --name sekureid-api \
  sekureid-api
```

Or edit the `docker-compose.yml` file to set your credentials.

### Option 2: Run with Python Directly

If you prefer to run without Docker:

**Installing ChromeDriver:**

**On Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install chromium-chromedriver
```

**On Windows:**
1. Download ChromeDriver from https://chromedriver.chromium.org/
2. Add the ChromeDriver location to your PATH

**On macOS:**
```bash
brew install chromedriver
```

**Installation:**

1. Clone or navigate to this directory:
```bash
cd /mnt/c/git/octacer/cloud_sekureid
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

**Run as Standalone Script:**

```bash
python sekureid_automation.py
```

This will:
- Login to Sekure-ID Cloud
- Navigate to Daily Reports
- Generate today's attendance report
- Download the Excel file to `./downloads/` directory

**Run as API Server:**

```bash
python api_server.py
```

The API will be available at `http://localhost:8000`

Interactive API documentation: `http://localhost:8000/docs`

## API Endpoints

The API now offers **two modes** for each endpoint:

1. **JSON Response** (NEW - Recommended): Returns JSON with a download URL
2. **Direct Download** (Backwards Compatible): Returns Excel file directly

### GET /get-report-default

**Quick and easy!** Generate today's attendance report with default credentials - Returns JSON with download URL.

**Example:**
```bash
curl http://localhost:8000/get-report-default
```

**Response:**
```json
{
  "report_url": "https://sekureid.octacer.info/download/abc-123-def-456",
  "file_id": "abc-123-def-456",
  "report_date": "2024-01-15",
  "generated_at": "2024-01-15T10:30:00",
  "expires_in": 3600
}
```

Then download using the URL:
```bash
curl https://sekureid.octacer.info/download/abc-123-def-456 --output report.xlsx
```

### GET /get-report-default-direct

Same as above but returns Excel file directly (backwards compatible).

```bash
curl http://localhost:8000/get-report-default-direct --output report.xlsx
```

### POST /generate-report

Generate attendance report with custom parameters - Returns JSON with download URL.

**Request Body:**
```json
{
  "company_code": "85",
  "username": "hisham.octacer",
  "password": "P@ss1234",
  "report_date": "2024-01-15"
}
```

All fields are optional. Default values:
- `company_code`: "85"
- `username`: "hisham.octacer"
- `password`: "P@ss1234"
- `report_date`: Today's date (format: YYYY-MM-DD)

**Response:**
- Success: Excel file download (Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet)
- Error: JSON with error details

### Example API Calls

**Using the GET endpoint (simplest):**
```bash
# Download today's report with default credentials
curl http://localhost:8000/get-report-default --output report.xlsx

# Or use wget
wget http://localhost:8000/get-report-default -O report.xlsx

# Works in browser too - just visit:
# http://localhost:8000/get-report-default
```

**Using curl:**
```bash
# Generate today's report with default credentials
curl -X POST http://localhost:8000/generate-report \
  -H "Content-Type: application/json" \
  -d '{}' \
  --output report.xlsx

# Generate report for specific date
curl -X POST http://localhost:8000/generate-report \
  -H "Content-Type: application/json" \
  -d '{
    "company_code": "85",
    "username": "hisham.octacer",
    "password": "P@ss1234",
    "report_date": "2024-01-15"
  }' \
  --output report_2024-01-15.xlsx
```

**Using Python requests:**
```python
import requests

url = "http://localhost:8000/generate-report"
data = {
    "company_code": "85",
    "username": "hisham.octacer",
    "password": "P@ss1234",
    "report_date": "2024-01-15"
}

response = requests.post(url, json=data)

if response.status_code == 200:
    with open("report.xlsx", "wb") as f:
        f.write(response.content)
    print("Report downloaded successfully!")
else:
    print(f"Error: {response.json()}")
```

**Using JavaScript/fetch:**
```javascript
fetch('http://localhost:8000/generate-report', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    company_code: '85',
    username: 'hisham.octacer',
    password: 'P@ss1234',
    report_date: '2024-01-15'
  })
})
.then(response => response.blob())
.then(blob => {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'report.xlsx';
  a.click();
});
```

### GET /health

Health check endpoint to verify API is running.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00"
}
```

## Configuration

### Changing Default Credentials

Edit the default values in `api_server.py`:

```python
class ReportRequest(BaseModel):
    company_code: str = "YOUR_COMPANY_CODE"
    username: str = "YOUR_USERNAME"
    password: str = "YOUR_PASSWORD"
    report_date: Optional[str] = None
```

### Changing Download Directory

When initializing the automation class:

```python
automation = SekureIDAutomation(download_dir="/path/to/downloads")
```

### Headless Mode (AWS/Cloud Servers)

The application is **already configured for headless operation** and will work perfectly on:
- AWS EC2 instances
- Google Cloud Compute
- Azure VMs
- DigitalOcean Droplets
- Any server accessed via SSH without GUI

Chrome runs with `--headless=new` flag which is the latest and most stable headless mode. No Xvfb or virtual display needed!

## Project Structure

```
cloud_sekureid/
├── .github/
│   └── workflows/
│       └── docker-build.yml    # GitHub Actions CI/CD workflow
├── sekureid_automation.py      # Core Selenium automation script
├── api_server.py               # FastAPI REST API wrapper
├── api-test.http               # HTTP test file for VS Code REST Client
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Docker container configuration
├── docker-compose.yml          # Docker Compose configuration
├── .dockerignore               # Docker ignore file
├── .gitignore                  # Git ignore file
├── README.md                   # This file
├── downloads/                  # Default download directory (created automatically)
└── temp_reports/               # Temporary files for API (created automatically)
```

## Testing the API

### Using the .http File

The project includes an `api-test.http` file for easy API testing. You can use it with:
- **VS Code**: Install the [REST Client extension](https://marketplace.visualstudio.com/items?itemName=humao.rest-client)
- **IntelliJ IDEA / WebStorm**: Built-in HTTP Client

**Quick Start:**
1. Open `api-test.http` in your IDE
2. Change the `@baseUrl` variable if needed (default: `https://sekureid.octacer.info`)
3. Click "Send Request" above any request

The file includes:
- Health check tests
- GET endpoint for quick daily reports
- POST endpoint with various parameter combinations
- Error testing scenarios
- Helpful comments and examples

## Troubleshooting

### Docker Issues

**Container fails to start:**
```bash
# Check logs
docker-compose logs -f

# Check container status
docker ps -a

# Rebuild from scratch
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

**Chromium/Browser issues in Docker:**
- Chrome runs in native headless mode (--headless=new) - no virtual display needed
- If you see browser crashes, ensure `--shm-size=2g` is set (required for Chromium)
- If you see "DevToolsActivePort file doesn't exist", it usually means Chrome crashed - check memory limits
- Check logs: `docker-compose logs -f`

**Permission errors:**
- The container runs as non-root user `appuser`
- If mounting volumes, ensure permissions are correct

### Python Direct Installation Issues

**Chrome/ChromeDriver Version Mismatch:**

If you get an error about ChromeDriver version:
1. Check your Chrome version: `google-chrome --version` or `chromium --version`
2. Download matching ChromeDriver from https://chromedriver.chromium.org/
3. Update your PATH or specify the driver location

### General Issues

**Login Fails:**

- Verify credentials are correct
- Check if the website structure has changed
- Ensure you have network access to cloud.sekure-id.com
- Check API logs for detailed error messages

**Download Times Out:**

- Increase timeout in `wait_for_download()` method
- Check network speed
- Verify the report is generating correctly on the website

**API Returns 500 Error:**

- Check the API logs for detailed error messages
- If using Docker: `docker-compose logs -f`
- If using Python directly: Check console output
- Ensure ChromeDriver is properly installed (or use Docker to avoid this issue)
- Verify all dependencies are installed: `pip install -r requirements.txt`

**Report generation takes too long:**

- The first run may take longer as the browser initializes
- Typical generation time: 15-30 seconds
- If consistently slow, check your network connection to cloud.sekure-id.com

## Security Considerations

- **Do not commit credentials** to version control
- Consider using environment variables for sensitive data:
  ```python
  import os
  username = os.getenv("SEKUREID_USERNAME")
  password = os.getenv("SEKUREID_PASSWORD")
  ```
- Use HTTPS in production
- Implement authentication for the API endpoint
- Rate limit the API to prevent abuse

## CI/CD Pipeline (GitHub Actions)

This project includes automated CI/CD using GitHub Actions. The workflow automatically:

1. **Builds Docker images** when you push to `main` or `dev` branches
2. **Pushes to GitHub Container Registry** (ghcr.io)
3. **Tags images appropriately**:
   - `main` branch → `project-prod:latest`
   - `dev` branch → `project-dev:latest`
4. **Triggers deployment webhook** for production (main branch only)

### Workflow Triggers

The GitHub Actions workflow runs when:
- Push to `main` or `dev` branches
- Changes to Python files (`**/*.py`)
- Changes to `requirements.txt`, `Dockerfile`, or `docker-compose.yml`
- Version tags (e.g., `v1.0.0`)

### Using Published Images

After the workflow runs, you can pull and use the published images:

```bash
# Pull the production image
docker pull ghcr.io/octacer/cloud-sekureid-prod:latest

# Run it
docker run -d \
  -p 8000:8000 \
  --shm-size=2g \
  ghcr.io/octacer/cloud-sekureid-prod:latest
```

### Setting Up CI/CD

To use the GitHub Actions workflow:

1. **Enable GitHub Actions** in your repository settings
2. **Configure self-hosted runner** (if using `[self-hosted, octacer_info]`)
   - Or change to `runs-on: ubuntu-latest` for GitHub-hosted runners
3. **Grant permissions**:
   - Go to Settings → Actions → General
   - Enable "Read and write permissions" for GITHUB_TOKEN
4. **Push your code** to `main` or `dev` branch

The workflow will automatically build and publish Docker images to GitHub Container Registry.

### Deployment Webhook

The workflow triggers an automatic deployment webhook for production:
```bash
curl -s -X GET "https://automation.octacer.info/webhook/prod-vm-deploy?project=cloud-sekureid"
```

This webhook should pull the latest image and restart the service on your production server.

## Production Deployment

### Docker Deployment (Recommended)

**Using Docker Compose:**

1. Edit `docker-compose.yml` to set your credentials:
```yaml
environment:
  - SEKUREID_COMPANY_CODE=your_code
  - SEKUREID_USERNAME=your_username
  - SEKUREID_PASSWORD=your_password
```

2. Deploy:
```bash
docker-compose up -d
```

3. Set up nginx reverse proxy with SSL:
```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Increase timeout for report generation
        proxy_read_timeout 120s;
        proxy_connect_timeout 120s;
    }
}
```

4. Enable monitoring:
```bash
# View logs
docker-compose logs -f

# Set up log rotation
docker-compose up -d --log-opt max-size=10m --log-opt max-file=3
```

**Production Considerations:**

1. **Use environment variables for credentials** (never hardcode in files)
2. **Run behind a reverse proxy (nginx/traefik)** with HTTPS
3. **Add authentication/API keys** to protect the endpoint
4. **Set up logging and monitoring** (ELK stack, Prometheus, etc.)
5. **Configure resource limits** in docker-compose.yml
6. **Enable automatic container restart** (already configured in docker-compose.yml)
7. **Regular backups** of configuration and data
8. **Health checks** (already configured)

### Python Direct Deployment

For systemd service (if not using Docker):

```ini
[Unit]
Description=Sekure-ID Report Generator API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/cloud_sekureid
Environment="PATH=/usr/bin:/usr/local/bin"
Environment="DISPLAY=:99"
ExecStartPre=/usr/bin/Xvfb :99 -screen 0 1920x1080x24 &
ExecStart=/usr/bin/python3 api_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## License

This is an internal automation tool for Octacer. Use at your own risk.

## Support

For issues or questions, contact the development team.
