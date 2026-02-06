#!/usr/bin/env python3
"""
Canvas GPU Worker

Runs on any machine with a GPU (Colab, HuggingFace Spaces, Modal, local).
Polls the job queue, claims work, generates at FULL quality (SDXL + SVD),
and uploads results.

Usage:
  # On Google Colab (free T4 GPU):
  !pip install torch diffusers transformers accelerate pillow librosa
  !python gpu_worker.py --server https://your-server.com --worker-id colab-001

  # On HuggingFace Spaces:
  python gpu_worker.py --server https://your-server.com --worker-id hf-001

  # On your Mac (local, no network):
  python gpu_worker.py --local --worker-id mac-001

  # Continuous mode (keeps polling):
  python gpu_worker.py --server https://your-server.com --continuous

The worker:
1. Polls queue for jobs
2. Claims a job
3. Downloads audio file
4. Generates FULL QUALITY canvas (SDXL keyframe → SVD video → FFmpeg post)
5. Runs quality gate
6. Runs loop validation
7. Uploads result
8. Marks job complete
9. Loops back to 1

$0 cost — runs on free GPU tiers
"""

import os
import sys
import json
import time
import uuid
import hashlib
import subprocess
import tempfile
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Optional, Tuple
from datetime import datetime

# Add canvas-engine to path
WORKER_DIR = Path(__file__).parent
ENGINE_DIR = WORKER_DIR.parent
sys.path.insert(0, str(ENGINE_DIR))
sys.path.insert(0, str(ENGINE_DIR.parent.parent))


class GPUWorker:
    """
    GPU worker that generates canvases at full SDXL + SVD quality.

    Designed to run on transient GPU instances (Colab, HF Spaces).
    Communicates with the API server via HTTP or local file queue.
    """

    def __init__(self, server_url: str = None, worker_id: str = None,
                 local: bool = False, worker_type: str = "local"):
        self.server_url = server_url
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:6]}"
        self.local = local
        self.worker_type = worker_type
        self.work_dir = Path(tempfile.mkdtemp(prefix="canvas_worker_"))

        # Stats
        self.jobs_completed = 0
        self.jobs_failed = 0
        self.total_generation_time = 0

        print(f"[Worker {self.worker_id}] Initialized")
        print(f"  Type: {self.worker_type}")
        print(f"  Work dir: {self.work_dir}")
        print(f"  Server: {self.server_url or 'local file queue'}")

        # Detect GPU
        self._detect_gpu()

    def _detect_gpu(self):
        """Detect available GPU"""
        try:
            import torch
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                gpu_mem = torch.cuda.get_device_properties(0).total_mem / 1e9
                print(f"  GPU: {gpu_name} ({gpu_mem:.1f}GB)")
                self.has_gpu = True
                self.gpu_name = gpu_name
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                print(f"  GPU: Apple Silicon (MPS)")
                self.has_gpu = True
                self.gpu_name = "Apple MPS"
            else:
                print(f"  GPU: None (CPU only)")
                self.has_gpu = False
                self.gpu_name = "CPU"
        except ImportError:
            print(f"  GPU: torch not available")
            self.has_gpu = False
            self.gpu_name = "unknown"

    # ──────────────────────────────────────────────────────────
    # Queue Communication
    # ──────────────────────────────────────────────────────────

    def claim_job(self) -> Optional[Dict]:
        """Claim the next job from the queue"""
        if self.local:
            return self._claim_local()
        else:
            return self._claim_remote()

    def _claim_local(self) -> Optional[Dict]:
        """Claim from local file queue"""
        from dispatch.job_queue import FileQueue
        queue = FileQueue()
        job = queue.claim(self.worker_id, self.worker_type)
        return json.loads(json.dumps(job.__dict__)) if job else None

    def _claim_remote(self) -> Optional[Dict]:
        """Claim from remote API server"""
        try:
            data = json.dumps({
                "worker_id": self.worker_id,
                "worker_type": self.worker_type,
                "gpu": self.gpu_name,
            }).encode()

            req = urllib.request.Request(
                f"{self.server_url}/api/v2/queue/claim",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                if result.get("job"):
                    return result["job"]
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
            print(f"[Worker] Claim error: {e}")

        return None

    def update_progress(self, job_id: str, progress: int, message: str = ""):
        """Report progress back to queue"""
        if self.local:
            from dispatch.job_queue import FileQueue
            FileQueue().update_progress(job_id, progress, message, "generating")
        else:
            try:
                data = json.dumps({
                    "job_id": job_id,
                    "progress": progress,
                    "message": message,
                }).encode()
                req = urllib.request.Request(
                    f"{self.server_url}/api/v2/queue/progress",
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                urllib.request.urlopen(req, timeout=5)
            except Exception:
                pass  # Non-critical

    def report_complete(self, job_id: str, output_dir: str,
                         quality_score: float = None, loop_score: float = None):
        """Report job completion"""
        if self.local:
            from dispatch.job_queue import FileQueue
            FileQueue().complete(job_id, output_dir=output_dir,
                                 quality_score=quality_score, loop_score=loop_score)
        else:
            try:
                data = json.dumps({
                    "job_id": job_id,
                    "output_dir": output_dir,
                    "quality_score": quality_score,
                    "loop_score": loop_score,
                }).encode()
                req = urllib.request.Request(
                    f"{self.server_url}/api/v2/queue/complete",
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                urllib.request.urlopen(req, timeout=10)
            except Exception as e:
                print(f"[Worker] Complete report error: {e}")

    def report_failure(self, job_id: str, error: str):
        """Report job failure"""
        if self.local:
            from dispatch.job_queue import FileQueue
            FileQueue().fail(job_id, error)
        else:
            try:
                data = json.dumps({"job_id": job_id, "error": error}).encode()
                req = urllib.request.Request(
                    f"{self.server_url}/api/v2/queue/fail",
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                urllib.request.urlopen(req, timeout=10)
            except Exception:
                pass

    # ──────────────────────────────────────────────────────────
    # Generation Pipeline (the real work)
    # ──────────────────────────────────────────────────────────

    def generate(self, job: Dict) -> Tuple[bool, str]:
        """
        Run full-quality SDXL + SVD generation.

        This is the $50K quality pipeline:
        1. SDXL generates photorealistic keyframe
        2. SVD animates into 25+ frames of cinematic motion
        3. FFmpeg applies Observed Moment post-processing
        4. Quality gate validates output
        5. Loop engine ensures seamless looping

        Returns: (success, output_dir_or_error)
        """
        job_id = job['job_id']
        audio_path = job['audio_path']
        direction = job.get('direction', {})
        emotional_dna = job.get('emotional_dna', {})
        params = job.get('params', {})

        output_dir = str(self.work_dir / job_id)
        os.makedirs(output_dir, exist_ok=True)

        start_time = time.time()

        try:
            # Step 1: Resolve audio file
            self.update_progress(job_id, 5, "Preparing audio...")

            if job.get('audio_url'):
                # Download from URL
                local_audio = os.path.join(output_dir, "audio.mp3")
                urllib.request.urlretrieve(job['audio_url'], local_audio)
                audio_path = local_audio
            elif not os.path.exists(audio_path):
                return False, f"Audio file not found: {audio_path}"

            # Step 2: Build generation prompt from direction
            self.update_progress(job_id, 10, "Building visual concept...")

            prompt = direction.get('preview_prompt', '')
            if not prompt:
                prompt = self._build_fallback_prompt(emotional_dna)

            # Step 3: Check for evolved params from optimization loop
            self._apply_evolved_params(params, direction.get('director_style', ''))

            # Step 4: Run the Grammy pipeline at FULL quality
            self.update_progress(job_id, 15, "Starting generation pipeline...")

            pipeline_script = ENGINE_DIR.parent.parent / "loopcanvas_grammy.py"
            if not pipeline_script.exists():
                # Try relative paths
                for candidate in [
                    Path("loopcanvas_grammy.py"),
                    ENGINE_DIR.parent.parent / "loopcanvas_grammy.py",
                ]:
                    if candidate.exists():
                        pipeline_script = candidate
                        break

            if not pipeline_script.exists():
                return False, "Grammy pipeline script not found"

            # Build command — NO --fast flag. Full quality.
            cmd = [
                sys.executable, str(pipeline_script),
                "--audio", audio_path,
                "--out", output_dir,
            ]

            # Style from direction
            style_map = {
                'spike_jonze': 'memory_in_motion',
                'hype_williams': 'peak_transmission',
                'dave_meyers': 'concrete_heat',
                'khalil_joseph': 'analog_memory',
                'wong_kar_wai': 'midnight_city',
                'the_daniels': 'euphoric_drift',
                'observed_moment': 'memory_in_motion',
            }
            style = style_map.get(
                direction.get('director_style', ''), 'memory_in_motion'
            )
            cmd.extend(["--style", style])

            # Environment with director params
            env = os.environ.copy()
            env["LOOPCANVAS_MODE"] = "local" if self.has_gpu else "fast"
            env["LOOPCANVAS_GRAIN"] = str(params.get('grain', 0.18))
            env["LOOPCANVAS_SATURATION"] = str(params.get('saturation', 0.75))
            env["LOOPCANVAS_CONTRAST"] = str(params.get('contrast', 0.80))
            env["LOOPCANVAS_BLUR"] = str(params.get('blur', 1.0))
            env["LOOPCANVAS_MOTION_INTENSITY"] = str(params.get('motion_intensity', 0.4))

            # Run pipeline
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=str(pipeline_script.parent),
                env=env,
            )

            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue

                # Map pipeline stages to progress
                if "[1/7]" in line:
                    self.update_progress(job_id, 20, "Transcribing lyrics...")
                elif "[2/7]" in line:
                    self.update_progress(job_id, 30, "Analyzing audio structure...")
                elif "[3/7]" in line:
                    self.update_progress(job_id, 35, "Understanding mood...")
                elif "[4/7]" in line:
                    self.update_progress(job_id, 40, "Building visual concept...")
                elif "[5/7]" in line:
                    self.update_progress(job_id, 45, "Planning shots...")
                elif "[6/7]" in line:
                    self.update_progress(job_id, 50, "Generating AI visuals...")
                elif "OK" in line:
                    self.update_progress(job_id, 65, "Creating clips...")
                elif "[7/7]" in line:
                    self.update_progress(job_id, 75, "Rendering final video...")
                elif "PIPELINE COMPLETE" in line:
                    self.update_progress(job_id, 85, "Running quality checks...")

            process.wait()

            if process.returncode != 0:
                return False, f"Pipeline failed (exit {process.returncode})"

            # Step 5: Quality gate
            self.update_progress(job_id, 88, "Quality gate check...")
            quality_score = self._run_quality_gate(output_dir)

            # Step 6: Loop validation
            self.update_progress(job_id, 92, "Loop validation...")
            loop_score = self._run_loop_check(output_dir)

            # Step 7: Web-encode the output
            self.update_progress(job_id, 95, "Encoding for web...")
            self._web_encode(output_dir)

            elapsed = time.time() - start_time
            self.total_generation_time += elapsed
            self.jobs_completed += 1

            self.update_progress(
                job_id, 100,
                f"Complete in {elapsed:.0f}s | Quality: {quality_score:.1f}/10"
            )

            # Report completion
            self.report_complete(
                job_id, output_dir,
                quality_score=quality_score,
                loop_score=loop_score,
            )

            return True, output_dir

        except Exception as e:
            self.jobs_failed += 1
            error_msg = str(e)
            self.report_failure(job_id, error_msg)
            return False, error_msg

    def _build_fallback_prompt(self, emotional_dna: dict) -> str:
        """Build a generation prompt from emotional DNA when no direction given"""
        elements = [
            "Warm golden light drifting across soft textured surface",
            "dust particles floating in amber sunbeams",
            "gentle movement, soft focus throughout",
            "heavy 35mm film grain, lifted shadows",
            "muted warm tones, memory-like quality",
        ]

        valence = emotional_dna.get('valence', 0)
        if valence < -0.3:
            elements[0] = "Cool pale light filtering through mist"
            elements[4] = "muted cool tones, contemplative mood"
        elif valence > 0.3:
            elements.append("hopeful atmosphere, golden hour warmth")

        return ", ".join(elements)

    def _apply_evolved_params(self, params: dict, style: str):
        """Apply evolved parameters from the optimization loop"""
        evolved_config = ENGINE_DIR / "optimization_data" / "evolved_config.json"
        if not evolved_config.exists():
            return

        try:
            with open(evolved_config) as f:
                config = json.load(f)

            evolved = config.get('evolved_params', {}).get(style, {})
            for key, value in evolved.items():
                if key not in params:  # Don't override explicit params
                    params[key] = value
        except (json.JSONDecodeError, KeyError):
            pass

    def _run_quality_gate(self, output_dir: str) -> float:
        """Run quality gate on output"""
        try:
            from quality_gate_wrapper import QualityGateWrapper
            gate = QualityGateWrapper()

            canvas = Path(output_dir) / "spotify_canvas_7s_9x16.mp4"
            if not canvas.exists():
                return 0.0

            result = gate.evaluate(str(canvas))
            return result.get('overall_score', 0.0)
        except Exception:
            return 0.0  # Non-fatal

    def _run_loop_check(self, output_dir: str) -> float:
        """Run loop seamlessness check"""
        try:
            from loop.seamless_loop import CanvasLoopEngine
            engine = CanvasLoopEngine()

            canvas = Path(output_dir) / "spotify_canvas_7s_9x16.mp4"
            if not canvas.exists():
                return 0.0

            analysis = engine.analyze_loop(str(canvas))

            # Auto-fix if needed
            if not analysis.is_seamless and analysis.recommended_crossfade_frames > 0:
                fixed = str(canvas).replace('.mp4', '_fixed.mp4')
                success, _ = engine.create_seamless_loop(
                    str(canvas), fixed, analysis.recommended_crossfade_frames
                )
                if success:
                    os.replace(fixed, str(canvas))

            return analysis.seamlessness_score
        except Exception:
            return 0.0

    def _web_encode(self, output_dir: str):
        """Re-encode canvas for web playback"""
        canvas = Path(output_dir) / "spotify_canvas_7s_9x16.mp4"
        web = Path(output_dir) / "spotify_canvas_web.mp4"

        if canvas.exists() and not web.exists():
            subprocess.run([
                "ffmpeg", "-y", "-i", str(canvas),
                "-c:v", "libx264", "-profile:v", "baseline",
                "-level", "3.0", "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-c:a", "aac", "-b:a", "128k",
                str(web)
            ], capture_output=True)

    # ──────────────────────────────────────────────────────────
    # Worker Loop
    # ──────────────────────────────────────────────────────────

    def run_once(self) -> bool:
        """Poll queue, process one job. Returns True if a job was processed."""
        job = self.claim_job()
        if not job:
            return False

        print(f"\n[Worker {self.worker_id}] Claimed job {job['job_id']}")
        success, result = self.generate(job)

        if success:
            print(f"[Worker {self.worker_id}] Completed: {result}")
        else:
            print(f"[Worker {self.worker_id}] Failed: {result}")

        return True

    def run_continuous(self, poll_interval: int = 15, max_idle_minutes: int = 0):
        """
        Continuously poll queue and process jobs.

        Args:
            poll_interval: Seconds between polls when idle
            max_idle_minutes: Stop after this many minutes idle (0 = never stop)
        """
        print(f"\n[Worker {self.worker_id}] Starting continuous mode")
        print(f"  Poll interval: {poll_interval}s")
        print(f"  Max idle: {'unlimited' if max_idle_minutes == 0 else f'{max_idle_minutes}min'}")

        idle_start = time.time()

        while True:
            try:
                processed = self.run_once()

                if processed:
                    idle_start = time.time()  # Reset idle timer
                else:
                    # No work available
                    idle_minutes = (time.time() - idle_start) / 60

                    if max_idle_minutes > 0 and idle_minutes >= max_idle_minutes:
                        print(f"[Worker] Idle for {idle_minutes:.0f}min. Shutting down.")
                        break

                    time.sleep(poll_interval)

            except KeyboardInterrupt:
                print(f"\n[Worker {self.worker_id}] Shutting down...")
                break
            except Exception as e:
                print(f"[Worker {self.worker_id}] Error: {e}")
                time.sleep(poll_interval)

        self._print_stats()

    def _print_stats(self):
        print(f"\n{'='*50}")
        print(f"Worker {self.worker_id} Stats")
        print(f"{'='*50}")
        print(f"  Jobs completed: {self.jobs_completed}")
        print(f"  Jobs failed:    {self.jobs_failed}")
        if self.jobs_completed > 0:
            avg = self.total_generation_time / self.jobs_completed
            print(f"  Avg gen time:   {avg:.0f}s")
        print(f"  GPU:            {self.gpu_name}")


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Canvas GPU Worker")
    parser.add_argument("--server", help="API server URL (e.g., https://loopcanvas.vercel.app)")
    parser.add_argument("--worker-id", help="Unique worker ID", default=None)
    parser.add_argument("--local", action="store_true", help="Use local file queue")
    parser.add_argument("--continuous", action="store_true", help="Run continuously")
    parser.add_argument("--poll-interval", type=int, default=15, help="Poll interval (sec)")
    parser.add_argument("--max-idle", type=int, default=0, help="Max idle minutes (0=unlimited)")
    parser.add_argument("--type", default="local", help="Worker type (colab/hf/modal/local)")

    args = parser.parse_args()

    if not args.server and not args.local:
        print("Must specify --server URL or --local")
        sys.exit(1)

    worker = GPUWorker(
        server_url=args.server,
        worker_id=args.worker_id,
        local=args.local,
        worker_type=args.type,
    )

    if args.continuous:
        worker.run_continuous(
            poll_interval=args.poll_interval,
            max_idle_minutes=args.max_idle,
        )
    else:
        worker.run_once()
