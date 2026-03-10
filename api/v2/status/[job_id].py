"""
GET /api/v2/status/:job_id — V2 status endpoint
"""
import json
import os
import random
from http.server import BaseHTTPRequestHandler


DEMO_VIDEOS = [
    "mood_demos/memory_in_motion_demo.mp4",
    "mood_demos/analog_memory_demo.mp4",
    "mood_demos/midnight_city_demo.mp4",
    "mood_demos/concrete_heat_demo.mp4",
    "mood_demos/desert_drive_demo.mp4",
    "mood_demos/euphoric_drift_demo.mp4",
    "mood_demos/neon_calm_demo.mp4",
    "mood_demos/peak_transmission_demo.mp4",
    "mood_demos/velvet_dark_demo.mp4",
    "mood_demos/ghost_room_demo.mp4",
    "mood_demos/sunrise_departure_demo.mp4",
    "mood_demos/afterglow_ritual_demo.mp4",
]


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path_parts = self.path.strip('/').split('/')
        job_id = path_parts[-1].split('?')[0] if path_parts else None

        if not job_id:
            self._json(400, {"error": "Missing job_id"})
            return

        # Proxy to GPU server if available
        gen_server = os.environ.get('GENERATION_SERVER', '')
        gpu_error = None
        if gen_server:
            import urllib.request
            import urllib.error
            try:
                req = urllib.request.Request(
                    f"{gen_server}/api/v2/status/{job_id}",
                    method="GET",
                    headers={"Bypass-Tunnel-Reminder": "true"},
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
                print(f"[V2 Status] GPU server error: {e}")

        # GPU server unreachable — return error
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
