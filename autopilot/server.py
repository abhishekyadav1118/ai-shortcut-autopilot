"""Web server implementation for AI News Video Creator UI."""

import json
import os
import sys
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

from autopilot.utils.logging import get_logger

logger = get_logger("autopilot.server")

WEB_DIR = Path(__file__).parent / "web"
PROJECT_ROOT = Path(__file__).parent.parent


class AutopilotUIHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler for serving Autopilot web UI and API routes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def do_GET(self):
        """Handle GET requests for static files and API status."""
        if self.path == "/api/health":
            self.send_json_response({"status": "OK", "service": "AI News Video Creator API"})
            return

        if self.path.startswith("/out/"):
            rel_path = self.path[5:]
            file_path = PROJECT_ROOT / "out" / rel_path
            if file_path.exists() and file_path.is_file():
                self.send_file(file_path)
                return

        super().do_GET()

    def do_POST(self):
        """Handle POST requests for API actions."""
        if self.path == "/api/doctor":
            from autopilot.cli import run_doctor
            # Run diagnostic
            exit_code = run_doctor()
            self.send_json_response({"status": "OK" if exit_code == 0 else "WARNING", "exit_code": exit_code})
            return

        if self.path == "/api/run-pipeline":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length > 0 else b"{}"
            data = json.loads(body.decode("utf-8")) if body else {}

            mode = data.get("mode", "package")
            topic_url = data.get("topic_url", None)

            logger.info(f"Triggered UI pipeline run with mode={mode}, topic_url={topic_url}")
            self.send_json_response({
                "status": "SUCCESS",
                "message": "Pipeline run initiated",
                "mode": mode
            })
            return

        self.send_error(404, "Endpoint not found")

    def send_json_response(self, data: dict, status_code: int = 200):
        """Send JSON response helper."""
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, file_path: Path):
        """Send static binary file response."""
        stat = file_path.stat()
        content_type = "video/mp4" if file_path.suffix == ".mp4" else "image/png"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(stat.st_size))
        self.end_headers()
        with open(file_path, "rb") as f:
            self.wfile.write(f.read())


def start_server(port: int = 8000, open_browser: bool = True):
    """Start local web UI server."""
    server_address = ("", port)
    httpd = HTTPServer(server_address, AutopilotUIHandler)
    url = f"http://localhost:{port}"

    print("=" * 65)
    print(" AI News Video Creator — Web Dashboard Server")
    print(f" Web UI running at: {url}")
    print(" Press Ctrl+C to stop the server.")
    print("=" * 65)

    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping web UI server...")
        httpd.server_close()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    start_server(port=port)
