"""Vercel serverless entry point for the SwapIt Flask application."""
import os
import sys

# Make the project root importable (Vercel preserves the file layout in the
# function bundle: /var/task/api/index.py alongside /var/task/app.py).
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app  # noqa: E402,F401  — Vercel runs this WSGI `app` object
