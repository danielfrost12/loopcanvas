"""
POST /api/v2/analyze — Extract emotional DNA from uploaded track
In serverless mode: proxies to GPU server or returns demo analysis
"""
import json
import os
import random
from http.server import BaseHTTPRequestHandler


DIRECTORS = [
    {
        "id": "lubezki",
        "director_style": "lubezki",
        "director_name": "Emmanuel Lubezki",
        "philosophy": "Footage that does not know it is being watched",
        "color_palette": ["#2d3436", "#636e72", "#dfe6e9", "#b2bec3"],
        "motion_style": "Handheld drift with natural light",
        "texture": "Soft grain, golden hour warmth",
        "confidence": 0.92,
    },
    {
        "id": "hype_williams",
        "director_style": "hype_williams",
        "director_name": "Hype Williams",
        "philosophy": "Make the mundane feel mythological",
        "color_palette": ["#6c5ce7", "#a29bfe", "#fd79a8", "#ffeaa7"],
        "motion_style": "Fisheye distortion, slow-motion grandeur",
        "texture": "High contrast, saturated excess",
        "confidence": 0.88,
    },
    {
        "id": "spike_jonze",
        "director_style": "spike_jonze",
        "director_name": "Spike Jonze",
        "philosophy": "Find beauty in vulnerability",
        "color_palette": ["#fab1a0", "#ffeaa7", "#74b9ff", "#a29bfe"],
        "motion_style": "Playful tracking shots, unexpected angles",
        "texture": "Warm film stock, intimate framing",
        "confidence": 0.85,
    },
    {
        "id": "dave_meyers",
        "director_style": "dave_meyers",
        "director_name": "Dave Meyers",
        "philosophy": "Transform reality into spectacle",
        "color_palette": ["#e17055", "#fdcb6e", "#00cec9", "#6c5ce7"],
        "motion_style": "Dynamic angles, bold compositions",
        "texture": "Vivid color, sharp detail",
        "confidence": 0.82,
    },
    {
        "id": "khalil_joseph",
        "director_style": "khalil_joseph",
        "director_name": "Khalil Joseph",
        "philosophy": "Memory as a living, breathing thing",
        "color_palette": ["#2d3436", "#636e72", "#b2bec3", "#dfe6e9"],
        "motion_style": "Fragmented narrative, poetic montage",
        "texture": "Archival warmth, dream-like grain",
        "confidence": 0.79,
    },
]


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        data = json.loads(body)

        job_id = data.get('job_id')
        if not job_id:
            self._json(400, {"error": "Missing job_id"})
            return

        # Check GPU server
        gen_server = os.environ.get('GENERATION_SERVER', '')
        gpu_error = None
        if gen_server:
            import urllib.request
            import urllib.error
            try:
                api_key = os.environ.get('GPU_API_KEY', '')
                req = urllib.request.Request(
                    f"{gen_server}/api/v2/analyze",
                    data=json.dumps(data).encode(),
                    headers={
                        "Content-Type": "application/json",
                        "Bypass-Tunnel-Reminder": "true",
                        **({"Authorization": f"Bearer {api_key}"} if api_key else {}),
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    result = json.loads(resp.read())
                    result["mode"] = "gpu"
                    self._json(200, result)
                    return
            except urllib.error.HTTPError as e:
                # GPU server responded with an error — forward it, don't fall back
                try:
                    error_body = json.loads(e.read())
                    error_body["mode"] = "gpu"
                    self._json(e.code, error_body)
                except Exception:
                    self._json(e.code, {"error": str(e), "mode": "gpu"})
                return
            except Exception as e:
                gpu_error = str(e)
                print(f"[Analyze] GPU server error: {e}")

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

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
