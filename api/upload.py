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
        if gen_server:
            import urllib.request
            try:
                req = urllib.request.Request(
                    f"{gen_server}/api/upload",
                    data=body,
                    headers={
                        "Content-Type": content_type,
                        "Content-Length": str(len(body)),
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    result = json.loads(resp.read())
                    self._json(200, result)
                    return
            except Exception as e:
                print(f"[Upload] GPU proxy error: {e}")
                # Fall through to local handling

        # Local/demo mode: parse multipart and save to /tmp
        boundary = None
        for part in content_type.split(';'):
            part = part.strip()
            if part.startswith('boundary='):
                boundary = part[9:].strip('"')
                break

        if not boundary:
            self._json(400, {"error": "No boundary found"})
            return

        boundary_bytes = boundary.encode()
        parts = body.split(b'--' + boundary_bytes)
        filename = "track.mp3"
        file_data = None

        for part in parts:
            if b'Content-Disposition' in part:
                header_end = part.find(b'\r\n\r\n')
                if header_end == -1:
                    continue
                headers = part[:header_end].decode('utf-8', errors='replace')
                data = part[header_end + 4:]
                if data.endswith(b'\r\n'):
                    data = data[:-2]

                if 'filename=' in headers:
                    fn_start = headers.find('filename="')
                    if fn_start != -1:
                        fn_start += 10
                        fn_end = headers.find('"', fn_start)
                        filename = headers[fn_start:fn_end]
                    file_data = data

        if file_data is None:
            self._json(400, {"error": "No file found in upload"})
            return

        job_id = uuid.uuid4().hex[:8]

        # Save to /tmp
        tmp_path = os.path.join(tempfile.gettempdir(), f"{job_id}_{filename}")
        with open(tmp_path, 'wb') as f:
            f.write(file_data)

        self._json(200, {
            "success": True,
            "job_id": job_id,
            "filename": filename,
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
