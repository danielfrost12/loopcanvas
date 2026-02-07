"""
GET /api/health — GPU liveness check for frontend fail-gate

Returns {"gpu": "live"} if GPU server is reachable.
Returns 503 {"gpu": "dead"} if GPU server is down or not configured.

The frontend calls this on page load and blocks the entire UI if GPU is dead.
"""
import json
import os
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        gen_server = os.environ.get('GENERATION_SERVER', '')

        if not gen_server:
            self._json(503, {
                "gpu": "dead",
                "error": "GENERATION_SERVER not configured",
            })
            return

        # Ping the GPU server's health endpoint
        import urllib.request
        import urllib.error
        try:
            req = urllib.request.Request(
                f"{gen_server}/api/health",
                headers={"Bypass-Tunnel-Reminder": "true"},
                method="GET"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                result["gpu"] = "live"
                self._json(200, result)
                return
        except Exception as e:
            self._json(503, {
                "gpu": "dead",
                "error": str(e),
                "server": gen_server,
            })

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
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
