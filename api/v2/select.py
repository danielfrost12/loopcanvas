"""
POST /api/v2/select — Select a visual direction and start generation
"""
import json
import os
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        data = json.loads(body)

        job_id = data.get('job_id')
        direction_id = data.get('direction_id')

        if not job_id or not direction_id:
            self._json(400, {"error": "Missing job_id or direction_id"})
            return

        # Proxy to GPU server if available
        gen_server = os.environ.get('GENERATION_SERVER', '')
        gpu_error = None
        if gen_server:
            import urllib.request
            import urllib.error
            try:
                req = urllib.request.Request(
                    f"{gen_server}/api/v2/select",
                    data=json.dumps(data).encode(),
                    headers={
                        "Content-Type": "application/json",
                        "Bypass-Tunnel-Reminder": "true",
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    result = json.loads(resp.read())
                    result["mode"] = "gpu"
                    self._json(200, result)
                    return
            except urllib.error.HTTPError as e:
                try:
                    error_body = json.loads(e.read())
                    error_body["mode"] = "gpu"
                    self._json(e.code, error_body)
                except Exception:
                    self._json(e.code, {"error": str(e), "mode": "gpu"})
                return
            except Exception as e:
                gpu_error = str(e)
                print(f"[Select] GPU server error: {e}")

        # GPU server unreachable — return error, never fall back to demo
        self._json(503, {
            "error": "GPU server unreachable",
            "gpu_error": gpu_error,
            "mode": "error",
        })

    def _json(self, code, data):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
