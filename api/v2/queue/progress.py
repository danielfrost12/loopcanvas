"""
POST /api/v2/queue/progress — Worker reports generation progress
"""
import json
import tempfile
from http.server import BaseHTTPRequestHandler
from pathlib import Path


QUEUE_DIR = Path(tempfile.gettempdir()) / "loopcanvas_queue"
QUEUE_DIR.mkdir(exist_ok=True)


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        data = json.loads(body) if body else {}

        job_id = data.get('job_id')
        progress = data.get('progress', 0)
        message = data.get('message', '')

        if not job_id:
            self._json(400, {"error": "Missing job_id"})
            return

        # Update job file
        job_file = QUEUE_DIR / f"job_{job_id}.json"
        if job_file.exists():
            try:
                job = json.loads(job_file.read_text())
                job["progress"] = progress
                job["message"] = message
                job["status"] = "generating"
                job_file.write_text(json.dumps(job, indent=2))
            except (json.JSONDecodeError, IOError):
                pass

        self._json(200, {"ok": True})

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
