#!/usr/bin/env python3
"""
Launcher script for Paddle Matrix macOS App
Starts the FastAPI server and displays UI in a native desktop window
"""

import os
import sys
import threading
import logging

# Fix OpenSSL library conflict on macOS
if sys.platform == 'darwin':
    if hasattr(sys, '_MEIPASS'):
        resources_dir = sys._MEIPASS
    else:
        resources_dir = os.path.dirname(os.path.abspath(__file__))

    homebrew_openssl_paths = [
        '/opt/homebrew/opt/openssl@3/lib',
        '/opt/homebrew/opt/openssl/lib',
        '/usr/local/opt/openssl@3/lib',
        '/usr/local/opt/openssl/lib',
    ]

    for ssl_path in homebrew_openssl_paths:
        if os.path.exists(ssl_path):
            os.environ['DYLD_LIBRARY_PATH'] = ssl_path + ':' + os.environ.get('DYLD_LIBRARY_PATH', '')
            break

# Configure PaddleOCR to use bundled models
if hasattr(sys, '_MEIPASS'):
    bundled_models_dir = os.path.join(sys._MEIPASS, '.paddlex')
    if os.path.exists(bundled_models_dir):
        os.environ['PADDLEX_HOME'] = bundled_models_dir
        os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'


import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def run_server(host: str, port: int):
    """Run the FastAPI server in a background thread"""
    import uvicorn
    from app.main import app

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False
    )


def main():
    """Main entry point"""
    import webview

    from app.main import app
    from app.config import settings

    host = DEFAULT_HOST
    port = settings.PORT
    url = f"http://{host}:{port}/"

    logger.info("=" * 50)
    logger.info("  Paddle Matrix - Video Subtitle OCR Service")
    logger.info("=" * 50)

    # Start server in background thread
    server_thread = threading.Thread(
        target=run_server,
        args=(host, port),
        daemon=True
    )
    server_thread.start()

    # Wait for server to start
    import time
    for _ in range(30):  # Wait up to 30 seconds
        try:
            import urllib.request
            urllib.request.urlopen(url, timeout=1)
            logger.info(f"Server ready at: {url}")
            break
        except:
            time.sleep(0.5)

    # Create native desktop window
    logger.info("Opening application window...")

    window = webview.create_window(
        title='Paddle Matrix - Video Subtitle OCR',
        url=url,
        width=1200,
        height=800,
        min_size=(800, 600),
        background_color='#1a1a2e',
        text_select=True
    )

    # Start the webview event loop (this blocks until window is closed)
    webview.start(debug=False)

    logger.info("Application closed.")


if __name__ == "__main__":
    main()