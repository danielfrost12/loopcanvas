"""
POST /api/track — Receive frontend analytics events, append to JSONL
Body: { "event": "upload_start", "data": {...}, "ts": 1234567890, "session_id": "..." }
Appends to /tmp/events.jsonl (Vercel serverless /tmp — 512 MB)
Also tries canvas-engine/checklist_data/onboarding_funnel.jsonl if writable
"""
import json
import os
import time
from http.server import BaseHTTPRequestHandler

EVENTS_FILE = '/tmp/events.jsonl'
FUNNEL_FILE = os.path.join(
    os.path.dirname(__file__), '..',
    'canvas-engine', 'checklist_data', 'onboarding_funnel.jsonl'
)

VALID_EVENTS = {
    'page_load',
    'upload_start',
    'upload_complete',
    'analyze_start',
    'director_select',
    'generate_start',
    'generate_complete',
    'export',
    'share',
    'return_visit',
}


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            self._json(400, {"ok": False, "error": "Empty request body"})
            return

        try:
            body = json.loads(self.rfile.read(content_length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._json(400, {"ok": False, "error": "Invalid JSON"})
            return

        event = body.get('event', '')
        if event not in VALID_EVENTS:
            self._json(400, {
                "ok": False,
                "error": f"Unknown event: {event}",
                "valid_events": sorted(VALID_EVENTS),
            })
            return

        # Build the record with server-side received timestamp
        record = {
            "event":      event,
            "data":       body.get('data', {}),
            "ts":         body.get('ts', int(time.time() * 1000)),
            "session_id": body.get('session_id', ''),
            "received":   int(time.time() * 1000),
        }

        line = json.dumps(record, separators=(',', ':')) + '\n'

        # Primary: append to /tmp/events.jsonl (always writable on Vercel)
        try:
            with open(EVENTS_FILE, 'a') as f:
                f.write(line)
        except OSError as e:
            self._json(500, {"ok": False, "error": f"Write failed: {e}"})
            return

        # Secondary: also try onboarding funnel log (best-effort, ignore errors)
        try:
            os.makedirs(os.path.dirname(FUNNEL_FILE), exist_ok=True)
            with open(FUNNEL_FILE, 'a') as f:
                f.write(line)
        except OSError:
            pass  # Not writable in Vercel prod — that's fine

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
