"""
Universal /api/v2/* proxy — forwards ALL v2 API calls to GPU server.

Handles: iterate, extend, edit, export, undo, platforms, cost-report, directions
Single function to stay under Vercel's 12-function limit on Hobby plan.
"""
import json
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse


class handler(BaseHTTPRequestHandler):
    def _proxy(self, method="POST"):
        """Forward request to GPU server."""
        gen_server = os.environ.get('GENERATION_SERVER', '')
        if not gen_server:
            self._json(503, {"error": "GENERATION_SERVER not configured"})
            return

        # Reconstruct the path from the original request
        parsed = urlparse(self.path)
        target_path = parsed.path  # e.g. /api/v2/iterate
        target_url = f"{gen_server}{target_path}"
        if parsed.query:
            target_url += f"?{parsed.query}"

        import urllib.request
        import urllib.error

        headers = {
            "Bypass-Tunnel-Reminder": "true",
        }

        body = None
        if method == "POST":
            content_type = self.headers.get('Content-Type', 'application/json')
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                body = self.rfile.read(content_length)
            headers["Content-Type"] = content_type
            if body:
                headers["Content-Length"] = str(len(body))

        try:
            req = urllib.request.Request(
                target_url,
                data=body,
                headers=headers,
                method=method
            )
            with urllib.request.urlopen(req, timeout=300) as resp:
                content_type = resp.headers.get('Content-Type', 'application/octet-stream')
                result = resp.read()

                # Binary content (video, images, audio) — pass through directly
                if not content_type.startswith('application/json') and not content_type.startswith('text/'):
                    self.send_response(resp.getcode())
                    self.send_header('Content-Type', content_type)
                    self.send_header('Content-Length', str(len(result)))
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Cache-Control', 'public, max-age=3600')
                    self.end_headers()
                    self.wfile.write(result)
                    return

                # JSON response — parse and forward
                try:
                    data = json.loads(result)
                    self._json(resp.getcode(), data)
                except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
                    self.send_response(resp.getcode())
                    self.send_header('Content-Type', content_type)
                    self.send_header('Content-Length', str(len(result)))
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(result)
        except urllib.error.HTTPError as e:
            try:
                error_body = json.loads(e.read())
                self._json(e.code, error_body)
            except Exception:
                self._json(e.code, {"error": str(e)})
        except Exception as e:
            self._json(503, {
                "error": "Generation server not available",
                "gpu_error": str(e),
            })

    def do_POST(self):
        self._proxy("POST")

    def do_GET(self):
        self._proxy("GET")

    def _json(self, code, data):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache, no-store')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
