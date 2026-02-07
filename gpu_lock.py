"""
GPU Mutex — Prevents multiple pipeline processes from fighting for the MPS GPU.

Uses a threading.Lock() for in-process coordination and a lockfile (gpu.lock)
for cross-process coordination with the seed runner.

All operations degrade gracefully: if anything fails, default to "unlocked"
so the system never deadlocks.
"""

import os
import json
import threading
from pathlib import Path
from datetime import datetime

_gpu_lock = threading.Lock()
_LOCKFILE = Path(__file__).parent / "gpu.lock"


def acquire_gpu(job_type: str, job_id: str):
    """Acquire the GPU: threading lock + write gpu.lock with job metadata."""
    _gpu_lock.acquire()
    try:
        _LOCKFILE.write_text(json.dumps({
            "pid": os.getpid(),
            "job_type": job_type,
            "job_id": job_id,
            "started_at": datetime.now().isoformat(),
        }))
    except Exception:
        pass  # Lock file write failed — thread lock is still held


def release_gpu():
    """Remove gpu.lock and release threading lock."""
    try:
        _LOCKFILE.unlink(missing_ok=True)
    except Exception:
        pass
    try:
        _gpu_lock.release()
    except RuntimeError:
        pass  # Lock was not held


def is_gpu_busy() -> bool:
    """Check if gpu.lock exists AND the owning PID is still alive."""
    try:
        if not _LOCKFILE.exists():
            return False
        data = json.loads(_LOCKFILE.read_text())
        pid = data.get("pid")
        if pid is None:
            return False
        os.kill(pid, 0)  # Signal 0: check if process exists
        return True
    except ProcessLookupError:
        # PID is dead — stale lock
        try:
            _LOCKFILE.unlink(missing_ok=True)
        except Exception:
            pass
        return False
    except Exception:
        return False  # Degrade gracefully


def get_gpu_status() -> dict:
    """Return GPU lock status for the admin health endpoint."""
    try:
        if not _LOCKFILE.exists():
            return {"locked": False, "locked_by": None, "job_id": None, "duration_seconds": None}
        data = json.loads(_LOCKFILE.read_text())
        started = datetime.fromisoformat(data["started_at"])
        duration = (datetime.now() - started).total_seconds()
        return {
            "locked": True,
            "locked_by": data.get("job_type"),
            "job_id": data.get("job_id"),
            "duration_seconds": round(duration, 1),
        }
    except Exception:
        return {"locked": False, "locked_by": None, "job_id": None, "duration_seconds": None}
