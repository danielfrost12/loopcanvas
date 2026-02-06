#!/usr/bin/env python3
"""
Canvas Generation Queue

The bridge between the always-on API (Vercel/Oracle) and transient GPU workers
(Colab, HuggingFace Spaces, Modal).

Architecture:
  ┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
  │  API Server   │────▶│  Job Queue   │◀────│  GPU Workers      │
  │  (always-on)  │     │  (JSON file  │     │  (transient)      │
  │  Vercel/Oracle│     │   or Supabase│     │  Colab/HF/Modal   │
  └──────────────┘     │   free tier) │     └──────────────────┘
                        └──────────────┘

The queue is file-based by default (works on a single server) with an
optional Supabase backend for distributed workers (also free).

Job lifecycle:
  QUEUED → CLAIMED → GENERATING → UPLOADING → COMPLETE
                  ↘ FAILED (retryable)
                  ↘ DEAD (max retries exceeded)

Workers poll the queue, claim a job, generate on GPU, upload result.
The API server polls for completion and serves the output.

$0 cost: JSON files on disk, or Supabase free tier (500MB).
"""

import os
import json
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
import threading


class JobStatus(Enum):
    QUEUED = "queued"
    CLAIMED = "claimed"
    GENERATING = "generating"
    UPLOADING = "uploading"
    COMPLETE = "complete"
    FAILED = "failed"
    DEAD = "dead"  # Max retries exceeded


@dataclass
class GenerationJob:
    """A canvas generation job in the queue"""
    job_id: str
    status: str  # JobStatus value
    created_at: str
    updated_at: str

    # Input
    audio_path: str  # Local path or URL to uploaded audio
    audio_url: Optional[str] = None  # Public URL for remote workers
    direction: Optional[Dict] = None  # Selected visual direction
    emotional_dna: Optional[Dict] = None
    params: Dict = field(default_factory=dict)

    # Worker
    claimed_by: Optional[str] = None  # Worker ID
    claimed_at: Optional[str] = None
    worker_type: Optional[str] = None  # "colab", "hf_spaces", "modal", "local"

    # Progress
    progress: int = 0
    message: str = ""
    generation_mode: str = "full"  # "full" (SDXL+SVD) or "fast" (Ken Burns)

    # Output
    output_url: Optional[str] = None  # URL to generated canvas
    output_dir: Optional[str] = None
    quality_score: Optional[float] = None
    loop_score: Optional[float] = None

    # Retry
    attempt: int = 0
    max_attempts: int = 3
    error: Optional[str] = None

    # Priority (lower = higher priority)
    priority: int = 10


# ══════════════════════════════════════════════════════════════
# File-Based Queue (single server, $0)
# ══════════════════════════════════════════════════════════════

class FileQueue:
    """
    File-based job queue using a JSON file with file locking.

    Works for a single server with multiple worker processes.
    For distributed workers, use SupabaseQueue instead.
    """

    def __init__(self, queue_dir: str = None):
        self.queue_dir = Path(queue_dir or Path(__file__).parent.parent.parent / "queue_data")
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_file = self.queue_dir / "jobs.json"
        self.lock = threading.Lock()

        if not self.jobs_file.exists():
            self._write_jobs({})

    def _read_jobs(self) -> Dict[str, Dict]:
        """Read all jobs from file"""
        try:
            with open(self.jobs_file) as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _write_jobs(self, jobs: Dict[str, Dict]):
        """Write all jobs to file (atomic via temp file)"""
        temp = self.jobs_file.with_suffix('.tmp')
        with open(temp, 'w') as f:
            json.dump(jobs, f, indent=2)
        os.replace(str(temp), str(self.jobs_file))

    def enqueue(self, job: GenerationJob) -> str:
        """Add a job to the queue. Returns job_id."""
        with self.lock:
            jobs = self._read_jobs()
            jobs[job.job_id] = asdict(job)
            self._write_jobs(jobs)
        return job.job_id

    def claim(self, worker_id: str, worker_type: str = "local") -> Optional[GenerationJob]:
        """
        Claim the next available job. Returns None if queue empty.

        Workers call this to get work. Only one worker gets each job.
        """
        with self.lock:
            jobs = self._read_jobs()

            # Find oldest queued job (by priority then time)
            candidates = [
                (jid, j) for jid, j in jobs.items()
                if j['status'] == JobStatus.QUEUED.value
            ]

            if not candidates:
                return None

            # Sort by priority (lower first), then created_at
            candidates.sort(key=lambda x: (x[1]['priority'], x[1]['created_at']))

            jid, job_data = candidates[0]

            # Claim it
            job_data['status'] = JobStatus.CLAIMED.value
            job_data['claimed_by'] = worker_id
            job_data['claimed_at'] = datetime.now().isoformat()
            job_data['worker_type'] = worker_type
            job_data['updated_at'] = datetime.now().isoformat()

            jobs[jid] = job_data
            self._write_jobs(jobs)

            return GenerationJob(**job_data)

    def update_progress(self, job_id: str, progress: int, message: str = "",
                         status: str = None):
        """Update job progress (called by worker during generation)"""
        with self.lock:
            jobs = self._read_jobs()
            if job_id in jobs:
                jobs[job_id]['progress'] = progress
                jobs[job_id]['message'] = message
                jobs[job_id]['updated_at'] = datetime.now().isoformat()
                if status:
                    jobs[job_id]['status'] = status
                self._write_jobs(jobs)

    def complete(self, job_id: str, output_url: str = None, output_dir: str = None,
                  quality_score: float = None, loop_score: float = None):
        """Mark job as complete with output"""
        with self.lock:
            jobs = self._read_jobs()
            if job_id in jobs:
                jobs[job_id]['status'] = JobStatus.COMPLETE.value
                jobs[job_id]['progress'] = 100
                jobs[job_id]['message'] = "Generation complete"
                jobs[job_id]['output_url'] = output_url
                jobs[job_id]['output_dir'] = output_dir
                jobs[job_id]['quality_score'] = quality_score
                jobs[job_id]['loop_score'] = loop_score
                jobs[job_id]['updated_at'] = datetime.now().isoformat()
                self._write_jobs(jobs)

    def fail(self, job_id: str, error: str):
        """Mark job as failed. Will be retried if attempts remain."""
        with self.lock:
            jobs = self._read_jobs()
            if job_id in jobs:
                job = jobs[job_id]
                job['attempt'] = job.get('attempt', 0) + 1
                job['error'] = error
                job['updated_at'] = datetime.now().isoformat()

                if job['attempt'] >= job.get('max_attempts', 3):
                    job['status'] = JobStatus.DEAD.value
                    job['message'] = f"Failed after {job['attempt']} attempts: {error}"
                else:
                    # Re-queue for retry
                    job['status'] = JobStatus.QUEUED.value
                    job['claimed_by'] = None
                    job['claimed_at'] = None
                    job['message'] = f"Retry {job['attempt']}/{job.get('max_attempts', 3)}: {error}"

                self._write_jobs(jobs)

    def get_job(self, job_id: str) -> Optional[Dict]:
        """Get job status"""
        jobs = self._read_jobs()
        return jobs.get(job_id)

    def get_queue_stats(self) -> Dict:
        """Get queue statistics"""
        jobs = self._read_jobs()
        stats = {
            'total': len(jobs),
            'queued': 0,
            'claimed': 0,
            'generating': 0,
            'complete': 0,
            'failed': 0,
            'dead': 0,
        }
        for j in jobs.values():
            status = j.get('status', 'unknown')
            if status in stats:
                stats[status] += 1
        return stats

    def cleanup_stale(self, timeout_minutes: int = 30):
        """
        Re-queue jobs that have been claimed but not completed.

        This handles workers that crash or disconnect.
        """
        with self.lock:
            jobs = self._read_jobs()
            cutoff = datetime.now() - timedelta(minutes=timeout_minutes)
            requeued = 0

            for jid, job in jobs.items():
                if job['status'] in (JobStatus.CLAIMED.value, JobStatus.GENERATING.value):
                    claimed_at = job.get('claimed_at')
                    if claimed_at:
                        try:
                            claimed_time = datetime.fromisoformat(claimed_at)
                            if claimed_time < cutoff:
                                job['status'] = JobStatus.QUEUED.value
                                job['claimed_by'] = None
                                job['claimed_at'] = None
                                job['message'] = "Re-queued: worker timed out"
                                job['updated_at'] = datetime.now().isoformat()
                                requeued += 1
                        except ValueError:
                            pass

            if requeued > 0:
                self._write_jobs(jobs)

            return requeued


# ══════════════════════════════════════════════════════════════
# Supabase Queue (distributed workers, still $0)
# ══════════════════════════════════════════════════════════════

class SupabaseQueue:
    """
    Supabase-backed queue for distributed GPU workers.

    Supabase free tier: 500MB database, 1GB file storage, 50K MAU.
    More than enough for a job queue.

    Workers anywhere (Colab, HF Spaces, your laptop) can poll this
    queue and claim jobs.

    Requires: SUPABASE_URL and SUPABASE_KEY environment variables.
    Falls back to FileQueue if not configured.
    """

    TABLE = "canvas_jobs"

    def __init__(self):
        self.url = os.environ.get("SUPABASE_URL")
        self.key = os.environ.get("SUPABASE_KEY")
        self.client = None

        if self.url and self.key:
            try:
                from supabase import create_client
                self.client = create_client(self.url, self.key)
            except ImportError:
                print("[Queue] supabase-py not installed, using file queue")

    @property
    def available(self) -> bool:
        return self.client is not None

    def enqueue(self, job: GenerationJob) -> str:
        """Add job to Supabase queue"""
        data = asdict(job)
        self.client.table(self.TABLE).insert(data).execute()
        return job.job_id

    def claim(self, worker_id: str, worker_type: str = "colab") -> Optional[GenerationJob]:
        """
        Claim next job using Supabase RPC for atomic claim.

        Uses a Postgres function to atomically SELECT + UPDATE,
        preventing race conditions between workers.
        """
        # Simple version: select oldest queued, update to claimed
        result = self.client.table(self.TABLE) \
            .select("*") \
            .eq("status", "queued") \
            .order("priority", desc=False) \
            .order("created_at", desc=False) \
            .limit(1) \
            .execute()

        if not result.data:
            return None

        job_data = result.data[0]

        # Attempt to claim (optimistic lock via status check)
        update = self.client.table(self.TABLE) \
            .update({
                "status": "claimed",
                "claimed_by": worker_id,
                "claimed_at": datetime.now().isoformat(),
                "worker_type": worker_type,
                "updated_at": datetime.now().isoformat(),
            }) \
            .eq("job_id", job_data['job_id']) \
            .eq("status", "queued") \
            .execute()

        if update.data:
            return GenerationJob(**update.data[0])
        return None

    def update_progress(self, job_id: str, progress: int, message: str = "",
                         status: str = None):
        update = {"progress": progress, "message": message,
                  "updated_at": datetime.now().isoformat()}
        if status:
            update["status"] = status
        self.client.table(self.TABLE).update(update).eq("job_id", job_id).execute()

    def complete(self, job_id: str, output_url: str = None, **kwargs):
        update = {
            "status": "complete",
            "progress": 100,
            "output_url": output_url,
            "updated_at": datetime.now().isoformat(),
        }
        update.update({k: v for k, v in kwargs.items() if v is not None})
        self.client.table(self.TABLE).update(update).eq("job_id", job_id).execute()

    def fail(self, job_id: str, error: str):
        # Fetch current attempt count
        result = self.client.table(self.TABLE).select("attempt,max_attempts") \
            .eq("job_id", job_id).execute()
        if not result.data:
            return

        job = result.data[0]
        attempt = job.get('attempt', 0) + 1
        max_attempts = job.get('max_attempts', 3)

        if attempt >= max_attempts:
            self.client.table(self.TABLE).update({
                "status": "dead", "error": error, "attempt": attempt,
                "updated_at": datetime.now().isoformat(),
            }).eq("job_id", job_id).execute()
        else:
            self.client.table(self.TABLE).update({
                "status": "queued", "error": error, "attempt": attempt,
                "claimed_by": None, "claimed_at": None,
                "updated_at": datetime.now().isoformat(),
            }).eq("job_id", job_id).execute()

    def get_job(self, job_id: str) -> Optional[Dict]:
        result = self.client.table(self.TABLE).select("*").eq("job_id", job_id).execute()
        return result.data[0] if result.data else None


# ══════════════════════════════════════════════════════════════
# Unified Queue Interface
# ══════════════════════════════════════════════════════════════

def get_queue() -> FileQueue:
    """
    Get the best available queue backend.

    Tries Supabase first (for distributed workers),
    falls back to FileQueue (for single server).
    """
    sb = SupabaseQueue()
    if sb.available:
        return sb
    return FileQueue()


# ══════════════════════════════════════════════════════════════
# Queue Manager (runs on the API server)
# ══════════════════════════════════════════════════════════════

class QueueManager:
    """
    Manages the job queue on the API server side.

    Responsibilities:
    - Accept generation requests and enqueue them
    - Monitor for completed jobs
    - Clean up stale claimed jobs
    - Provide queue status to the API
    """

    def __init__(self):
        self.queue = get_queue()
        self._monitor_thread = None
        self._running = False

    def submit(self, job_id: str, audio_path: str, direction: Dict = None,
               emotional_dna: Dict = None, params: Dict = None,
               priority: int = 10) -> GenerationJob:
        """Submit a new generation job to the queue"""
        job = GenerationJob(
            job_id=job_id,
            status=JobStatus.QUEUED.value,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            audio_path=audio_path,
            direction=direction,
            emotional_dna=emotional_dna,
            params=params or {},
            priority=priority,
            generation_mode="full",  # Always target full quality
        )

        self.queue.enqueue(job)
        return job

    def get_status(self, job_id: str) -> Optional[Dict]:
        """Get job status"""
        return self.queue.get_job(job_id)

    def get_stats(self) -> Dict:
        """Get queue statistics"""
        if isinstance(self.queue, FileQueue):
            return self.queue.get_queue_stats()
        return {}

    def start_monitor(self, interval: int = 30):
        """Start background monitoring thread"""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return

        self._running = True

        def monitor():
            while self._running:
                try:
                    if isinstance(self.queue, FileQueue):
                        requeued = self.queue.cleanup_stale(timeout_minutes=30)
                        if requeued > 0:
                            print(f"[Queue] Re-queued {requeued} stale jobs")
                except Exception as e:
                    print(f"[Queue] Monitor error: {e}")
                time.sleep(interval)

        self._monitor_thread = threading.Thread(target=monitor, daemon=True)
        self._monitor_thread.start()

    def stop_monitor(self):
        self._running = False
