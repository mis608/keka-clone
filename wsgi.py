"""WSGI entry point for production servers (gunicorn, etc.)"""
from app import app

if __name__ == "__main__":
    app.run()
