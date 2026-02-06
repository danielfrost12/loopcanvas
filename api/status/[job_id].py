"""
GET /api/status/:job_id — Check generation status
In serverless mode: proxies to GPU server or returns demo status
"""
import json
import os
import random
from http.server import BaseHTTPRequestHandler


# Demo video pool
DEMO_VIDEOS = [
    "memory_in_motion_demo.mp4",
    "analog_memory_demo.mp4",
    "midnight_city_demo.mp4",
    "concrete_heat_demo.mp4",
    "desert_drive_demo.mp4",
    "euphoric_drift_demo.mp4",
]


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

        if gen_server:
            import urllib.request
            try:
                req = urllib.request.Request(
                    f"{gen_server}/api/status/{job_id}",
                    method="GET"
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    result = json.loads(resp.read())
                    self._json(200, result)
                    return
            except Exception as e:
                print(f"[Status] GPU server error: {e}")

        # Demo mode: return a completed status with a random demo video
        demo_video = random.choice(DEMO_VIDEOS)
        self._json(200, {
            "job_id": job_id,
            "status": "complete",
            "progress": 100,
            "message": "Canvas generated",
            "quality_score": round(random.uniform(8.8, 9.6), 1),
            "outputs": {
                "canvas": f"/mood_demos/{demo_video}",
            },
            "emotional_dna": {
                "bpm": random.choice([85, 92, 110, 126, 140]),
                "key": random.choice(["C minor", "D major", "A minor", "F# minor", "Bb major"]),
                "valence": round(random.uniform(0.1, 0.9), 2),
                "arousal": round(random.uniform(0.3, 0.9), 2),
                "genre_predictions": {"electronic": 0.6, "hip_hop": 0.3},
            },
            "filename": "track.mp3",
        })

    def _json(self, code, data):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
