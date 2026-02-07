"""
POST /api/v2/queue/claim — Worker claims next job from queue
Used by HuggingFace Spaces GPU worker to claim generation jobs.
"""
import json
import os
import tempfile
from http.server import BaseHTTPRequestHandler
from pathlib import Path


# Job queue stored as JSON in /tmp (Vercel serverless)
QUEUE_DIR = Path(tempfile.gettempdir()) / "loopcanvas_queue"
QUEUE_DIR.mkdir(exist_ok=True)


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        data = json.loads(body) if body else {}

        worker_id = data.get('worker_id', 'unknown')
        worker_type = data.get('worker_type', 'unknown')

        # Scan queue directory for pending jobs
        pending_jobs = []
        for job_file in sorted(QUEUE_DIR.glob("job_*.json")):
            try:
                job = json.loads(job_file.read_text())
                if job.get("status") == "pending":
                    pending_jobs.append((job_file, job))
            except (json.JSONDecodeError, IOError):
                continue

        if not pending_jobs:
            self._json(200, {"job": None, "message": "No pending jobs"})
            return

        # Claim the oldest pending job
        job_file, job = pending_jobs[0]
        job["status"] = "claimed"
        job["worker_id"] = worker_id
        job["worker_type"] = worker_type
        job_file.write_text(json.dumps(job, indent=2))

        self._json(200, {"job": job})

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
