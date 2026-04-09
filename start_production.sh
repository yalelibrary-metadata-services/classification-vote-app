#!/bin/bash
#
# Start the Classification Vote application with Gunicorn (production WSGI server)
#
# Usage:
#   ./start_production.sh [port]
#
# Default port is 5000 if not specified

PORT=${1:-5000}

echo "Starting Classification Vote application..."
echo "Server will be available at: http://0.0.0.0:$PORT"
echo "Access from other machines using your server's IP address"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start gunicorn with:
# - 4 worker processes for handling concurrent requests
# - Bind to 0.0.0.0 (all network interfaces) on specified port
# - Access logs to stdout
# - Error logs to stderr
# - Worker timeout of 120 seconds for long-running requests
# - Graceful restart on code changes (in development)

gunicorn \
    --workers 4 \
    --bind "0.0.0.0:$PORT" \
    --access-logfile - \
    --error-logfile - \
    --timeout 120 \
    --reload \
    wsgi:app
