"""
Gunicorn configuration file for Classification Vote application.

This file can be used with: gunicorn -c gunicorn.conf.py wsgi:app
"""

import multiprocessing

# Server Socket
bind = "0.0.0.0:5000"  # Bind to all network interfaces (accessible from other machines)
backlog = 2048

# Worker Processes
workers = 4  # Number of worker processes (recommended: 2-4 x CPU cores)
worker_class = "sync"  # sync, gevent, eventlet
worker_connections = 1000
max_requests = 1000  # Restart workers after this many requests (prevents memory leaks)
max_requests_jitter = 50
timeout = 120  # Workers silent for more than this many seconds are killed
keepalive = 5  # Wait this many seconds for next request on Keep-Alive connection

# Logging
accesslog = "-"  # Log to stdout
errorlog = "-"   # Log to stderr
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process Naming
proc_name = "classification-vote"

# Server Mechanics
daemon = False  # Don't daemonize (run in foreground)
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Development vs Production
# For development, enable reload:
reload = True
reload_extra_files = []

# For production, disable reload and increase workers:
# reload = False
# workers = multiprocessing.cpu_count() * 2 + 1
