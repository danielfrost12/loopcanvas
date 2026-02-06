"""
GET /api/configs — Serve merged JSON of all config files
Reads from repo root: retention_config.json, onboarding_config.json,
growth_config.json, landing_config.json
$0 cost — local file reads only
"""
import json
import os
from http.server import BaseHTTPRequestHandler

# Config files live at the repo root (one directory above /api)
CONFIG_DIR = os.path.join(os.path.dirname(__file__), '..')

CONFIG_FILES = {
    'retention':  'retention_config.json',
    'onboarding': 'onboarding_config.json',
    'growth':     'growth_config.json',
    'landing':    'landing_config.json',
}

# Empty defaults if a config file is missing
DEFAULTS = {
    'retention':  {},
    'onboarding': {},
    'growth':     {},
    'landing':    {},
}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        merged = {}
        for key, filename in CONFIG_FILES.items():
            filepath = os.path.join(CONFIG_DIR, filename)
            try:
                with open(filepath, 'r') as f:
                    merged[key] = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                merged[key] = DEFAULTS.get(key, {})

        self._json(200, merged)

    def do_POST(self):
        # Also support POST for convenience
        self.do_GET()

    def _json(self, code, data):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
