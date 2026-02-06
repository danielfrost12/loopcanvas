"""
POST /api/generate — Start generation for an uploaded file
In serverless mode: dispatches to GPU worker or returns demo
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
        if not job_id:
            self._json(400, {"error": "Missing job_id"})
            return

        # Check if we have a generation server configured
        gen_server = os.environ.get('GENERATION_SERVER', '')

        if gen_server:
            # Proxy to GPU generation server
            import urllib.request
            try:
                req = urllib.request.Request(
                    f"{gen_server}/api/generate",
                    data=json.dumps(data).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    result = json.loads(resp.read())
                    self._json(200, result)
                    return
            except Exception as e:
                print(f"[Generate] GPU server error: {e}")

        # Fallback: return success with demo mode
        self._json(200, {
            "success": True,
            "job_id": job_id,
            "status": "generating",
            "mode": "demo",
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
