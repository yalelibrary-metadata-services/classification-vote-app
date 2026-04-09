"""
WSGI entry point for production deployment.

This file is used by WSGI servers (like gunicorn) to run the application.
"""

from app import create_app

# Create the application instance
app = create_app()

if __name__ == "__main__":
    # This allows running with: python wsgi.py
    # But for production, use: gunicorn wsgi:app
    app.run()
