#!/usr/bin/env python3
"""
Canvas Seed Runner — Bootstrap the Optimization Loop

The Brockmann approach: don't wait for users. Generate your own training data.

This script:
1. Scans audio_demos/ and uploads/ for every audio file
2. For EACH track, runs ALL 9 director styles through the pipeline
3. Quality gate scores every output
4. Logs every result to the optimization loop
5. After each batch, triggers an optimization cycle
6. Repeats forever — each round uses the evolved params from the last

The result: LoopCanvas gets better with every loop, 24/7, with zero human input.
After 50-100 generations, the system converges on optimal params per genre/mood.

Usage:
  # Run one batch (all tracks × all styles):
  python seed_runner.py

  # Run continuously forever (daemon mode):
  python seed_runner.py --continuous

  # Run with specific tracks only:
  python seed_runner.py --tracks "225.mp3,facing the sun.m4a"

  # Run N batches then stop:
  python seed_runner.py --batches 5

Cost: $0 — everything is local SDXL/SVD or free-tier fallback
"""

import os
import sys
import json
import time
import hashlib
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime
from dataclasses import asdict

# Add paths
ENGINE_DIR = Path(__file__).parent.parent
APP_DIR = ENGINE_DIR.parent
ROOT_DIR = APP_DIR.parent
sys.path.insert(0, str(ENGINE_DIR))
sys.path.insert(0, str(ROOT_DIR))

from agents.optimization_loop import OptimizationLoop, CanvasResult


# ══════════════════════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════════════════════

# Where to find audio files
AUDIO_DIRS = [
    APP_DIR / "audio_demos",
    APP_DIR / "audio_demos" / "artists",
    APP_DIR / "uploads",
]

# All director styles to test
DIRECTOR_STYLES = [
    "spike_jonze",
    "hype_williams",
    "dave_meyers",
    "khalil_joseph",
    "wong_kar_wai",
    "the_daniels",
    "observed_moment",
    "golden_hour",
    "midnight_drift",
]

# Style → pipeline style mapping
STYLE_TO_PIPELINE = {
    "spike_jonze": "memory_in_motion",
    "hype_williams": "peak_transmission",
    "dave_meyers": "concrete_heat",
    "khalil_joseph": "analog_memory",
    "wong_kar_wai": "midnight_city",
    "the_daniels": "euphoric_drift",
    "observed_moment": "memory_in_motion",
    "golden_hour": "sunrise_departure",
    "midnight_drift": "neon_calm",
}

# Base params per style (will be overridden by evolved params after first cycle)
BASE_PARAMS = {
    "spike_jonze":      {"grain": 0.18, "saturation": 0.75, "contrast": 0.80, "blur": 1.0, "motion_intensity": 0.3},
    "hype_williams":    {"grain": 0.05, "saturation": 1.10, "contrast": 1.15, "blur": 0.3, "motion_intensity": 0.7},
    "dave_meyers":      {"grain": 0.10, "saturation": 0.90, "contrast": 0.95, "blur": 0.5, "motion_intensity": 0.8},
    "khalil_joseph":    {"grain": 0.25, "saturation": 0.60, "contrast": 0.75, "blur": 1.2, "motion_intensity": 0.25},
    "wong_kar_wai":     {"grain": 0.20, "saturation": 0.85, "contrast": 0.85, "blur": 0.8, "motion_intensity": 0.35},
    "the_daniels":      {"grain": 0.12, "saturation": 0.95, "contrast": 1.00, "blur": 0.4, "motion_intensity": 0.6},
    "observed_moment":  {"grain": 0.18, "saturation": 0.70, "contrast": 0.78, "blur": 1.0, "motion_intensity": 0.2},
    "golden_hour":      {"grain": 0.15, "saturation": 0.80, "contrast": 0.82, "blur": 0.9, "motion_intensity": 0.25},
    "midnight_drift":   {"grain": 0.10, "saturation": 0.65, "contrast": 0.90, "blur": 0.6, "motion_intensity": 0.4},
}

OUTPUT_BASE = APP_DIR / "seed_outputs"


class SeedRunner:
    """
    Generates canvases across all tracks × all styles to bootstrap optimization.

    Think of this as the pre-training phase. After enough runs, the system
    knows which params work best for each emotional profile.
    """

    def __init__(self):
        self.optimizer = OptimizationLoop()
        self.audio_analyzer = None
        self.quality_gate = None
        self.loop_engine = None

        # Stats
        self.total_generated = 0
        self.total_passed = 0
        self.total_failed = 0
        self.batch_number = 0
        self.start_time = time.time()

        # Lazy load heavy modules
        self._init_engines()

        OUTPUT_BASE.mkdir(exist_ok=True)

    def _init_engines(self):
        """Load the analysis and scoring engines"""
        try:
            from audio.audio_analyzer import CanvasAudioAnalyzer
            self.audio_analyzer = CanvasAudioAnalyzer()
            print("[Seed] Audio analyzer loaded")
        except Exception as e:
            print(f"[Seed] Audio analyzer failed: {e}")

        try:
            from quality_gate_wrapper import QualityGateWrapper
            self.quality_gate = QualityGateWrapper()
            print("[Seed] Quality gate loaded")
        except Exception as e:
            print(f"[Seed] Quality gate failed: {e}")

        try:
            from loop.seamless_loop import CanvasLoopEngine
            self.loop_engine = CanvasLoopEngine()
            print("[Seed] Loop engine loaded")
        except Exception as e:
            print(f"[Seed] Loop engine failed: {e}")

    # ──────────────────────────────────────────────────────────
    # Audio Discovery
    # ──────────────────────────────────────────────────────────

    def discover_audio(self, specific_tracks: List[str] = None) -> List[Path]:
        """Find all audio files to process"""
        extensions = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aif", ".aiff"}
        seen = set()
        tracks = []

        for audio_dir in AUDIO_DIRS:
            if not audio_dir.exists():
                continue

            for f in sorted(audio_dir.iterdir()):
                if f.suffix.lower() in extensions and f.is_file():
                    # Deduplicate by filename (ignore upload hash prefix)
                    clean_name = f.stem.split("_", 1)[-1] if "_" in f.stem else f.stem
                    if clean_name in seen:
                        continue
                    seen.add(clean_name)

                    if specific_tracks:
                        if not any(t.lower() in f.name.lower() for t in specific_tracks):
                            continue

                    tracks.append(f)

        return tracks

    # ──────────────────────────────────────────────────────────
    # Core Generation
    # ──────────────────────────────────────────────────────────

    def _ensure_wav(self, audio_path: Path) -> Path:
        """Convert audio to WAV if needed (librosa can't read MP3 on all systems)"""
        if audio_path.suffix.lower() == ".wav":
            return audio_path

        wav_dir = OUTPUT_BASE / "wav_cache"
        wav_dir.mkdir(parents=True, exist_ok=True)
        wav_path = wav_dir / f"{audio_path.stem}.wav"

        if wav_path.exists():
            return wav_path

        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(audio_path), "-ar", "44100", "-ac", "1", str(wav_path)],
                capture_output=True, timeout=30,
            )
            if wav_path.exists() and wav_path.stat().st_size > 1000:
                return wav_path
        except Exception:
            pass

        return audio_path  # Fallback to original

    def _validate_audio(self, audio_path: Path) -> bool:
        """Check that the file is actually audio (not HTML or corrupted)"""
        try:
            with open(audio_path, "rb") as f:
                header = f.read(16)
            # HTML files start with < or have DOCTYPE
            if header[:1] == b"<" or b"DOCTYPE" in header or b"html" in header.lower():
                return False
            # Must be at least 10KB to be real audio
            if audio_path.stat().st_size < 10000:
                return False
            return True
        except Exception:
            return False

    def generate_one(self, audio_path: Path, style: str, params: dict) -> Tuple[bool, float, float, str]:
        """
        Generate a single canvas for one track + one style.

        Returns: (success, quality_score, loop_score, output_dir)
        """
        track_hash = hashlib.md5(f"{audio_path.name}_{style}_{self.batch_number}".encode()).hexdigest()[:8]
        output_dir = OUTPUT_BASE / f"{track_hash}_{style}"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Validate audio file
        if not self._validate_audio(audio_path):
            return False, 0.0, 0.0, str(output_dir)

        # Convert to WAV for reliable librosa loading
        wav_path = self._ensure_wav(audio_path)

        pipeline_script = ROOT_DIR / "loopcanvas_grammy.py"
        if not pipeline_script.exists():
            # Try other locations
            for candidate in [APP_DIR.parent / "loopcanvas_grammy.py", Path("loopcanvas_grammy.py")]:
                if candidate.exists():
                    pipeline_script = candidate
                    break

        if not pipeline_script.exists():
            return False, 0.0, 0.0, str(output_dir)

        # Build command (Grammy script doesn't accept --style; style comes from audio analysis)
        cmd = [
            sys.executable, str(pipeline_script),
            "--audio", str(wav_path),
            "--out", str(output_dir),
            "--fast",  # Use fast mode for seeding (Ken Burns, not full SVD)
        ]

        # Apply params as env vars (including director style hint)
        env = os.environ.copy()
        env["LOOPCANVAS_MODE"] = "fast"
        env["LOOPCANVAS_DIRECTOR_STYLE"] = style
        env["LOOPCANVAS_PIPELINE_STYLE"] = STYLE_TO_PIPELINE.get(style, "memory_in_motion")
        env["LOOPCANVAS_GRAIN"] = str(params.get("grain", 0.18))
        env["LOOPCANVAS_SATURATION"] = str(params.get("saturation", 0.75))
        env["LOOPCANVAS_CONTRAST"] = str(params.get("contrast", 0.80))
        env["LOOPCANVAS_BLUR"] = str(params.get("blur", 1.0))
        env["LOOPCANVAS_MOTION_INTENSITY"] = str(params.get("motion_intensity", 0.4))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(pipeline_script.parent),
                env=env,
                timeout=600,  # 10 minute timeout (Grammy fast mode needs ~5-7 min on MPS)
            )

            # Check for output files regardless of exit code
            # (Grammy pipeline may crash in its own scoring step after generating video)
            canvas_file = output_dir / "spotify_canvas_7s_9x16.mp4"
            if not canvas_file.exists():
                canvas_file = output_dir / "spotify_canvas_web.mp4"

            if canvas_file.exists() and canvas_file.stat().st_size > 10000:
                # Canvas was generated — score it with our quality gate
                quality_score = self._score_quality(output_dir)
                loop_score = self._score_loop(output_dir)
                return True, quality_score, loop_score, str(output_dir)

            if result.returncode != 0:
                stderr_tail = (result.stderr or "")[-200:]
                if stderr_tail:
                    print(f"    stderr: {stderr_tail.strip()}")
                return False, 0.0, 0.0, str(output_dir)

            # Fallback: pipeline succeeded but no canvas file found
            return False, 0.0, 0.0, str(output_dir)

        except subprocess.TimeoutExpired:
            return False, 0.0, 0.0, str(output_dir)
        except Exception as e:
            print(f"    Error: {e}")
            return False, 0.0, 0.0, str(output_dir)

    def _score_quality(self, output_dir: Path) -> float:
        """Run quality gate on output"""
        if not self.quality_gate:
            return 0.0

        canvas = output_dir / "spotify_canvas_7s_9x16.mp4"
        if not canvas.exists():
            canvas = output_dir / "spotify_canvas_web.mp4"
        if not canvas.exists():
            return 0.0

        try:
            result = self.quality_gate.evaluate(str(canvas))
            return result.get("overall_score", 0.0)
        except Exception:
            return 0.0

    def _score_loop(self, output_dir: Path) -> float:
        """Run loop check on output"""
        if not self.loop_engine:
            return 0.0

        canvas = output_dir / "spotify_canvas_7s_9x16.mp4"
        if not canvas.exists():
            return 0.0

        try:
            analysis = self.loop_engine.analyze_loop(str(canvas))
            return analysis.seamlessness_score
        except Exception:
            return 0.0

    def _get_params_for_style(self, style: str) -> dict:
        """Get params — uses evolved params if available, otherwise base"""
        # Check for evolved params from previous optimization runs
        evolved_config = ENGINE_DIR / "optimization_data" / "evolved_config.json"
        if evolved_config.exists():
            try:
                with open(evolved_config) as f:
                    config = json.load(f)
                evolved = config.get("evolved_params", {}).get(style)
                if evolved:
                    return evolved
            except (json.JSONDecodeError, KeyError):
                pass

        return BASE_PARAMS.get(style, BASE_PARAMS["observed_moment"]).copy()

    def _analyze_audio(self, audio_path: Path) -> dict:
        """Extract emotional DNA from a track"""
        if not self.audio_analyzer:
            return {}

        try:
            result = self.audio_analyzer.analyze(str(audio_path))
            dna = result.emotional_dna
            return {
                "bpm": dna.bpm,
                "key": dna.key,
                "valence": dna.valence,
                "arousal": dna.arousal,
                "warmth": dna.warmth,
                "genre_predictions": dna.genre_predictions,
            }
        except Exception:
            return {}

    # ──────────────────────────────────────────────────────────
    # Batch Execution
    # ──────────────────────────────────────────────────────────

    def run_batch(self, tracks: List[Path], styles: List[str] = None):
        """
        Run one full batch: every track × every style.

        After the batch, trigger the optimization loop.
        """
        if styles is None:
            styles = DIRECTOR_STYLES

        self.batch_number += 1
        total_combos = len(tracks) * len(styles)
        combo_num = 0

        print(f"\n{'='*60}")
        print(f"SEED BATCH #{self.batch_number}")
        print(f"  Tracks: {len(tracks)}")
        print(f"  Styles: {len(styles)}")
        print(f"  Total generations: {total_combos}")
        print(f"{'='*60}\n")

        batch_results = []

        for track in tracks:
            track_name = track.stem.split("_", 1)[-1] if "_" in track.stem else track.stem
            print(f"\n--- Track: {track_name} ---")

            # Analyze audio once per track
            emotional_dna = self._analyze_audio(track)
            if emotional_dna:
                v = emotional_dna.get('valence', 0)
                print(f"  BPM={emotional_dna.get('bpm', '?')} Key={emotional_dna.get('key', '?')} "
                      f"Valence={v:.2f}" if isinstance(v, (int, float)) else f"  Audio analyzed")

            for style in styles:
                combo_num += 1
                try:
                    params = self._get_params_for_style(style)

                    print(f"  [{combo_num}/{total_combos}] {style}... ", end="", flush=True)

                    start = time.time()
                    success, quality, loop, output_dir = self.generate_one(track, style, params)
                    elapsed = time.time() - start

                    if success:
                        self.total_generated += 1
                        passed = quality >= 9.3
                        if passed:
                            self.total_passed += 1
                        status = f"Q={quality:.1f}/10 L={loop:.2f} ({elapsed:.0f}s)" + (" PASS" if passed else " FAIL")
                        print(status)

                        # Log to optimization loop
                        result = CanvasResult(
                            job_id=f"seed_{self.batch_number}_{combo_num}",
                            timestamp=datetime.now().isoformat(),
                            director_style=style,
                            prompt=f"seed_batch_{self.batch_number}",
                            params=params,
                            quality_score=quality,
                            quality_passed=passed,
                            quality_breakdown={},
                            loop_score=loop,
                            selected_by_artist=False,
                            iterated=False,
                            exported=False,
                            export_platforms=[],
                        )
                        self.optimizer.log_result(result)
                        batch_results.append(result)
                    else:
                        self.total_failed += 1
                        print(f"FAILED ({elapsed:.0f}s)")

                    # Clean up output to save disk space (keep only scores, not video files)
                    self._cleanup_output(Path(output_dir))
                except Exception as e:
                    self.total_failed += 1
                    print(f"CRASH: {e}")

        # After batch: trigger optimization
        print(f"\n{'='*60}")
        print(f"BATCH #{self.batch_number} COMPLETE")
        print(f"  Generated: {len(batch_results)}")
        print(f"  Passed quality gate: {sum(1 for r in batch_results if r.quality_passed)}")
        print(f"  Avg quality: {sum(r.quality_score for r in batch_results) / len(batch_results):.2f}" if batch_results else "  No results")
        print(f"\nRunning optimization loop...")
        print(f"{'='*60}")

        self.optimizer.run()

        # Print what changed
        self._print_evolution_summary()

    def _cleanup_output(self, output_dir: Path):
        """Remove large video files to save disk, keep metadata"""
        if not output_dir.exists():
            return

        for f in output_dir.iterdir():
            if f.suffix in {".mp4", ".avi", ".mov", ".mkv"}:
                try:
                    f.unlink()
                except OSError:
                    pass

    def _print_evolution_summary(self):
        """Show what the optimization loop changed"""
        evolved_config = ENGINE_DIR / "optimization_data" / "evolved_config.json"
        if not evolved_config.exists():
            return

        try:
            with open(evolved_config) as f:
                config = json.load(f)

            evolved_params = config.get("evolved_params", {})
            if evolved_params:
                print("\n  Evolved params (what changed):")
                for style, params in evolved_params.items():
                    base = BASE_PARAMS.get(style, {})
                    changes = []
                    for key, val in params.items():
                        base_val = base.get(key)
                        if base_val is not None and abs(val - base_val) > 0.01:
                            direction = "+" if val > base_val else ""
                            changes.append(f"{key}:{direction}{val - base_val:.2f}")
                    if changes:
                        print(f"    {style}: {', '.join(changes)}")

            negative_prompts = config.get("evolved_negative_prompts", [])
            if negative_prompts:
                print(f"\n  Learned to avoid: {', '.join(negative_prompts[:5])}")

        except Exception:
            pass

    # ──────────────────────────────────────────────────────────
    # Continuous Mode
    # ──────────────────────────────────────────────────────────

    def run_continuous(self, max_batches: int = 0, specific_tracks: List[str] = None):
        """
        Run batches continuously until stopped or max_batches reached.

        Each batch:
        1. Discovers all audio
        2. Generates all combos with current evolved params
        3. Runs optimization
        4. Next batch uses the new evolved params

        This is the "agents optimizing forever" loop.
        """
        tracks = self.discover_audio(specific_tracks)
        if not tracks:
            print("No audio files found!")
            return

        print(f"\n{'#'*60}")
        print(f"# CANVAS SEED RUNNER — CONTINUOUS MODE")
        print(f"# Tracks: {len(tracks)}")
        print(f"# Styles: {len(DIRECTOR_STYLES)}")
        print(f"# Combos per batch: {len(tracks) * len(DIRECTOR_STYLES)}")
        print(f"# Max batches: {'unlimited' if max_batches == 0 else max_batches}")
        print(f"{'#'*60}")

        while True:
            try:
                self.run_batch(tracks, DIRECTOR_STYLES)
            except Exception as e:
                import traceback
                print(f"\n[Seed Runner] Batch {self.batch_number} crashed: {e}")
                traceback.print_exc()
                print("[Seed Runner] Continuing to next batch in 10s...")

            if max_batches > 0 and self.batch_number >= max_batches:
                break

            # Brief pause between batches
            print(f"\nBatch {self.batch_number} done. Starting next batch in 10s...")
            print(f"  (Total: {self.total_generated} generated, {self.total_passed} passed, "
                  f"{self.total_failed} failed)")
            time.sleep(10)

        self._print_final_report()

    def _print_final_report(self):
        """Print final optimization report"""
        elapsed = time.time() - self.start_time
        elapsed_min = elapsed / 60

        print(f"\n{'#'*60}")
        print(f"# SEED RUNNER — FINAL REPORT")
        print(f"{'#'*60}")
        print(f"  Batches completed: {self.batch_number}")
        print(f"  Total generated:   {self.total_generated}")
        print(f"  Quality passed:    {self.total_passed}")
        print(f"  Failed:            {self.total_failed}")
        if self.total_generated > 0:
            print(f"  Pass rate:         {self.total_passed / self.total_generated * 100:.1f}%")
        print(f"  Runtime:           {elapsed_min:.1f} minutes")
        print(f"  Evolved config:    {ENGINE_DIR / 'optimization_data' / 'evolved_config.json'}")
        print(f"  Results log:       {ENGINE_DIR / 'optimization_data' / 'canvas_results.jsonl'}")
        print(f"{'#'*60}")


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Canvas Seed Runner — Bootstrap the optimization loop")
    parser.add_argument("--continuous", action="store_true", help="Run continuously (daemon mode)")
    parser.add_argument("--batches", type=int, default=1, help="Number of batches to run (0=unlimited)")
    parser.add_argument("--tracks", type=str, help="Comma-separated track names to use (default: all)")
    parser.add_argument("--styles", type=str, help="Comma-separated styles (default: all 9)")

    args = parser.parse_args()

    specific_tracks = args.tracks.split(",") if args.tracks else None
    specific_styles = args.styles.split(",") if args.styles else None

    runner = SeedRunner()

    if args.continuous:
        runner.run_continuous(max_batches=0, specific_tracks=specific_tracks)
    elif args.batches > 1 or args.batches == 0:
        runner.run_continuous(max_batches=args.batches, specific_tracks=specific_tracks)
    else:
        tracks = runner.discover_audio(specific_tracks)
        if tracks:
            styles = specific_styles or DIRECTOR_STYLES
            runner.run_batch(tracks, styles)
            runner._print_final_report()
        else:
            print("No audio files found!")
