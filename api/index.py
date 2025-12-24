import sys
import os

# Add parent directory to path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import app

# Vercel expects the Flask app to be exposed as 'app'
# This allows Vercel to handle WSGI requests
