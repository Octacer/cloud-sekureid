# Quick Debug Reference for Sekure-ID API

## 🚨 When An Error Occurs

### Step 1: Check API Error Response

The API returns debug information:
```json
{
  "error": "Could not find Excel button",
  "debug": {
    "debug_id": "abc-123-def-456",
    "debug_files": [...],
    "view_all_url": "https://sekureid.octacer.info/debug/abc-123"
  }
}
```

### Step 2: View Screenshots (Choose One Method)

#### 🌐 Method 1: Direct Browser Access (Easiest!)
```
https://sekureid.octacer.info/files/debug_abc-123/error_screenshot.png
https://sekureid.octacer.info/files/debug_abc-123/error_page_source.html
```

#### 📁 Method 2: Check Volume Mount (You Have This!)
```bash
cd /var/www/projects/cloud-sekureid/sekureId_downloads
ls -lah debug_*/
cd debug_abc-123/
# Files: error_screenshot.png, error_page_source.html, page_source.html
```

#### 💻 Method 3: Download via curl
```bash
curl https://sekureid.octacer.info/files/debug_abc-123/error_screenshot.png --output error.png
```

#### 📋 Method 4: List All Debug Sessions
```bash
curl https://sekureid.octacer.info/debug
```

### Step 3: Check Logs

```bash
docker logs cloud-sekureid --tail=100
```

Look for:
- `→ Current URL:` - Where the browser is
- `→ Found X links` - If buttons/links are found
- `Method X failed:` - Which detection method failed

## 🔍 Common Issues & Solutions

| What You See | Problem | Solution |
|--------------|---------|----------|
| `→ Current URL: .../DailyReports` (never changes) | New tab didn't open | Check form submission |
| `→ Found 0 links` | Page not loaded | Increase wait time |
| `$find is not defined` | ASP.NET not ready | Increase wait time (already improved) |
| `→ Window handles: 1` | No new tab | Form didn't trigger report |

## 📱 Quick Commands

```bash
# View logs live
docker logs -f cloud-sekureid

# List all debug sessions
curl https://sekureid.octacer.info/debug | jq

# Get specific debug session
curl https://sekureid.octacer.info/debug/abc-123 | jq

# Download latest screenshot from server
cd /var/www/projects/cloud-sekureid/sekureId_downloads
ls -lt debug_*/error_screenshot.png | head -1

# Copy to local machine (from your laptop)
scp ubuntu@server-ip:/var/www/projects/cloud-sekureid/sekureId_downloads/debug_abc-123/error_screenshot.png ./
```

## 🎯 Typical Debugging Workflow

1. **Run report generation** → It fails
2. **Check API response** → Get `debug_id`
3. **Open screenshot URL** in browser → See what's on screen
4. **Check logs** → See detailed execution flow
5. **Analyze issue** → Screenshot + logs show the problem
6. **Fix code** → Update wait times, selectors, etc.
7. **Rebuild** → `docker-compose up -d --build`

## 📊 API Endpoints Summary

| Endpoint | Purpose |
|----------|---------|
| `GET /debug` | List all debug sessions |
| `GET /debug/{id}` | Get files for specific session |
| `GET /files/debug_{id}/{file}` | Download specific debug file |
| `GET /health` | Check if API is running |

## 💡 Pro Tips

1. **Use volume mounts** - Already configured! Files appear in `./sekureId_downloads/`
2. **Check timestamps** - `ls -lt` shows newest first
3. **Use jq** - Format JSON nicely: `curl ... | jq`
4. **Watch logs live** - `docker logs -f cloud-sekureid`
5. **Screenshot tells all** - Visual snapshot worth 1000 log lines

## 🔗 Your Setup

- **Server**: `/var/www/projects/cloud-sekureid`
- **Downloads**: `./sekureId_downloads` (mapped to container)
- **Container**: `cloud-sekureid`
- **Port**: `3003:8000`
- **URL**: `https://sekureid.octacer.info`

## ⚡ One-Liner Shortcuts

```bash
# Latest error screenshot
cd /var/www/projects/cloud-sekureid/sekureId_downloads && ls -t debug_*/error_screenshot.png | head -1 | xargs cat

# Count debug sessions
ls -d /var/www/projects/cloud-sekureid/sekureId_downloads/debug_* | wc -l

# Find today's debug sessions
find /var/www/projects/cloud-sekureid/sekureId_downloads -type d -name "debug_*" -mtime -1

# View latest logs
docker logs cloud-sekureid --tail=50 --follow
```
