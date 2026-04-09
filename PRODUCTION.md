# Production Deployment Guide

This guide covers running the Classification Vote application with a production WSGI server.

## Quick Start

### 1. Install Gunicorn

```bash
pip install -r requirements.txt
```

### 2. Run with the startup script

```bash
# Default port 5000
./start_production.sh

# Custom port (e.g., 8080)
./start_production.sh 8080
```

The server will be available at:
- **Local access**: `http://localhost:5000`
- **Network access**: `http://YOUR_SERVER_IP:5000` (e.g., `http://192.168.1.100:5000`)

The server binds to `0.0.0.0` (all network interfaces), making it accessible from other machines on your network.

**Security Note**: When binding to `0.0.0.0`, ensure your firewall is properly configured and only trusted users have network access. For public deployments, use nginx with SSL/TLS.

### Finding Your Server IP Address

To find your server's IP address for network access:

```bash
# macOS/Linux
ifconfig | grep "inet " | grep -v 127.0.0.1

# Or on macOS
ipconfig getifaddr en0  # Usually WiFi
ipconfig getifaddr en1  # Usually Ethernet

# Linux
hostname -I
```

Share this IP address with users who need to access the application from other machines.

## Production Configuration

### Using Gunicorn Directly

```bash
# Basic usage
gunicorn wsgi:app

# With configuration file
gunicorn -c gunicorn.conf.py wsgi:app

# Custom port and workers
gunicorn --bind 127.0.0.1:8080 --workers 4 wsgi:app
```

### Configuration Options

Edit `gunicorn.conf.py` to customize:

- **Workers**: Number of worker processes (default: 4)
  - Recommended: 2-4 × CPU cores
  - For CPU-bound apps: CPU cores × 2 + 1
  - For I/O-bound apps: More workers help

- **Timeout**: Worker timeout in seconds (default: 120)
  - Increase if you have long-running requests

- **Reload**: Auto-reload on code changes (default: True for development)
  - Set to False for production

- **Logging**: Access and error logs (default: stdout/stderr)

### Environment Variables

Set these before starting the server:

```bash
# Flask environment (development/production)
export FLASK_ENV=production

# Secret key for sessions (IMPORTANT: use a random string)
export SECRET_KEY='your-secret-key-here'

# Database URL (optional, defaults to SQLite)
export SQLALCHEMY_DATABASE_URI='sqlite:///instance/classification.db'
```

## Running as a System Service (macOS/Linux)

### Option 1: Using launchd (macOS)

Create `~/Library/LaunchAgents/edu.yale.classification-vote.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>edu.yale.classification-vote</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/gunicorn</string>
        <string>-c</string>
        <string>/path/to/classification-vote/gunicorn.conf.py</string>
        <string>wsgi:app</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/classification-vote</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/classification-vote.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/classification-vote-error.log</string>
</dict>
</plist>
```

Load and start:
```bash
launchctl load ~/Library/LaunchAgents/edu.yale.classification-vote.plist
launchctl start edu.yale.classification-vote
```

### Option 2: Using systemd (Linux)

Create `/etc/systemd/system/classification-vote.service`:

```ini
[Unit]
Description=Classification Vote Application
After=network.target

[Service]
User=your-username
Group=your-group
WorkingDirectory=/path/to/classification-vote
Environment="PATH=/path/to/classification-vote/venv/bin"
ExecStart=/path/to/classification-vote/venv/bin/gunicorn -c gunicorn.conf.py wsgi:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable classification-vote
sudo systemctl start classification-vote
sudo systemctl status classification-vote
```

## Nginx Reverse Proxy (Optional)

If you want to use nginx as a reverse proxy:

### 1. Install nginx

```bash
# macOS
brew install nginx

# Ubuntu/Debian
sudo apt-get install nginx
```

### 2. Configure nginx

Create `/usr/local/etc/nginx/servers/classification-vote.conf` (macOS) or
`/etc/nginx/sites-available/classification-vote` (Linux):

```nginx
server {
    listen 80;
    server_name your-domain.com;  # or localhost

    # Increase timeouts for long-running requests
    proxy_connect_timeout 120s;
    proxy_send_timeout 120s;
    proxy_read_timeout 120s;

    location / {
        # Forward to Gunicorn
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static {
        # Serve static files directly (more efficient)
        alias /path/to/classification-vote/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

On Linux, enable the site:
```bash
sudo ln -s /etc/nginx/sites-available/classification-vote /etc/nginx/sites-enabled/
```

Restart nginx:
```bash
# macOS
brew services restart nginx

# Linux
sudo systemctl restart nginx
```

### 3. Start your application

```bash
./start_production.sh
```

Now your app is available at `http://your-domain.com` with nginx handling incoming requests.

## Performance Tips

1. **Use multiple workers**: Start with 4, adjust based on your CPU
2. **Monitor memory**: Each worker uses memory, watch total usage
3. **Enable caching**: Consider Redis for session/vote caching
4. **Static files**: Serve with nginx in production (faster than Flask)
5. **Database**: Consider PostgreSQL for better concurrency than SQLite
6. **Load balancing**: Run multiple gunicorn instances behind nginx

## Troubleshooting

### Workers timing out
Increase `timeout` in `gunicorn.conf.py`

### High memory usage
Reduce number of workers or enable `max_requests` to recycle workers

### Slow response times
- Increase workers
- Check database performance
- Enable caching
- Use nginx for static files

### Can't bind to port
- Port already in use: `lsof -i :5000`
- Permission denied: Use port > 1024 or run with sudo (not recommended)

## Monitoring

### View logs
```bash
# If running in terminal
# Logs go to stdout/stderr

# If running as service (macOS)
tail -f /tmp/classification-vote.log

# If running as service (Linux)
sudo journalctl -u classification-vote -f
```

### Check worker status
```bash
ps aux | grep gunicorn
```

### Monitor requests
Gunicorn access logs show all incoming requests with response times.

## Security Considerations

1. **Never run as root**: Use a dedicated user account
2. **Set SECRET_KEY**: Use a random, strong secret key
3. **Use HTTPS**: Configure nginx with SSL/TLS certificates
4. **Firewall**: Only expose necessary ports
5. **Update dependencies**: Regularly update Flask and dependencies
6. **Rate limiting**: Consider nginx rate limiting for public deployments
