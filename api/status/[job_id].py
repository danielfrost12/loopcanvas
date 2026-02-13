"""
GET /api/status/:job_id — Check generation status
Proxies to GPU server. No demo fallback.
"""
import json
import os
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Extract job_id from path
        path_parts = self.path.strip('/').split('/')
        job_id = path_parts[-1].split('?')[0] if path_parts else None

        if not job_id:
            self._json(400, {"error": "Missing job_id"})
            return

        # Check GPU generation server
        gen_server = os.environ.get('GENERATION_SERVER', '')
        gpu_error = None

        if gen_server:
            import urllib.request
            import urllib.error
            try:
                api_key = os.environ.get('GPU_API_KEY', '')
                hdrs = {"Bypass-Tunnel-Reminder": "true"}
                if api_key:
                    hdrs["Authorization"] = f"Bearer {api_key}"
                req = urllib.request.Request(
                    f"{gen_server}/api/status/{job_id}",
                    method="GET",
                    headers=hdrs,
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
                print(f"[Status] GPU server error: {e}")

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
