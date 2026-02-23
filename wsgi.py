"""
WSGI entry point for Gunicorn (production).
Calls the app factory so Gunicorn gets a real WSGI app instance, not the factory.
"""
from app import create_app

application = create_app()
