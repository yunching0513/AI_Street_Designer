import sys
import os

# Get the directory paths
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)

# Add parent directory to path so we can import app
sys.path.insert(0, parent_dir)

# Import the Flask app
from app import app

# Vercel serverless function handler
# The app is automatically exposed for Vercel to handle WSGI requests
