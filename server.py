#!/usr/bin/env python3
"""
LoopCanvas Backend Server v2.0

Canvas Agent Army architecture integrated.

v1.0 endpoints (preserved):
  POST /api/upload       — Upload audio file
  POST /api/generate     — Start generation (legacy: direct pipeline)
  POST /api/regenerate   — Regenerate with new params
  GET  /api/status/:id   — Job status
  POST /api/cms/save     — Save CMS data

v2.0 endpoints (new):
  POST /api/v2/analyze          — Extract emotional DNA from uploaded track
  GET  /api/v2/directions/:id   — Get 3-5 visual directions for a job
  POST /api/v2/select           — Select a direction and start generation
  POST /api/v2/iterate          — Real-time adjustment ("make it warmer")
  POST /api/v2/edit             — Intent-based edit ("cut the intro")
  POST /api/v2/export           — Multi-platform export
  GET  /api/v2/platforms        — List supported export platforms
  GET  /api/v2/cost-report      — Cost enforcement status
  POST /api/v2/undo             — Undo last iteration or edit

Queue endpoints (GPU worker communication):
  POST /api/v2/queue/claim      — Worker claims next job
  POST /api/v2/queue/progress   — Worker reports progress
  POST /api/v2/queue/complete   — Worker reports completion
  POST /api/v2/queue/fail       — Worker reports failure
  GET  /api/v2/queue/stats      — Queue statistics
  POST /api/v2/queue/submit     — Submit a job to the queue
"""

import os
import sys
import json
import uuid
import subprocess
import shutil
import re
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import parse_qs, urlparse
import threading
import time

# Add parent dir and canvas-engine to path
APP_DIR = Path(__file__).parent
ENGINE_DIR = APP_DIR / "canvas-engine"
ROOT_DIR = APP_DIR.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ENGINE_DIR))

# Configuration
UPLOAD_DIR = APP_DIR / "uploads"
OUTPUT_DIR = APP_DIR / "outputs"
PIPELINE_SCRIPT = ROOT_DIR / "loopcanvas_grammy.py"
PORT = 8888

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Track active jobs (v1 legacy)
active_jobs = {}

# Canvas v2.0 orchestrator (lazy-loaded)
_orchestrator = None


def get_orchestrator():
    """Lazy-load the orchestrator to avoid import overhead on startup"""
    global _orchestrator
    if _orchestrator is None:
        try:
            from orchestrator import get_orchestrator as _get_orch
            _orchestrator = _get_orch()
            print("[Canvas v2.0] Orchestrator loaded")
        except Exception as e:
            print(f"[Canvas v2.0] Orchestrator load failed: {e}")
            print("[Canvas v2.0] Falling back to v1 pipeline")
    return _orchestrator


def parse_multipart(content_type: str, body: bytes):
    """Parse multipart form data without cgi module (Python 3.13+ compatible)."""
    match = re.search(r'boundary=([^\s;]+)', content_type)
    if not match:
        raise ValueError("No boundary in Content-Type")

    boundary = match.group(1).encode()
    if boundary.startswith(b'"') and boundary.endswith(b'"'):
        boundary = boundary[1:-1]

    parts = body.split(b'--' + boundary)

    result = {}
    for part in parts:
        if not part or part.strip() == b'' or part.strip() == b'--':
            continue

        try:
            header_end = part.index(b'\r\n\r\n')
            headers = part[:header_end].decode('utf-8', errors='replace')
            content = part[header_end + 4:]

            if content.endswith(b'\r\n'):
                content = content[:-2]

            name_match = re.search(r'name="([^"]+)"', headers)
            filename_match = re.search(r'filename="([^"]+)"', headers)

            if name_match:
                name = name_match.group(1)
                result[name] = {
                    'content': content,
                    'filename': filename_match.group(1) if filename_match else None
                }
        except ValueError:
            continue

    return result


class LoopCanvasHandler(SimpleHTTPRequestHandler):
    """HTTP handler with v1 + v2 API endpoints."""

    def do_POST(self):
        """Route POST requests."""
        # === v2.0 endpoints ===
        if self.path == "/api/v2/analyze":
            self.handle_v2_analyze()
        elif self.path == "/api/v2/select":
            self.handle_v2_select()
        elif self.path == "/api/v2/iterate":
            self.handle_v2_iterate()
        elif self.path == "/api/v2/edit":
            self.handle_v2_edit()
        elif self.path == "/api/v2/export":
            self.handle_v2_export()
        elif self.path == "/api/v2/undo":
            self.handle_v2_undo()
        # === Queue endpoints (GPU worker communication) ===
        elif self.path == "/api/v2/queue/claim":
            self.handle_queue_claim()
        elif self.path == "/api/v2/queue/progress":
            self.handle_queue_progress()
        elif self.path == "/api/v2/queue/complete":
            self.handle_queue_complete()
        elif self.path == "/api/v2/queue/fail":
            self.handle_queue_fail()
        elif self.path == "/api/v2/queue/submit":
            self.handle_queue_submit()
        # === v1 endpoints (preserved) ===
        elif self.path == "/api/upload":
            self.handle_upload()
        elif self.path == "/api/generate":
            self.handle_generate()
        elif self.path == "/api/regenerate":
            self.handle_regenerate()
        elif self.path.startswith("/api/status/"):
            self.handle_status()
        elif self.path == "/api/cms/save":
            self.handle_cms_save()
        else:
            self.send_error(404)

    def do_GET(self):
        """Route GET requests."""
        parsed = urlparse(self.path)

        # === Health check (GPU liveness) ===
        if parsed.path == "/api/health":
            self.send_json_response({
                "gpu": "live",
                "server": "loopcanvas-gpu",
                "port": PORT,
                "timestamp": datetime.now().isoformat(),
            })
            return

        # === v2.0 endpoints ===
        if parsed.path.startswith("/api/v2/directions/"):
            job_id = parsed.path.split("/")[-1]
            self.handle_v2_directions(job_id)
        elif parsed.path == "/api/v2/platforms":
            self.handle_v2_platforms()
        elif parsed.path == "/api/v2/cost-report":
            self.handle_v2_cost_report()
        elif parsed.path == "/api/v2/queue/stats":
            self.handle_queue_stats()
        elif parsed.path == "/api/v2/seed/status":
            self.handle_seed_status()
        elif parsed.path.startswith("/api/v2/status/"):
            job_id = parsed.path.split("/")[-1]
            self.handle_v2_status(job_id)
        # === v1 endpoints ===
        elif parsed.path.startswith("/api/status/"):
            job_id = parsed.path.split("/")[-1]
            self.handle_status_get(job_id)
        elif parsed.path.startswith("/outputs/"):
            self.path = parsed.path
            super().do_GET()
        else:
            super().do_GET()

    # ══════════════════════════════════════════════════════════════
    # v2.0 API HANDLERS
    # ══════════════════════════════════════════════════════════════

    def handle_v2_analyze(self):
        """
        POST /api/v2/analyze
        Body: {"job_id": "abc123"}

        Triggers Audio Intelligence Engine to extract emotional DNA.
        Returns emotional DNA + auto-generated visual directions.
        """
        try:
            data = self._read_json_body()
            job_id = data.get('job_id')

            if not job_id or job_id not in active_jobs:
                self.send_json_error("Invalid job ID. Upload a file first.", 400)
                return

            legacy_job = active_jobs[job_id]
            audio_path = legacy_job.get("upload_path")

            if not audio_path or not Path(audio_path).exists():
                self.send_json_error("Audio file not found", 400)
                return

            orch = get_orchestrator()
            if not orch:
                self.send_json_error("Canvas v2.0 engine not available", 503)
                return

            # Run analysis (synchronous — fast, ~5-10 sec)
            job = orch.analyze_audio(audio_path, job_id)

            if job.status == "failed":
                self.send_json_error(job.message, 500)
                return

            # Auto-generate directions
            directions = orch.generate_directions(job_id, count=5)

            # Update legacy job with v2 data
            legacy_job["emotional_dna"] = job.emotional_dna
            legacy_job["directions"] = [
                {
                    "id": d.id,
                    "director_style": d.director_style,
                    "director_name": d.director_name,
                    "philosophy": d.philosophy,
                    "color_palette": d.color_palette,
                    "motion_style": d.motion_style,
                    "texture": d.texture,
                    "confidence": d.confidence,
                }
                for d in directions
            ]
            legacy_job["status"] = "directions_ready"
            legacy_job["progress"] = 30

            self.send_json_response({
                "success": True,
                "job_id": job_id,
                "emotional_dna": job.emotional_dna,
                "directions": legacy_job["directions"],
                "duration_seconds": job.duration_seconds,
            })

        except Exception as e:
            self.send_json_error(str(e), 500)

    def handle_v2_directions(self, job_id):
        """
        GET /api/v2/directions/:job_id

        Returns visual directions for a job (must be analyzed first).
        """
        orch = get_orchestrator()
        if not orch:
            self.send_json_error("Canvas v2.0 engine not available", 503)
            return

        job_status = orch.get_job_status(job_id)
        if not job_status:
            # Try legacy jobs
            if job_id in active_jobs and "directions" in active_jobs[job_id]:
                self.send_json_response({
                    "directions": active_jobs[job_id]["directions"]
                })
                return
            self.send_json_error("Job not found or not analyzed yet", 404)
            return

        self.send_json_response({
            "directions": job_status.get("directions", []),
            "emotional_dna": job_status.get("emotional_dna"),
        })

    def handle_v2_select(self):
        """
        POST /api/v2/select
        Body: {"job_id": "abc123", "direction_id": "dir_0_spike_jonze"}

        Artist selects a visual direction. Starts generation.
        """
        try:
            data = self._read_json_body()
            job_id = data.get('job_id')
            direction_id = data.get('direction_id')

            if not job_id or not direction_id:
                self.send_json_error("job_id and direction_id required", 400)
                return

            orch = get_orchestrator()
            if not orch:
                self.send_json_error("Canvas v2.0 engine not available", 503)
                return

            output_dir = str(OUTPUT_DIR / job_id)

            # Run generation in background thread
            def run():
                result = orch.select_direction_and_generate(
                    job_id, direction_id, output_dir
                )
                # Sync back to legacy job dict
                if job_id in active_jobs and result:
                    active_jobs[job_id]["status"] = result.status
                    active_jobs[job_id]["progress"] = result.progress
                    active_jobs[job_id]["message"] = result.message
                    active_jobs[job_id]["output_dir"] = output_dir
                    if result.outputs:
                        active_jobs[job_id]["outputs"] = result.outputs
                    if result.quality_score:
                        active_jobs[job_id]["quality_score"] = result.quality_score
                    if result.loop_analysis:
                        active_jobs[job_id]["loop_analysis"] = result.loop_analysis

            thread = threading.Thread(target=run, daemon=True)
            thread.start()

            # Update legacy job
            if job_id in active_jobs:
                active_jobs[job_id]["status"] = "generating"
                active_jobs[job_id]["progress"] = 35
                active_jobs[job_id]["message"] = "Generating canvas..."
                active_jobs[job_id]["selected_direction"] = direction_id

            self.send_json_response({
                "success": True,
                "job_id": job_id,
                "direction_id": direction_id,
                "status": "generating",
            })

        except Exception as e:
            self.send_json_error(str(e), 500)

    def handle_v2_iterate(self):
        """
        POST /api/v2/iterate
        Body: {"job_id": "abc123", "adjustment": "make it warmer", "params": {}}

        Real-time canvas adjustment. Target: < 3 seconds.
        """
        try:
            data = self._read_json_body()
            job_id = data.get('job_id')
            adjustment = data.get('adjustment', '')
            params = data.get('params', {})

            if not job_id:
                self.send_json_error("job_id required", 400)
                return

            orch = get_orchestrator()
            if not orch:
                self.send_json_error("Canvas v2.0 engine not available", 503)
                return

            # Run iteration (synchronous — should be < 3 sec)
            start = time.time()
            result = orch.iterate(job_id, adjustment, params)
            elapsed = time.time() - start

            if result and result.outputs:
                # Sync to legacy
                if job_id in active_jobs:
                    active_jobs[job_id]["outputs"] = result.outputs

                self.send_json_response({
                    "success": True,
                    "job_id": job_id,
                    "adjustment": adjustment,
                    "elapsed_seconds": round(elapsed, 2),
                    "outputs": result.outputs,
                    "message": result.message,
                })
            else:
                msg = result.message if result else "Iteration failed"
                self.send_json_error(msg, 400)

        except Exception as e:
            self.send_json_error(str(e), 500)

    def handle_v2_edit(self):
        """
        POST /api/v2/edit
        Body: {"job_id": "abc123", "instruction": "cut the intro"}

        Intent-based video editing.
        """
        try:
            data = self._read_json_body()
            job_id = data.get('job_id')
            instruction = data.get('instruction', '')

            if not job_id or not instruction:
                self.send_json_error("job_id and instruction required", 400)
                return

            # Get video path and audio DNA
            orch = get_orchestrator()
            job_status = orch.get_job_status(job_id) if orch else None

            # Find the video to edit
            video_path = None
            audio_dna = None

            if job_status:
                outputs = job_status.get('outputs', {})
                audio_dna = job_status.get('emotional_dna')
                if outputs.get('full_video'):
                    video_path = str(OUTPUT_DIR / job_id / Path(outputs['full_video']).name)
                elif outputs.get('canvas'):
                    video_path = str(OUTPUT_DIR / job_id / Path(outputs['canvas']).name)

            if not video_path or not Path(video_path).exists():
                self.send_json_error("No video found to edit", 400)
                return

            # Run intent editor
            from editor.intent_editor import IntentEditor
            editor = IntentEditor()

            operations = editor.parse_intent(instruction, audio_dna)
            if not operations:
                self.send_json_error(f"Could not understand: '{instruction}'", 400)
                return

            output_path = str(Path(video_path).with_suffix('')) + "_edited.mp4"
            result = editor.apply_edits(video_path, operations, output_path)

            self.send_json_response({
                "success": result.success,
                "job_id": job_id,
                "instruction": instruction,
                "operations": [
                    {"type": op.op_type, "description": op.description}
                    for op in operations
                ],
                "operations_applied": result.operations_applied,
                "duration_change": result.duration_change,
                "output_path": f"/outputs/{job_id}/{Path(output_path).name}",
                "message": result.message,
            })

        except Exception as e:
            self.send_json_error(str(e), 500)

    def handle_v2_export(self):
        """
        POST /api/v2/export
        Body: {"job_id": "abc123", "platforms": ["spotify_canvas", "instagram_reels"]}

        Multi-platform export.
        """
        try:
            data = self._read_json_body()
            job_id = data.get('job_id')
            platforms = data.get('platforms')  # None = all
            metadata = data.get('metadata', {})

            if not job_id:
                self.send_json_error("job_id required", 400)
                return

            # Find source video
            source_path = None
            job_dir = OUTPUT_DIR / job_id

            for candidate in ["spotify_canvas_web.mp4", "spotify_canvas_7s_9x16.mp4"]:
                p = job_dir / candidate
                if p.exists():
                    source_path = str(p)
                    break

            if not source_path:
                self.send_json_error("No canvas found to export", 400)
                return

            # Run export
            from export.multi_platform import MultiPlatformExporter
            exporter = MultiPlatformExporter()

            export_dir = str(job_dir / "exports")
            results = exporter.export_all(source_path, export_dir, platforms, metadata)

            response = {
                "success": True,
                "job_id": job_id,
                "exports": {},
            }

            for key, result in results.items():
                response["exports"][key] = {
                    "platform": result.platform,
                    "success": result.success,
                    "output_path": f"/outputs/{job_id}/exports/{Path(result.output_path).name}" if result.success else None,
                    "file_size_mb": result.file_size_mb,
                    "resolution": result.resolution,
                    "warnings": result.warnings,
                    "message": result.message,
                }

            self.send_json_response(response)

        except Exception as e:
            self.send_json_error(str(e), 500)

    def handle_v2_platforms(self):
        """GET /api/v2/platforms — List supported export platforms"""
        try:
            from export.multi_platform import MultiPlatformExporter
            exporter = MultiPlatformExporter()
            self.send_json_response({
                "platforms": exporter.list_platforms()
            })
        except Exception as e:
            self.send_json_error(str(e), 500)

    def handle_v2_cost_report(self):
        """GET /api/v2/cost-report — Cost enforcement status"""
        orch = get_orchestrator()
        if orch:
            self.send_json_response({
                "report": orch.get_cost_report(),
                "enforcer_status": orch.enforcer.get_status(),
            })
        else:
            self.send_json_response({
                "report": "Orchestrator not loaded",
                "enforcer_status": {},
            })

    def handle_v2_status(self, job_id):
        """GET /api/v2/status/:id — Full v2 job status"""
        orch = get_orchestrator()
        if orch:
            status = orch.get_job_status(job_id)
            if status:
                self.send_json_response(status)
                return

        # Fall back to legacy
        if job_id in active_jobs:
            self.send_json_response(active_jobs[job_id])
        else:
            self.send_json_error("Job not found", 404)

    def handle_v2_undo(self):
        """POST /api/v2/undo — Undo last iteration"""
        try:
            data = self._read_json_body()
            job_id = data.get('job_id')

            if not job_id:
                self.send_json_error("job_id required", 400)
                return

            orch = get_orchestrator()
            if not orch:
                self.send_json_error("Canvas v2.0 engine not available", 503)
                return

            # Try to undo via iteration engine
            try:
                from iteration.realtime_iterator import RealtimeIterator
                iterator = RealtimeIterator()
                prev_path = iterator.undo(job_id)
                if prev_path:
                    self.send_json_response({
                        "success": True,
                        "job_id": job_id,
                        "message": "Reverted to previous version",
                        "canvas_path": prev_path,
                    })
                    return
            except Exception:
                pass

            self.send_json_error("Nothing to undo", 400)

        except Exception as e:
            self.send_json_error(str(e), 500)

    # ══════════════════════════════════════════════════════════════
    # QUEUE API HANDLERS (GPU worker communication)
    # ══════════════════════════════════════════════════════════════

    def _get_queue_manager(self):
        """Get the queue manager from the orchestrator"""
        orch = get_orchestrator()
        if orch and orch.queue_manager:
            return orch.queue_manager
        # Fallback: create one directly
        try:
            from dispatch.job_queue import QueueManager
            return QueueManager()
        except Exception:
            return None

    def handle_queue_claim(self):
        """
        POST /api/v2/queue/claim
        Body: {"worker_id": "colab-001", "worker_type": "colab", "gpu": "T4"}

        GPU worker claims next available job from the queue.
        Returns the job data or empty if no work available.
        """
        try:
            data = self._read_json_body()
            worker_id = data.get('worker_id', 'unknown')
            worker_type = data.get('worker_type', 'unknown')

            qm = self._get_queue_manager()
            if not qm:
                self.send_json_error("Queue not available", 503)
                return

            job = qm.queue.claim(worker_id, worker_type)

            if job:
                from dataclasses import asdict
                job_data = asdict(job)

                # If audio is a local path, try to provide a download URL
                audio_path = job_data.get('audio_path', '')
                if audio_path and os.path.exists(audio_path):
                    # Make it accessible via the static file server
                    rel = os.path.relpath(audio_path, str(APP_DIR))
                    job_data['audio_url'] = f"/{rel}"

                print(f"[Queue] Job {job.job_id} claimed by {worker_id} ({worker_type})")
                self.send_json_response({"job": job_data})
            else:
                self.send_json_response({"job": None, "message": "No jobs available"})

        except Exception as e:
            self.send_json_error(str(e), 500)

    def handle_queue_progress(self):
        """
        POST /api/v2/queue/progress
        Body: {"job_id": "abc123", "progress": 50, "message": "Generating visuals..."}

        GPU worker reports progress on a claimed job.
        """
        try:
            data = self._read_json_body()
            job_id = data.get('job_id')
            progress = data.get('progress', 0)
            message = data.get('message', '')

            if not job_id:
                self.send_json_error("job_id required", 400)
                return

            qm = self._get_queue_manager()
            if not qm:
                self.send_json_error("Queue not available", 503)
                return

            qm.queue.update_progress(job_id, progress, message, "generating")

            # Also sync to active_jobs so v1 status endpoint sees progress
            if job_id in active_jobs:
                active_jobs[job_id]["progress"] = progress
                active_jobs[job_id]["message"] = message
                active_jobs[job_id]["status"] = "generating"

            self.send_json_response({"success": True})

        except Exception as e:
            self.send_json_error(str(e), 500)

    def handle_queue_complete(self):
        """
        POST /api/v2/queue/complete
        Body: {"job_id": "abc123", "output_dir": "/path/to/output",
               "quality_score": 9.5, "loop_score": 0.95}

        GPU worker reports job completion with results.
        """
        try:
            data = self._read_json_body()
            job_id = data.get('job_id')
            output_dir = data.get('output_dir')
            quality_score = data.get('quality_score')
            loop_score = data.get('loop_score')

            if not job_id:
                self.send_json_error("job_id required", 400)
                return

            qm = self._get_queue_manager()
            if not qm:
                self.send_json_error("Queue not available", 503)
                return

            qm.queue.complete(
                job_id,
                output_dir=output_dir,
                quality_score=quality_score,
                loop_score=loop_score,
            )

            # Sync to active_jobs
            if job_id in active_jobs:
                active_jobs[job_id]["status"] = "complete"
                active_jobs[job_id]["progress"] = 100
                active_jobs[job_id]["message"] = "Generation complete!"
                if quality_score:
                    active_jobs[job_id]["quality_score"] = quality_score
                if loop_score:
                    active_jobs[job_id]["loop_score"] = loop_score
                if output_dir:
                    active_jobs[job_id]["output_dir"] = output_dir
                    # Build output URLs
                    out = Path(output_dir)
                    web = out / "spotify_canvas_web.mp4"
                    canvas = out / "spotify_canvas_7s_9x16.mp4"
                    if web.exists():
                        active_jobs[job_id]["outputs"] = {
                            "canvas": f"/outputs/{job_id}/spotify_canvas_web.mp4"
                        }
                    elif canvas.exists():
                        active_jobs[job_id]["outputs"] = {
                            "canvas": f"/outputs/{job_id}/spotify_canvas_7s_9x16.mp4"
                        }

            # Log result for optimization loop
            self._log_optimization_result(job_id, quality_score, loop_score)

            print(f"[Queue] Job {job_id} completed (quality={quality_score}, loop={loop_score})")
            self.send_json_response({"success": True})

        except Exception as e:
            self.send_json_error(str(e), 500)

    def handle_queue_fail(self):
        """
        POST /api/v2/queue/fail
        Body: {"job_id": "abc123", "error": "Out of memory"}

        GPU worker reports job failure. Job will be retried if attempts remain.
        """
        try:
            data = self._read_json_body()
            job_id = data.get('job_id')
            error = data.get('error', 'Unknown error')

            if not job_id:
                self.send_json_error("job_id required", 400)
                return

            qm = self._get_queue_manager()
            if not qm:
                self.send_json_error("Queue not available", 503)
                return

            qm.queue.fail(job_id, error)

            # Check if it was re-queued or marked dead
            job_data = qm.queue.get_job(job_id)
            status = job_data.get('status', 'failed') if job_data else 'failed'

            if job_id in active_jobs:
                if status == "dead":
                    active_jobs[job_id]["status"] = "error"
                    active_jobs[job_id]["message"] = f"Failed after max retries: {error}"
                else:
                    active_jobs[job_id]["status"] = "queued"
                    active_jobs[job_id]["message"] = f"Retrying: {error}"

            print(f"[Queue] Job {job_id} failed: {error} (status={status})")
            self.send_json_response({"success": True, "status": status})

        except Exception as e:
            self.send_json_error(str(e), 500)

    def handle_queue_submit(self):
        """
        POST /api/v2/queue/submit
        Body: {"job_id": "abc123", "priority": 5}

        Submit a job to the GPU worker queue (alternative to direct generation).
        The job must already be analyzed with directions selected.
        """
        try:
            data = self._read_json_body()
            job_id = data.get('job_id')
            priority = data.get('priority', 10)

            if not job_id or job_id not in active_jobs:
                self.send_json_error("Invalid job_id", 400)
                return

            legacy_job = active_jobs[job_id]
            audio_path = legacy_job.get("upload_path")

            if not audio_path:
                self.send_json_error("No audio file for this job", 400)
                return

            qm = self._get_queue_manager()
            if not qm:
                self.send_json_error("Queue not available", 503)
                return

            # Submit to queue
            queue_job = qm.submit(
                job_id=job_id,
                audio_path=audio_path,
                direction=legacy_job.get("selected_direction_data"),
                emotional_dna=legacy_job.get("emotional_dna"),
                params=legacy_job.get("params", {}),
                priority=priority,
            )

            legacy_job["status"] = "queued"
            legacy_job["progress"] = 5
            legacy_job["message"] = "Queued for GPU generation"

            print(f"[Queue] Job {job_id} submitted (priority={priority})")
            self.send_json_response({
                "success": True,
                "job_id": job_id,
                "status": "queued",
                "queue_stats": qm.get_stats(),
            })

        except Exception as e:
            self.send_json_error(str(e), 500)

    def handle_seed_status(self):
        """GET /api/v2/seed/status — Seed runner and optimization status"""
        try:
            from agents.optimization_loop import OptimizationLoop
            loop = OptimizationLoop()
            state = loop._load_state()

            # Read results count
            results_file = ENGINE_DIR / "optimization_data" / "canvas_results.jsonl"
            result_count = 0
            if results_file.exists():
                with open(results_file) as f:
                    result_count = sum(1 for _ in f)

            # Read evolved config
            evolved_config = {}
            config_file = ENGINE_DIR / "optimization_data" / "evolved_config.json"
            if config_file.exists():
                with open(config_file) as f:
                    evolved_config = json.load(f)

            from dataclasses import asdict
            self.send_json_response({
                "seed_runner": os.environ.get("LOOPCANVAS_SEED", "1") == "1",
                "total_results_logged": result_count,
                "optimization_state": asdict(state),
                "evolved_styles": list(evolved_config.get("evolved_params", {}).keys()),
                "negative_prompts": evolved_config.get("evolved_negative_prompts", []),
            })
        except Exception as e:
            self.send_json_response({
                "seed_runner": False,
                "error": str(e),
            })

    def handle_queue_stats(self):
        """GET /api/v2/queue/stats — Queue statistics and worker info"""
        qm = self._get_queue_manager()
        if not qm:
            self.send_json_response({"error": "Queue not available", "stats": {}})
            return

        stats = qm.get_stats()
        self.send_json_response({"stats": stats})

    def _log_optimization_result(self, job_id: str, quality_score: float, loop_score: float):
        """Log completed job result for the optimization loop to analyze"""
        try:
            from agents.optimization_loop import OptimizationLoop, CanvasResult

            legacy_job = active_jobs.get(job_id, {})
            direction = {}
            for d in legacy_job.get("directions", []):
                if d.get("id") == legacy_job.get("selected_direction"):
                    direction = d
                    break

            result = CanvasResult(
                job_id=job_id,
                timestamp=datetime.now().isoformat(),
                director_style=direction.get("director_style", "unknown"),
                prompt=direction.get("preview_prompt", ""),
                params=direction.get("params", {}),
                quality_score=quality_score or 0.0,
                quality_passed=(quality_score or 0) >= 9.3,
                quality_breakdown={},
                loop_score=loop_score or 0.0,
                selected_by_artist=True,
                iterated=len(legacy_job.get("iterations", [])) > 0,
                exported=False,
                export_platforms=[],
            )

            loop = OptimizationLoop()
            loop.log_result(result)
        except Exception:
            pass  # Non-critical

    # ══════════════════════════════════════════════════════════════
    # v1 API HANDLERS (preserved, unchanged)
    # ══════════════════════════════════════════════════════════════

    def handle_cms_save(self):
        """Save CMS data."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)

            cms_path = APP_DIR / "cms" / "moods.json"
            with open(cms_path, 'w') as f:
                json.dump(data, f, indent=2)

            self.send_json_response({"success": True})
        except Exception as e:
            self.send_json_error(str(e), 500)

    def handle_regenerate(self):
        """Regenerate canvas/video with new parameters."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)

            job_id = data.get('job_id')
            if not job_id or job_id not in active_jobs:
                self.send_json_error("Invalid job ID", 400)
                return

            job = active_jobs[job_id]
            if job["status"] != "complete":
                self.send_json_error("Job not complete, cannot regenerate", 400)
                return

            params = data.get('params', {})
            output_type = data.get('output_type', 'canvas')

            regen_id = f"{job_id}_r{int(time.time())}"
            job["regen_status"] = "processing"
            job["regen_progress"] = 10
            job["regen_message"] = "Applying new parameters..."

            thread = threading.Thread(
                target=self.run_regeneration,
                args=(job_id, regen_id, params, output_type),
                daemon=True
            )
            thread.start()

            self.send_json_response({
                "success": True,
                "job_id": job_id,
                "regen_id": regen_id,
                "status": "processing",
            })

        except Exception as e:
            self.send_json_error(str(e), 500)

    def run_regeneration(self, job_id, regen_id, params, output_type):
        """Run regeneration with new parameters."""
        job = active_jobs[job_id]
        output_dir = Path(job["output_dir"])

        try:
            job["regen_progress"] = 30
            job["regen_message"] = "Generating with new parameters..."

            cmd = [
                sys.executable,
                str(PIPELINE_SCRIPT),
                "--audio", job["upload_path"],
                "--out", str(output_dir / "regen"),
            ]

            env = os.environ.copy()
            if params.get('style'):
                env["LOOPCANVAS_STYLE"] = params['style']
            env["LOOPCANVAS_GRAIN"] = str(params.get('grain', 0.4))
            env["LOOPCANVAS_VIGNETTE"] = str(params.get('vignette', 0.5))
            env["LOOPCANVAS_GLOW"] = str(params.get('glow', 0.6))
            env["LOOPCANVAS_MOTION_SPEED"] = str(params.get('motion_speed', 0.3))
            env["LOOPCANVAS_SATURATION"] = str(params.get('saturation', 1.15))
            env["LOOPCANVAS_CONTRAST"] = str(params.get('contrast', 1.1))
            env["LOOPCANVAS_TEMPERATURE"] = str(params.get('temperature', 5500))

            regen_dir = output_dir / "regen"
            regen_dir.mkdir(exist_ok=True)

            job["regen_progress"] = 50
            job["regen_message"] = "Rendering..."

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=str(PIPELINE_SCRIPT.parent),
                env=env,
            )

            for line in process.stdout:
                line = line.strip()
                print(f"[Regen {regen_id}] {line}")
                if "Rendering" in line or "[7/7]" in line:
                    job["regen_progress"] = 70
                    job["regen_message"] = "Applying visual effects..."
                elif "Canvas:" in line or "complete" in line.lower():
                    job["regen_progress"] = 90
                    job["regen_message"] = "Finalizing..."

            process.wait()

            if process.returncode == 0:
                canvas_path = regen_dir / "spotify_canvas_7s_9x16.mp4"
                if canvas_path.exists():
                    fixed_canvas = regen_dir / "spotify_canvas_web.mp4"
                    result = subprocess.run([
                        "ffmpeg", "-y",
                        "-i", str(canvas_path),
                        "-c:v", "libx264", "-profile:v", "baseline",
                        "-level", "3.0", "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart",
                        "-c:a", "aac", "-b:a", "128k",
                        str(fixed_canvas)
                    ], capture_output=True, text=True)

                    if result.returncode != 0:
                        print(f"FFmpeg re-encode failed: {result.stderr}")
                        shutil.copy(canvas_path, fixed_canvas)

                    job["regen_status"] = "complete"
                    job["regen_progress"] = 100
                    job["regen_message"] = "Regeneration complete!"
                    job["regen_outputs"] = {
                        "canvas": f"/outputs/{job_id}/regen/spotify_canvas_web.mp4?t={int(time.time())}",
                    }
                else:
                    job["regen_status"] = "error"
                    job["regen_message"] = "No output generated"
            else:
                job["regen_status"] = "error"
                job["regen_message"] = f"Regeneration failed with code {process.returncode}"

        except Exception as e:
            job["regen_status"] = "error"
            job["regen_message"] = str(e)

    def handle_upload(self):
        """Handle audio file upload."""
        try:
            content_type = self.headers.get('Content-Type', '')
            if 'multipart/form-data' not in content_type:
                self.send_json_error("Invalid content type", 400)
                return

            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)

            form = parse_multipart(content_type, body)

            if 'file' not in form:
                self.send_json_error("No file provided", 400)
                return

            file_data = form['file']
            if not file_data.get('filename'):
                self.send_json_error("No filename", 400)
                return

            job_id = str(uuid.uuid4())[:8]

            original_name = Path(file_data['filename']).name
            safe_name = "".join(c for c in original_name if c.isalnum() or c in "._- ")
            upload_path = UPLOAD_DIR / f"{job_id}_{safe_name}"

            with open(upload_path, 'wb') as f:
                f.write(file_data['content'])

            active_jobs[job_id] = {
                "id": job_id,
                "status": "uploaded",
                "filename": original_name,
                "upload_path": str(upload_path),
                "created_at": datetime.now().isoformat(),
                "progress": 0,
                "message": "File uploaded, ready to generate",
            }

            self.send_json_response({
                "success": True,
                "job_id": job_id,
                "filename": original_name,
            })

        except Exception as e:
            self.send_json_error(str(e), 500)

    def handle_generate(self):
        """Start generation for an uploaded file (v1 legacy — direct pipeline)."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)

            job_id = data.get('job_id')
            if not job_id or job_id not in active_jobs:
                self.send_json_error("Invalid job ID", 400)
                return

            job = active_jobs[job_id]
            if job["status"] not in ["uploaded", "error"]:
                self.send_json_error("Job already processing", 400)
                return

            job["status"] = "generating"
            job["progress"] = 10
            job["message"] = "Starting video generation..."

            thread = threading.Thread(
                target=self.run_pipeline,
                args=(job_id,),
                daemon=True
            )
            thread.start()

            self.send_json_response({
                "success": True,
                "job_id": job_id,
                "status": "generating",
            })

        except Exception as e:
            self.send_json_error(str(e), 500)

    def handle_status_get(self, job_id):
        """Get status of a generation job."""
        if job_id not in active_jobs:
            self.send_json_error("Job not found", 404)
            return

        job = active_jobs[job_id]
        self.send_json_response(job)

    def run_pipeline(self, job_id):
        """Run the Grammy pipeline for a job (v1 legacy)."""
        job = active_jobs[job_id]

        try:
            output_dir = OUTPUT_DIR / job_id
            output_dir.mkdir(exist_ok=True)

            job["output_dir"] = str(output_dir)
            job["progress"] = 20
            job["message"] = "Analyzing audio..."

            cmd = [
                sys.executable,
                str(PIPELINE_SCRIPT),
                "--audio", job["upload_path"],
                "--out", str(output_dir),
            ]

            if os.environ.get("LOOPCANVAS_MODE") == "fast":
                cmd.append("--fast")

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=str(PIPELINE_SCRIPT.parent),
            )

            for line in process.stdout:
                line = line.strip()
                print(f"[Pipeline {job_id}] {line}")

                if "[1/7]" in line or "Transcribing" in line:
                    job["progress"] = 15
                    job["message"] = "Transcribing lyrics..."
                elif "[2/7]" in line or "Audio structure" in line:
                    job["progress"] = 25
                    job["message"] = "Analyzing audio structure..."
                elif "[3/7]" in line or "Semantic" in line:
                    job["progress"] = 35
                    job["message"] = "Understanding mood and vibe..."
                elif "[4/7]" in line or "Deriving concept" in line:
                    job["progress"] = 45
                    job["message"] = "Building visual concept..."
                elif "[5/7]" in line or "cut plan" in line:
                    job["progress"] = 50
                    job["message"] = "Planning video cuts..."
                elif "[6/7]" in line or "Acquiring" in line:
                    job["progress"] = 55
                    job["message"] = "Generating visual assets..."
                elif "OK (local)" in line or "OK:" in line:
                    job["progress"] = min(job["progress"] + 5, 75)
                    job["message"] = "Creating clips..."
                elif "[7/7]" in line or "Rendering outputs" in line:
                    job["progress"] = 80
                    job["message"] = "Rendering final video..."
                elif "Canvas:" in line:
                    job["progress"] = 90
                    job["message"] = "Finalizing canvas..."
                elif "PIPELINE COMPLETE" in line:
                    job["progress"] = 95
                    job["message"] = "Almost done..."
                elif "Canvas complete" in line:
                    job["progress"] = 90
                    job["message"] = "Finalizing..."

            process.wait()

            if process.returncode == 0:
                canvas_path = output_dir / "spotify_canvas_7s_9x16.mp4"
                video_path = output_dir / "full_music_video_9x16.mp4"
                concept_path = output_dir / "concept.json"

                if canvas_path.exists():
                    fixed_canvas = output_dir / "spotify_canvas_web.mp4"
                    result = subprocess.run([
                        "ffmpeg", "-y",
                        "-i", str(canvas_path),
                        "-c:v", "libx264", "-profile:v", "baseline",
                        "-level", "3.0", "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart",
                        "-c:a", "aac", "-b:a", "128k",
                        str(fixed_canvas)
                    ], capture_output=True, text=True)

                    if result.returncode != 0:
                        print(f"FFmpeg re-encode failed: {result.stderr}")
                        shutil.copy(canvas_path, fixed_canvas)

                    job["status"] = "complete"
                    job["progress"] = 100
                    job["message"] = "Generation complete!"
                    job["outputs"] = {
                        "canvas": f"/outputs/{job_id}/spotify_canvas_web.mp4",
                        "full_video": f"/outputs/{job_id}/full_music_video_9x16.mp4" if video_path.exists() else None,
                        "concept": f"/outputs/{job_id}/concept.json" if concept_path.exists() else None,
                    }

                    if concept_path.exists():
                        with open(concept_path) as f:
                            concept = json.load(f)
                            job["track_info"] = {
                                "theme": concept.get("theme", "unknown"),
                                "thesis": concept.get("thesis", ""),
                            }
                else:
                    job["status"] = "error"
                    job["message"] = "Pipeline completed but no output files found"
            else:
                job["status"] = "error"
                job["message"] = f"Pipeline failed with code {process.returncode}"

        except Exception as e:
            job["status"] = "error"
            job["message"] = str(e)

    # ══════════════════════════════════════════════════════════════
    # UTILS
    # ══════════════════════════════════════════════════════════════

    def _read_json_body(self) -> dict:
        """Read and parse JSON body from request"""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        return json.loads(body)

    def send_json_response(self, data, status=200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def send_json_error(self, message, status=400):
        """Send JSON error response."""
        self.send_json_response({"error": message}, status)

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in separate threads for concurrent video streaming."""
    daemon_threads = True


def start_seed_runner():
    """Start the seed runner in background to bootstrap optimization"""
    try:
        from agents.seed_runner import SeedRunner
        runner = SeedRunner()
        tracks = runner.discover_audio()
        if tracks:
            print(f"[Seed Runner] Found {len(tracks)} tracks. Starting continuous optimization...")
            runner.run_continuous(max_batches=0)
        else:
            print("[Seed Runner] No audio files found. Skipping.")
    except Exception as e:
        import traceback
        print(f"[Seed Runner] CRASHED: {e}")
        traceback.print_exc()


def run_server():
    """Start the server."""
    os.chdir(APP_DIR)

    # Pre-load orchestrator in background
    threading.Thread(target=get_orchestrator, daemon=True).start()

    # Auto-start seed runner for continuous optimization
    if os.environ.get("LOOPCANVAS_SEED", "1") == "1":
        threading.Thread(target=start_seed_runner, daemon=True).start()

    server = ThreadedHTTPServer(('', PORT), LoopCanvasHandler)

    seed_status = "ACTIVE" if os.environ.get("LOOPCANVAS_SEED", "1") == "1" else "disabled (set LOOPCANVAS_SEED=1)"

    print(f"""
╔══════════════════════════════════════════════════════════╗
║           LoopCanvas v2.0 — Canvas Agent Army            ║
╠══════════════════════════════════════════════════════════╣
║  Server:    http://localhost:{PORT}                        ║
║  Mode:      {os.environ.get('LOOPCANVAS_MODE', 'fast'):12s}                         ║
║  Cost:      $0 ceiling enforced                          ║
║  Seed:      {seed_status:42s} ║
║                                                          ║
║  v1 API:    /api/upload, /api/generate, /api/status      ║
║  v2 API:    /api/v2/analyze, /api/v2/directions          ║
║             /api/v2/select, /api/v2/iterate              ║
║             /api/v2/edit, /api/v2/export                 ║
║             /api/v2/platforms, /api/v2/cost-report        ║
║  Queue:     /api/v2/queue/claim, /queue/progress         ║
║             /api/v2/queue/complete, /queue/fail           ║
║             /api/v2/queue/submit, /queue/stats            ║
╚══════════════════════════════════════════════════════════╝
    """)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    run_server()
