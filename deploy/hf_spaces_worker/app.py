#!/usr/bin/env python3
"""
LoopCanvas GPU Worker — HuggingFace Spaces Edition

Deploy this as a HuggingFace Space (Gradio SDK, GPU T4) and it will:
1. Connect to your LoopCanvas API server
2. Poll for generation jobs
3. Generate canvases at FULL SDXL + SVD quality on the free T4 GPU
4. Upload results back to the server
5. Show a live dashboard of worker status

HuggingFace Spaces free tier:
  - T4 GPU (16GB VRAM) — enough for SDXL + SVD
  - 2 vCPU, 16GB RAM
  - Sleeps after 48h inactivity (auto-wakes on request)
  - Unlimited usage when active

To deploy:
  1. Create a new HF Space: huggingface.co/new-space
  2. Select Gradio SDK, GPU T4 (free)
  3. Upload this app.py + requirements.txt
  4. Set secrets: LOOPCANVAS_SERVER_URL = your server URL
  5. The worker starts automatically

Cost: $0 (HF Spaces free GPU tier)
"""

import os
import sys
import json
import time
import threading
from pathlib import Path
from datetime import datetime

import gradio as gr

# ──────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────

SERVER_URL = os.environ.get("LOOPCANVAS_SERVER_URL", "")
WORKER_ID = os.environ.get("WORKER_ID", "hf-spaces-t4")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "15"))
MAX_IDLE_MINUTES = int(os.environ.get("MAX_IDLE_MINUTES", "0"))  # 0 = unlimited

# ──────────────────────────────────────────────────────────
# Worker State (shared between Gradio UI and worker thread)
# ──────────────────────────────────────────────────────────

worker_state = {
    "status": "initializing",
    "server_url": SERVER_URL,
    "worker_id": WORKER_ID,
    "gpu": "detecting...",
    "jobs_completed": 0,
    "jobs_failed": 0,
    "current_job": None,
    "current_progress": 0,
    "current_message": "",
    "last_activity": datetime.now().isoformat(),
    "total_generation_time": 0,
    "log": [],
}


def log(msg: str):
    """Add to worker log"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = f"[{timestamp}] {msg}"
    worker_state["log"].append(entry)
    # Keep last 100 entries
    if len(worker_state["log"]) > 100:
        worker_state["log"] = worker_state["log"][-100:]
    print(entry)


# ──────────────────────────────────────────────────────────
# GPU Detection
# ──────────────────────────────────────────────────────────

def detect_gpu():
    """Detect available GPU and set up CUDA"""
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            gpu_mem = torch.cuda.get_device_properties(0).total_mem / 1e9
            worker_state["gpu"] = f"{gpu_name} ({gpu_mem:.1f}GB)"
            log(f"GPU detected: {gpu_name} ({gpu_mem:.1f}GB VRAM)")
            return True
        else:
            worker_state["gpu"] = "None (CPU only)"
            log("WARNING: No GPU detected. Generation will be slow.")
            return False
    except ImportError:
        worker_state["gpu"] = "torch not available"
        log("ERROR: PyTorch not installed")
        return False


# ──────────────────────────────────────────────────────────
# Queue Communication (HTTP to your API server)
# ──────────────────────────────────────────────────────────

import urllib.request
import urllib.error


def api_post(endpoint: str, data: dict) -> dict:
    """POST JSON to the API server"""
    url = f"{SERVER_URL}{endpoint}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def claim_job() -> dict:
    """Claim next job from queue"""
    try:
        result = api_post("/api/v2/queue/claim", {
            "worker_id": WORKER_ID,
            "worker_type": "hf_spaces",
            "gpu": worker_state["gpu"],
        })
        return result.get("job")
    except Exception as e:
        log(f"Claim error: {e}")
        return None


def report_progress(job_id: str, progress: int, message: str):
    """Report progress to server"""
    try:
        api_post("/api/v2/queue/progress", {
            "job_id": job_id,
            "progress": progress,
            "message": message,
        })
    except Exception:
        pass  # Non-critical


def report_complete(job_id: str, output_dir: str, quality_score: float, loop_score: float):
    """Report completion to server"""
    try:
        api_post("/api/v2/queue/complete", {
            "job_id": job_id,
            "output_dir": output_dir,
            "quality_score": quality_score,
            "loop_score": loop_score,
        })
    except Exception as e:
        log(f"Complete report error: {e}")


def report_failure(job_id: str, error: str):
    """Report failure to server"""
    try:
        api_post("/api/v2/queue/fail", {
            "job_id": job_id,
            "error": error,
        })
    except Exception:
        pass


# ──────────────────────────────────────────────────────────
# Generation Pipeline
# ──────────────────────────────────────────────────────────

def generate_canvas(job: dict) -> tuple:
    """
    Run full-quality generation for a job.
    Returns: (success, output_dir_or_error)
    """
    import subprocess
    import tempfile

    job_id = job["job_id"]
    audio_path = job.get("audio_path", "")
    audio_url = job.get("audio_url", "")
    direction = job.get("direction", {})
    params = job.get("params", {})

    output_dir = os.path.join(tempfile.mkdtemp(prefix="canvas_"), job_id)
    os.makedirs(output_dir, exist_ok=True)

    start_time = time.time()

    try:
        # Step 1: Get audio file
        worker_state["current_message"] = "Preparing audio..."
        report_progress(job_id, 5, "Preparing audio...")

        if audio_url:
            local_audio = os.path.join(output_dir, "audio.mp3")
            urllib.request.urlretrieve(audio_url, local_audio)
            audio_path = local_audio
        elif audio_url := job.get("audio_url"):
            local_audio = os.path.join(output_dir, "audio.mp3")
            urllib.request.urlretrieve(audio_url, local_audio)
            audio_path = local_audio

        if not os.path.exists(audio_path):
            return False, f"Audio file not found: {audio_path}"

        # Step 2: Find the pipeline script
        # On HF Spaces, this would be cloned into /home/user/app/
        pipeline_candidates = [
            Path("/home/user/app/loopcanvas_grammy.py"),
            Path(__file__).parent.parent.parent / "loopcanvas_grammy.py",
        ]
        pipeline_script = None
        for p in pipeline_candidates:
            if p.exists():
                pipeline_script = str(p)
                break

        if not pipeline_script:
            return False, "Pipeline script not found"

        # Step 3: Build command — FULL quality, no --fast
        cmd = [
            sys.executable, pipeline_script,
            "--audio", audio_path,
            "--out", output_dir,
        ]

        # Style from direction
        style_map = {
            "spike_jonze": "memory_in_motion",
            "hype_williams": "peak_transmission",
            "dave_meyers": "concrete_heat",
            "khalil_joseph": "analog_memory",
            "wong_kar_wai": "midnight_city",
            "the_daniels": "euphoric_drift",
            "observed_moment": "memory_in_motion",
        }
        style = style_map.get(direction.get("director_style", ""), "memory_in_motion")
        cmd.extend(["--style", style])

        env = os.environ.copy()
        env["LOOPCANVAS_MODE"] = "local"  # Full GPU mode
        env["LOOPCANVAS_GRAIN"] = str(params.get("grain", 0.18))
        env["LOOPCANVAS_SATURATION"] = str(params.get("saturation", 0.75))
        env["LOOPCANVAS_CONTRAST"] = str(params.get("contrast", 0.80))

        # Step 4: Run pipeline
        report_progress(job_id, 15, "Starting generation pipeline...")
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )

        for line in process.stdout:
            line = line.strip()
            if not line:
                continue

            if "[1/7]" in line:
                report_progress(job_id, 20, "Transcribing lyrics...")
            elif "[2/7]" in line:
                report_progress(job_id, 30, "Analyzing audio structure...")
            elif "[3/7]" in line:
                report_progress(job_id, 35, "Understanding mood...")
            elif "[4/7]" in line:
                report_progress(job_id, 40, "Building visual concept...")
            elif "[5/7]" in line:
                report_progress(job_id, 50, "Generating AI visuals...")
            elif "[7/7]" in line:
                report_progress(job_id, 75, "Rendering final video...")
            elif "PIPELINE COMPLETE" in line:
                report_progress(job_id, 85, "Running quality checks...")

        process.wait()

        if process.returncode != 0:
            return False, f"Pipeline failed (exit {process.returncode})"

        # Step 5: Quality gate
        report_progress(job_id, 88, "Quality gate check...")
        quality_score = _run_quality_gate(output_dir)

        # Step 6: Loop validation
        report_progress(job_id, 92, "Loop validation...")
        loop_score = _run_loop_check(output_dir)

        # Step 7: Web encode
        report_progress(job_id, 95, "Encoding for web...")
        _web_encode(output_dir)

        elapsed = time.time() - start_time
        report_progress(job_id, 100, f"Complete in {elapsed:.0f}s")

        return True, output_dir, quality_score, loop_score, elapsed

    except Exception as e:
        return False, str(e), 0.0, 0.0, 0.0


def _run_quality_gate(output_dir: str) -> float:
    try:
        # Import from canvas-engine if available
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "canvas-engine"))
        from quality_gate_wrapper import QualityGateWrapper
        gate = QualityGateWrapper()
        canvas = Path(output_dir) / "spotify_canvas_7s_9x16.mp4"
        if canvas.exists():
            result = gate.evaluate(str(canvas))
            return result.get("overall_score", 0.0)
    except Exception:
        pass
    return 0.0


def _run_loop_check(output_dir: str) -> float:
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "canvas-engine"))
        from loop.seamless_loop import CanvasLoopEngine
        engine = CanvasLoopEngine()
        canvas = Path(output_dir) / "spotify_canvas_7s_9x16.mp4"
        if canvas.exists():
            analysis = engine.analyze_loop(str(canvas))
            if not analysis.is_seamless and analysis.recommended_crossfade_frames > 0:
                fixed = str(canvas).replace(".mp4", "_fixed.mp4")
                success, _ = engine.create_seamless_loop(
                    str(canvas), fixed, analysis.recommended_crossfade_frames
                )
                if success:
                    os.replace(fixed, str(canvas))
            return analysis.seamlessness_score
    except Exception:
        pass
    return 0.0


def _web_encode(output_dir: str):
    import subprocess
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
# Worker Loop (runs in background thread)
# ──────────────────────────────────────────────────────────

def worker_loop():
    """Main worker loop — polls queue and processes jobs"""
    log("Worker starting...")

    if not SERVER_URL:
        log("ERROR: LOOPCANVAS_SERVER_URL not set. Add it as a Space secret.")
        worker_state["status"] = "error: no server URL"
        return

    detect_gpu()

    worker_state["status"] = "running"
    log(f"Connected to {SERVER_URL}")
    log(f"Worker ID: {WORKER_ID}")
    log(f"Polling every {POLL_INTERVAL}s")

    idle_start = time.time()

    while True:
        try:
            job = claim_job()

            if job:
                idle_start = time.time()
                job_id = job["job_id"]

                worker_state["current_job"] = job_id
                worker_state["current_progress"] = 0
                worker_state["current_message"] = "Starting..."
                worker_state["last_activity"] = datetime.now().isoformat()
                log(f"Claimed job {job_id}")

                result = generate_canvas(job)

                if result[0]:  # success
                    _, output_dir, quality, loop, elapsed = result
                    report_complete(job_id, output_dir, quality, loop)
                    worker_state["jobs_completed"] += 1
                    worker_state["total_generation_time"] += elapsed
                    log(f"Completed {job_id} in {elapsed:.0f}s (quality={quality:.1f})")
                else:
                    _, error = result[0], result[1]
                    report_failure(job_id, error)
                    worker_state["jobs_failed"] += 1
                    log(f"Failed {job_id}: {error}")

                worker_state["current_job"] = None
                worker_state["current_progress"] = 0
                worker_state["current_message"] = ""
            else:
                # No work
                idle_min = (time.time() - idle_start) / 60
                if MAX_IDLE_MINUTES > 0 and idle_min >= MAX_IDLE_MINUTES:
                    log(f"Idle for {idle_min:.0f}min. Shutting down.")
                    worker_state["status"] = "idle_shutdown"
                    break

                time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            log("Shutting down...")
            break
        except Exception as e:
            log(f"Error: {e}")
            time.sleep(POLL_INTERVAL)

    worker_state["status"] = "stopped"


# ──────────────────────────────────────────────────────────
# Gradio Dashboard
# ──────────────────────────────────────────────────────────

def get_status():
    """Build status display for dashboard"""
    s = worker_state

    avg_time = ""
    if s["jobs_completed"] > 0:
        avg = s["total_generation_time"] / s["jobs_completed"]
        avg_time = f"\nAvg generation time: {avg:.0f}s"

    current = ""
    if s["current_job"]:
        current = f"\n\nCurrent Job: {s['current_job']}\nProgress: {s['current_progress']}%\nMessage: {s['current_message']}"

    status = f"""LoopCanvas GPU Worker Dashboard
{'='*40}

Status:     {s['status']}
Worker ID:  {s['worker_id']}
GPU:        {s['gpu']}
Server:     {s['server_url'] or 'NOT SET'}

Jobs completed: {s['jobs_completed']}
Jobs failed:    {s['jobs_failed']}{avg_time}

Last activity: {s['last_activity']}{current}
"""
    return status


def get_log():
    """Get recent log entries"""
    return "\n".join(worker_state["log"][-50:])


# Build Gradio UI
with gr.Blocks(title="LoopCanvas GPU Worker", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# LoopCanvas GPU Worker")
    gr.Markdown("This Space runs as a GPU worker for LoopCanvas canvas generation.")

    with gr.Row():
        with gr.Column(scale=1):
            status_box = gr.Textbox(
                label="Worker Status",
                value=get_status,
                lines=18,
                every=5,
                interactive=False,
            )
        with gr.Column(scale=1):
            log_box = gr.Textbox(
                label="Worker Log",
                value=get_log,
                lines=18,
                every=3,
                interactive=False,
            )

    gr.Markdown("""
    ### Setup
    1. Set `LOOPCANVAS_SERVER_URL` in Space secrets → your API server URL
    2. The worker automatically connects and starts processing jobs
    3. Each canvas takes ~30-90 seconds on T4 GPU
    """)


# Start worker thread on launch
worker_thread = threading.Thread(target=worker_loop, daemon=True)
worker_thread.start()

# Launch Gradio
if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
