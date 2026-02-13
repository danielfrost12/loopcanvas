"""
POST /api/upload — Handle file upload on Vercel serverless
Proxies to GPU server if GENERATION_SERVER is set, otherwise stores to /tmp
"""
import json
import uuid
import os
import tempfile
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_type = self.headers.get('Content-Type', '')
        content_length = int(self.headers.get('Content-Length', 0))

        if 'multipart/form-data' not in content_type:
            self._json(400, {"error": "Expected multipart/form-data"})
            return

        body = self.rfile.read(content_length)

        # If GPU server is available, proxy the entire upload
        gen_server = os.environ.get('GENERATION_SERVER', '')
        gpu_error = None
        if gen_server:
            import urllib.request
            import urllib.error
            try:
                api_key = os.environ.get('GPU_API_KEY', '')
                req = urllib.request.Request(
                    f"{gen_server}/api/upload",
                    data=body,
                    headers={
                        "Content-Type": content_type,
                        "Content-Length": str(len(body)),
                        "Bypass-Tunnel-Reminder": "true",
                        **({"Authorization": f"Bearer {api_key}"} if api_key else {}),
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=120) as resp:
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
                print(f"[Upload] GPU proxy error: {e}")

        # GPU server unreachable or not configured — return error
        self._json(503, {
            "error": "Generation server not available",
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
