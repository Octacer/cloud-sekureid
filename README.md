# Sekure-ID Cloud Report Generator

**Automate your daily attendance reports - Get Excel files instantly without logging in manually!**

## What Is This?

This is a simple tool that automatically generates and downloads your daily attendance reports from Sekure-ID Cloud. Instead of logging in to the website every day, just run this tool and get your Excel report in seconds.

## Key Benefits

✨ **No Manual Work** - Fully automatic report generation
⚡ **Quick & Easy** - One command, get your report
🔒 **Secure** - Your credentials are never stored or exposed
☁️ **Cloud Ready** - Works on any server, no desktop needed
📦 **Docker Included** - Everything is packaged, no installation hassle

## Getting Started (Quick Start)

### Option 1: Docker (Easiest)

```bash
# Clone the project
cd /path/to/cloud_sekureid

# Start the service
docker-compose up -d

# Get your report
curl http://localhost:8000/get-report-default --output report.xlsx
```

That's it! Your report is downloaded as `report.xlsx`

### Option 2: Command Line

```bash
# Install dependencies
pip install -r requirements.txt

# Generate today's report
python sekureid_automation.py
```

Your Excel file will be saved in the `downloads/` folder.

## How to Use the API

Once running, you can access your reports through a simple API:

**Get today's report:**
```bash
curl http://localhost:8000/get-report-default --output report.xlsx
```

**Get a report for a specific date:**
```bash
curl http://localhost:8000/generate-report \
  -H "Content-Type: application/json" \
  -d '{"report_date": "2024-01-15"}' \
  --output report.xlsx
```

**Check if the service is running:**
```bash
curl http://localhost:8000/health
```

## Documentation

Looking for more detailed information? Check the documentation folder:

- **[TECHNICAL_README.md](docs/TECHNICAL_README.md)** - Complete technical documentation with API details and troubleshooting
- **[DEPLOYMENT.md](docs/DEPLOYMENT.md)** - How to deploy on Ubuntu servers
- **[QUICK_SETUP_GUIDE.md](docs/QUICK_SETUP_GUIDE.md)** - Fast setup for existing servers
- **[TESSERACT_SETUP.md](docs/TESSERACT_SETUP.md)** - OCR text extraction setup
- **[DEBUG_QUICK_REFERENCE.md](docs/DEBUG_QUICK_REFERENCE.md)** - Quick troubleshooting guide

All other documentation is in the [docs/](docs/) folder.

## Common Tasks

### Access the Web Interface
Visit `http://localhost:8000/docs` to see all available API endpoints and test them from your browser.

### View Logs (Docker)
```bash
docker-compose logs -f
```

### Stop the Service
```bash
docker-compose down
```

### Restart the Service
```bash
docker-compose restart
```

## Requirements

**With Docker:**
- Docker and Docker Compose (that's it!)

**Without Docker:**
- Python 3.8 or newer
- Chrome or Chromium browser
- ChromeDriver

## What Happens Behind the Scenes?

1. The tool logs into Sekure-ID Cloud with your credentials
2. Navigates to the reports section
3. Generates today's attendance report
4. Exports it as an Excel file
5. Returns the file to you

All of this happens automatically without any human interaction needed.

## Support & Help

For technical details and troubleshooting:
- See [TECHNICAL_README.md](docs/TECHNICAL_README.md)
- Check [DEBUG_QUICK_REFERENCE.md](docs/DEBUG_QUICK_REFERENCE.md) for common issues

## License

Internal tool for Octacer.
