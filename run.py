"""
Entry point for the web app.

Usage:
    python run.py

Then open http://127.0.0.1:5000 in a browser.
"""

import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    # threaded=True matters here: the MJPEG stream route blocks on a
    # generator, so without threading a single request would tie up
    # the whole dev server and nothing else could load.
    debug = os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
    app.run(debug=debug, threaded=True)