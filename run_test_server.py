"""Starts the app on port 5001 (mock mode) for API testing."""
from app import app

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5001, debug=False, use_reloader=False)
