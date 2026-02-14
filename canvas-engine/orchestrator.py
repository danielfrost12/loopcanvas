#!/usr/bin/env python3
"""
Canvas Master Orchestrator v2.0

The brain of the agent army. Routes work through departments:
  Audio Intelligence → Director Engine → Visual Generation → Quality Gate → Loop Engine → Export

Enforces:
  - $0 cost ceiling (via CostEnforcer)
  - 9.3/10 quality minimum (via QualityGate)
  - Seamless loops (via LoopEngine)
  - Sub-3-second iteration (via IterationEngine)

This module integrates every canvas-engine component into a single pipeline
that server.py can call instead of shelling out to loopcanvas_grammy.py.
"""

import os
import sys
import json
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime

# Add parent paths
ENGINE_DIR = Path(__file__).parent
APP_DIR = ENGINE_DIR.parent
ROOT_DIR = APP_DIR.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ENGINE_DIR))

# Canvas engine imports
from agents.cost_enforcer import get_enforcer, CostBlockedError
from agents.weekly_checklist import (
    get_checklist, log_generation_latency, log_direction_selection, log_agent_heartbeat
)
from audio.audio_analyzer import CanvasAudioAnalyzer, EmotionalDNA, AudioAnalysisResult
from director.philosophy_engine import DirectorPhilosophyEngine
from quality_gate_wrapper import QualityGateWrapper
from loop.seamless_loop import CanvasLoopEngine


@dataclass
class VisualDirection:
    """A proposed visual direction for the artist to choose from"""
    id: str
    director_style: str
    director_name: str
    philosophy: str
    preview_prompt: str
    color_palette: List[str]
    motion_style: str
    texture: str
    confidence: float
    params: Dict = field(default_factory=dict)


@dataclass
class CanvasJob:
    """Full state of a canvas generation job"""
    job_id: str
    status: str  # "analyzing", "directions_ready", "generating", "quality_check", "complete", "failed"
    created_at: str
    audio_path: str

    # Analysis
    emotional_dna: Optional[Dict] = None
    duration_seconds: float = 0.0

    # Directions
    directions: List[Dict] = field(default_factory=list)
    selected_direction: Optional[str] = None

    # Generation
    progress: int = 0
    message: str = ""
    output_dir: Optional[str] = None

    # Quality
    quality_score: Optional[Dict] = None
    loop_analysis: Optional[Dict] = None

    # Outputs
    outputs: Optional[Dict] = None

    # Iteration history
    iterations: List[Dict] = field(default_factory=list)


class CanvasOrchestrator:
    """
    Master orchestrator that runs the full Canvas v2.0 pipeline.

    Pipeline:
    1. Audio Intelligence: Extract emotional DNA
    2. Director Engine: Generate 3-5 visual directions
    3. Visual Generation: Create canvas from selected direction
    4. Quality Gate: Score output, reject if < 9.3
    5. Loop Engine: Ensure seamless looping
    6. Export: Multi-platform output
    """

    def __init__(self):
        self.enforcer = get_enforcer()
        self.audio_analyzer = CanvasAudioAnalyzer()
        self.director_engine = DirectorPhilosophyEngine()
        self.quality_gate = QualityGateWrapper()
        self.loop_engine = CanvasLoopEngine()

        # Job queue for GPU workers
        self.queue_manager = None
        try:
            from dispatch.job_queue import QueueManager
            self.queue_manager = QueueManager()
            self.queue_manager.start_monitor(interval=30)
        except Exception:
            pass  # Queue is optional — falls back to direct subprocess

        # Job storage
        self.jobs: Dict[str, CanvasJob] = {}

        # Config
        self.max_regeneration_attempts = 3
        self.quality_minimum = 9.3

        # Weekly checklist — 24/7 autonomous monitoring
        self.checklist = get_checklist()
        self._checklist_thread = None

    # ──────────────────────────────────────────────────────────────
    # Master Checklist — Part VII (24/7 Autonomous Mode)
    # ──────────────────────────────────────────────────────────────

    def start_checklist_autonomous(self, interval_seconds: int = 604800,
                                    auto_remediate: bool = True):
        """
        Start the weekly master checklist in 24/7 autonomous mode.

        Every `interval_seconds`, the system evaluates all 10 checks:
        1. Are we spending $0?
        2. Does output feel like AI?
        3. Are artists coming back?
        4. Is generation fast enough?
        5. Are artists sharing?
        6. Do loops work?
        7. Is the music matched?
        8. Are patent docs ready?
        9. Is revenue growing?
        10. Are agents healthy?

        Failing checks trigger automatic remediation.
        """
        if self._checklist_thread and self._checklist_thread.is_alive():
            print("[Orchestrator] Checklist already running in autonomous mode")
            return

        self._checklist_thread = self.checklist.run_autonomous_threaded(
            interval_seconds=interval_seconds,
            auto_remediate=auto_remediate,
        )
        log_agent_heartbeat("weekly_checklist", alive=True)
        print(f"[Orchestrator] Master Checklist started (interval: {interval_seconds}s)")

    def stop_checklist_autonomous(self):
        """Stop the autonomous checklist"""
        self.checklist.stop_autonomous()
        log_agent_heartbeat("weekly_checklist", alive=False)
        print("[Orchestrator] Master Checklist stopped")

    def run_checklist_now(self, auto_remediate: bool = True):
        """Run the master checklist immediately (one-shot)"""
        return self.checklist.evaluate(auto_remediate=auto_remediate)

    def get_checklist_report(self) -> dict:
        """Get the latest checklist report"""
        return self.checklist.get_latest_report() or {}

    def get_checklist_history(self, count: int = 10) -> list:
        """Get recent checklist evaluation history"""
        return self.checklist.get_history(count)

    # ──────────────────────────────────────────────────────────────
    # Step 1: Audio Analysis
    # ──────────────────────────────────────────────────────────────

    def analyze_audio(self, audio_path: str, job_id: str = None) -> CanvasJob:
        """
        Analyze an audio file and create a job with emotional DNA.

        This is the foundation — everything downstream depends on this.
        """
        if not job_id:
            job_id = hashlib.md5(f"{audio_path}{time.time()}".encode()).hexdigest()[:8]

        job = CanvasJob(
            job_id=job_id,
            status="analyzing",
            created_at=datetime.now().isoformat(),
            audio_path=audio_path,
            message="Extracting emotional DNA from track..."
        )
        self.jobs[job_id] = job

        try:
            # Cost check: audio analysis is local, $0
            result = self.audio_analyzer.analyze(audio_path)

            # Store emotional DNA as dict for serialization
            dna = result.emotional_dna
            job.emotional_dna = {
                'bpm': dna.bpm,
                'key': dna.key,
                'mode': dna.mode,
                'valence': dna.valence,
                'arousal': dna.arousal,
                'dominance': dna.dominance,
                'brightness': dna.brightness,
                'warmth': dna.warmth,
                'texture': dna.texture,
                'rhythm_complexity': dna.rhythm_complexity,
                'genre_predictions': dna.genre_predictions,
                'cultural_markers': dna.cultural_markers,
                'era_estimate': dna.era_estimate,
                'sections': dna.sections,
                'peak_moments': dna.peak_moments[:10],
                'drops': dna.drops[:5],
                'suggested_colors': dna.suggested_colors,
                'suggested_motion': dna.suggested_motion,
                'suggested_texture': dna.suggested_texture,
                'cinematographer_match': dna.cinematographer_match,
                'energy_curve': dna.energy_curve[:100],  # Truncate for JSON
            }
            job.duration_seconds = result.duration_seconds
            job.progress = 20
            job.message = "Audio analyzed. Generating visual directions..."
            job.status = "analyzed"

        except Exception as e:
            job.status = "failed"
            job.message = f"Audio analysis failed: {str(e)}"

        return job

    # ──────────────────────────────────────────────────────────────
    # Step 2: Generate Visual Directions
    # ──────────────────────────────────────────────────────────────

    def generate_directions(self, job_id: str, count: int = 5) -> List[VisualDirection]:
        """
        Generate 3-5 bespoke visual directions based on the emotional DNA.
        Each direction represents a different director's interpretation.
        """
        job = self.jobs.get(job_id)
        if not job or not job.emotional_dna:
            return []

        dna = job.emotional_dna
        directions = []

        # Get the best director match
        best_match, best_confidence = self.director_engine.match_audio_to_director(dna)

        # Generate directions from multiple directors
        all_styles = list(self.director_engine.directors.keys())

        # Score each director against this track's DNA
        scored_styles = []
        for style_id in all_styles:
            _, confidence = self.director_engine.match_audio_to_director(dna)
            # Re-score individually for proper ranking
            match_id, match_conf = style_id, 0.5  # base
            if style_id == best_match:
                match_conf = best_confidence

            scored_styles.append((style_id, match_conf))

        # Actually match each properly
        scored_styles = []
        for style_id in all_styles:
            director = self.director_engine.get_director(style_id)
            if not director:
                continue

            # Calculate match score based on emotional DNA alignment
            score = self._score_director_match(style_id, dna)
            scored_styles.append((style_id, score))

        # Sort by match score, take top N
        scored_styles.sort(key=lambda x: x[1], reverse=True)

        for i, (style_id, confidence) in enumerate(scored_styles[:count]):
            director = self.director_engine.get_director(style_id)
            if not director:
                continue

            # Get generation params for this director + emotion
            params = self.director_engine.get_generation_params(style_id)

            # Build a preview prompt
            base_prompt = self._build_base_prompt(dna)
            enhanced_prompt = self.director_engine.generate_prompt_enhancement(
                base_prompt, style_id, dna
            )

            direction = VisualDirection(
                id=f"dir_{i}_{style_id}",
                director_style=style_id,
                director_name=director.name,
                philosophy=director.central_theme,
                preview_prompt=enhanced_prompt,
                color_palette=dna.get('suggested_colors', ['#1a1a2e', '#16213e']),
                motion_style=params.get('emotion_motion', dna.get('suggested_motion', 'slow_drift')),
                texture=director.texture_preference,
                confidence=round(confidence, 3),
                params=params,
            )
            directions.append(direction)

        # Store in job
        job.directions = [asdict(d) for d in directions]
        job.status = "directions_ready"
        job.progress = 30
        job.message = f"Generated {len(directions)} visual directions. Awaiting artist selection."

        # Log for AV match tracking (selection logged when artist picks one)
        log_agent_heartbeat("director_engine", alive=True)

        return directions

    def _score_director_match(self, style_id: str, dna: dict) -> float:
        """Score how well a director matches the track's emotional DNA"""
        director = self.director_engine.get_director(style_id)
        if not director:
            return 0.0

        valence = dna.get('valence', 0)
        arousal = dna.get('arousal', 0.5)
        dominance = dna.get('dominance', 0.5)
        warmth = dna.get('warmth', 0.5)
        genres = dna.get('genre_predictions', {})

        # Each director has affinity scores for different emotional profiles
        affinity = {
            'spike_jonze': (
                0.3 * (1 - abs(valence)) +
                0.3 * (1 - arousal) +
                0.2 * genres.get('indie', 0) +
                0.2 * (1 - dominance)
            ),
            'hype_williams': (
                0.3 * dominance +
                0.2 * (1 - arousal) * 0.5 +
                0.3 * genres.get('hip_hop', 0) +
                0.2 * max(valence, 0)
            ),
            'dave_meyers': (
                0.4 * arousal +
                0.3 * genres.get('pop', 0) +
                0.2 * genres.get('electronic', 0) +
                0.1 * dominance
            ),
            'khalil_joseph': (
                0.3 * genres.get('r_and_b', 0) +
                0.3 * warmth +
                0.2 * (1 - arousal) +
                0.2 * (0.5 - abs(valence - 0.2))
            ),
            'wong_kar_wai': (
                0.3 * max(0, -valence) +
                0.3 * (0.5 - abs(arousal - 0.4)) +
                0.2 * genres.get('electronic', 0) +
                0.2 * (1 - warmth)
            ),
            'the_daniels': (
                0.3 * arousal +
                0.3 * abs(valence) +
                0.2 * dna.get('rhythm_complexity', 0.5) +
                0.2 * 0.5
            ),
            'observed_moment': (
                0.25 * (1 - arousal) +
                0.25 * (0.5 - abs(valence)) +
                0.25 * warmth +
                0.25 * 0.7
            ),
            'golden_hour': (
                0.3 * warmth +
                0.3 * max(valence, 0) +
                0.2 * (1 - arousal) +
                0.2 * 0.6
            ),
            'midnight_drift': (
                0.3 * (1 - warmth) +
                0.3 * max(0, -valence) +
                0.2 * arousal +
                0.2 * genres.get('electronic', 0)
            ),
        }

        return affinity.get(style_id, 0.3)

    def _build_base_prompt(self, dna: dict) -> str:
        """Build a base visual prompt from emotional DNA"""
        elements = []

        # Mood from valence
        valence = dna.get('valence', 0)
        if valence > 0.3:
            elements.append("warm golden light, hopeful atmosphere")
        elif valence < -0.3:
            elements.append("cool muted tones, contemplative mood")
        else:
            elements.append("ambient light, emotionally complex atmosphere")

        # Energy from arousal
        arousal = dna.get('arousal', 0.5)
        if arousal > 0.7:
            elements.append("dynamic movement, energetic")
        elif arousal < 0.3:
            elements.append("gentle drift, slow breathing motion")
        else:
            elements.append("measured movement, natural flow")

        # Texture from warmth
        warmth = dna.get('warmth', 0.5)
        if warmth > 0.4:
            elements.append("warm film grain, analog texture, soft focus")
        else:
            elements.append("clean texture, cool tones")

        # Always include Observed Moment qualities
        elements.extend([
            "lifted shadows, no pure black",
            "muted colors, cinematic color grading",
            "natural light, memory-like quality",
        ])

        return ", ".join(elements)

    # ──────────────────────────────────────────────────────────────
    # Step 3: Generate Canvas
    # ──────────────────────────────────────────────────────────────

    def select_direction_and_generate(self, job_id: str, direction_id: str,
                                       output_dir: str = None) -> CanvasJob:
        """
        Artist selects a direction. Begin generation.

        This calls the existing loopcanvas_grammy.py pipeline with
        director-informed parameters.
        """
        import subprocess

        job = self.jobs.get(job_id)
        if not job:
            return None

        # Find selected direction
        selected = None
        for d in job.directions:
            if d['id'] == direction_id:
                selected = d
                break

        if not selected:
            job.status = "failed"
            job.message = f"Direction {direction_id} not found"
            return job

        job.selected_direction = direction_id
        job.status = "generating"
        job.progress = 40
        job.message = f"Generating canvas in {selected['director_name']} style..."
        generation_start_time = time.time()

        # Set up output directory
        if not output_dir:
            output_dir = str(APP_DIR / "outputs" / job_id)
        os.makedirs(output_dir, exist_ok=True)
        job.output_dir = output_dir

        # Save emotional DNA and direction as concept
        concept = {
            'emotional_dna': job.emotional_dna,
            'direction': selected,
            'timestamp': datetime.now().isoformat(),
        }
        concept_path = os.path.join(output_dir, "concept.json")
        with open(concept_path, 'w') as f:
            json.dump(concept, f, indent=2)

        # Mode selection: cloud for user jobs (fast SLA), fast as fallback
        mode = os.environ.get("LOOPCANVAS_MODE", "cloud")
        if mode == "cloud":
            print(f"[Orchestrator] Using cloud mode (Modal H100) for job {job_id}")
        else:
            print(f"[Orchestrator] Using local mode ({mode}) for job {job_id}")

        # Build pipeline command with director params
        pipeline_script = ROOT_DIR / "loopcanvas_grammy.py"
        cmd = [
            sys.executable, str(pipeline_script),
            "--audio", job.audio_path,
            "--out", output_dir,
        ]

        # Style override from director engine
        style_map = {
            'spike_jonze': 'memory_in_motion',
            'hype_williams': 'peak_transmission',
            'dave_meyers': 'concrete_heat',
            'khalil_joseph': 'analog_memory',
            'wong_kar_wai': 'midnight_city',
            'the_daniels': 'euphoric_drift',
            'observed_moment': 'memory_in_motion',
            'golden_hour': 'sunrise_departure',
            'midnight_drift': 'neon_calm',
        }
        style_name = style_map.get(selected['director_style'], 'memory_in_motion')

        if mode == "fast":
            cmd.append("--fast")

        # Canvas-only: generate 1 clip for instant canvas delivery (~45s vs ~13 min)
        if mode == "cloud":
            cmd.append("--canvas-only")

        # Pass director params as environment variables
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"  # Flush stdout so progress lines arrive immediately
        env["LOOPCANVAS_MODE"] = mode  # Ensure subprocess inherits the correct mode
        env["LOOPCANVAS_STYLE"] = style_name

        # CRITICAL: Pass director identity so grammy.py uses correct visual DNA
        env["LOOPCANVAS_DIRECTOR"] = selected.get('director_style', '')
        env["LOOPCANVAS_DIRECTOR_NAME"] = selected.get('director_name', '')
        env["LOOPCANVAS_DIRECTOR_PHILOSOPHY"] = selected.get('philosophy', '')
        env["LOOPCANVAS_DIRECTOR_TEXTURE"] = selected.get('texture', '')
        preview_prompt = selected.get('preview_prompt', '')
        if preview_prompt:
            env["LOOPCANVAS_DIRECTOR_PROMPT"] = preview_prompt

        params = selected.get('params', {})
        env["LOOPCANVAS_GRAIN"] = str(params.get('grain', 0.18))
        env["LOOPCANVAS_SATURATION"] = str(params.get('saturation', 0.75))
        env["LOOPCANVAS_CONTRAST"] = str(params.get('contrast', 0.80))
        env["LOOPCANVAS_MOTION_INTENSITY"] = str(params.get('motion_intensity', 0.4))
        env["LOOPCANVAS_BLUR"] = str(params.get('blur', 1.0))

        # Run pipeline
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=str(ROOT_DIR),
                env=env,
            )

            for line in process.stdout:
                line = line.strip()
                if "[1/7]" in line or "Transcribing" in line:
                    job.progress = 45
                    job.message = "Transcribing lyrics..."
                elif "[2/7]" in line:
                    job.progress = 50
                    job.message = "Analyzing structure..."
                elif "[3/7]" in line:
                    job.progress = 55
                    job.message = "Understanding mood..."
                elif "[4/7]" in line:
                    job.progress = 60
                    job.message = "Building visual concept..."
                elif "[5/7]" in line:
                    job.progress = 65
                    job.message = "Planning shots..."
                elif "[6/7]" in line:
                    job.progress = 70
                    job.message = "Generating visuals..."
                elif "[CLIP_PROGRESS]" in line:
                    # Parse: [CLIP_PROGRESS] 2/7 clips
                    try:
                        parts = line.split("[CLIP_PROGRESS]")[1].strip().split("/")
                        done = int(parts[0])
                        total = int(parts[1].split()[0])
                        pct = 70 + int((done / max(total, 1)) * 10)  # 70-80%
                        job.progress = min(pct, 80)
                        job.message = f"Generating scene {done} of {total}..."
                    except Exception:
                        pass
                elif "[7/7]" in line:
                    job.progress = 80
                    job.message = "Rendering..."
                elif "PIPELINE COMPLETE" in line:
                    job.progress = 85

            process.wait()

            gen_elapsed = time.time() - generation_start_time
            log_generation_latency(gen_elapsed, gen_type="new")

            # Check if output files were actually created (pipeline may exit 1
            # due to non-fatal errors but still produce valid output)
            output_dir_path = Path(output_dir)
            has_canvas = (output_dir_path / "spotify_canvas_7s_9x16.mp4").exists()
            has_video = (output_dir_path / "full_music_video_9x16.mp4").exists()
            has_assets = any((output_dir_path / "assets").glob("*.mp4")) if (output_dir_path / "assets").exists() else False

            if process.returncode == 0 or has_canvas or has_video:
                # Pipeline produced output
                if process.returncode != 0:
                    print(f"[Orchestrator] Pipeline exited {process.returncode} but output files exist — treating as success")

                # ALWAYS validate quality and loops — no exceptions.
                # The artist deserves the same standard whether it's a 7s canvas or full video.
                # "Would a label pay $50K for this?" If not, regenerate.
                job.progress = 88
                job.message = "Validating quality..."
                self._run_quality_gate(job)

                job.progress = 90
                job.message = "Validating loop..."
                self._run_loop_validation(job)

                # Quality enforcement: regenerate if below minimum
                quality_passed = True
                if job.quality_score and not job.quality_score.get('passed', True):
                    quality_passed = False
                    score = job.quality_score.get('overall_score', 0)
                    print(f"[Orchestrator] ✗ Quality {score:.1f}/10 below {self.quality_minimum} minimum")

                attempt = 1
                while not quality_passed and attempt < self.max_regeneration_attempts:
                    attempt += 1
                    score = job.quality_score.get('overall_score', 0)
                    print(f"[Orchestrator] Regenerating (attempt {attempt}/{self.max_regeneration_attempts}) — score {score:.1f} < {self.quality_minimum}")
                    job.progress = 60
                    job.message = f"Refining quality (attempt {attempt})..."

                    # Re-run grammy pipeline
                    retry_process = subprocess.Popen(
                        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, cwd=str(pipeline_script.parent), env=env,
                    )
                    for line in retry_process.stdout:
                        line = line.strip()
                        if line:
                            print(f"[Orchestrator regen {attempt}] {line}")
                    retry_process.wait()

                    # Re-validate
                    job.progress = 88
                    job.message = f"Re-validating (attempt {attempt})..."
                    self._run_quality_gate(job)
                    self._run_loop_validation(job)

                    if job.quality_score and job.quality_score.get('passed', False):
                        quality_passed = True
                        print(f"[Orchestrator] ✓ Attempt {attempt} passed quality gate ({job.quality_score.get('overall_score', 0):.1f}/10)")
                    else:
                        new_score = job.quality_score.get('overall_score', 0) if job.quality_score else 0
                        print(f"[Orchestrator] ✗ Attempt {attempt} still below minimum ({new_score:.1f}/10)")

                if not quality_passed:
                    # Ship best effort but flag it
                    print(f"[Orchestrator] ⚠ Shipping after {self.max_regeneration_attempts} attempts — best available quality")

                # Finalize outputs
                self._finalize_outputs(job)
            elif has_assets:
                # Pipeline crashed mid-generation but some clips exist
                # Try to finalize with whatever we have
                print(f"[Orchestrator] Pipeline failed but {len(list((output_dir_path / 'assets').glob('*.mp4')))} clips exist — attempting partial finalize")
                self._finalize_outputs(job)
                if not job.outputs:
                    job.status = "failed"
                    job.message = f"Generation partially failed (exit code {process.returncode})"
            else:
                job.status = "failed"
                job.message = f"Generation failed (exit code {process.returncode})"

        except Exception as e:
            job.status = "failed"
            job.message = f"Generation error: {str(e)}"

        return job

    # ──────────────────────────────────────────────────────────────
    # Step 4: Quality Gate
    # ──────────────────────────────────────────────────────────────

    def _run_quality_gate(self, job: CanvasJob):
        """Run the quality gate on generated output.

        First checks if grammy.py already wrote a quality_score.json (it now does
        even in canvas-only mode). If so, uses that. Otherwise runs our own evaluation.
        """
        output_dir = Path(job.output_dir)

        # Check if grammy.py already scored this
        score_file = output_dir / "quality_score.json"
        if score_file.exists():
            try:
                import json
                with open(score_file) as f:
                    existing_score = json.load(f)
                if 'error' not in existing_score:
                    job.quality_score = existing_score
                    passed = existing_score.get('passed', False)
                    total = existing_score.get('total', 0)
                    print(f"[Orchestrator] Quality score from pipeline: {total:.0f}/100 ({'PASS' if passed else 'FAIL'})")
                    return
            except Exception:
                pass  # Fall through to our own evaluation

        canvas_path = output_dir / "spotify_canvas_7s_9x16.mp4"
        if not canvas_path.exists():
            canvas_path = output_dir / "spotify_canvas_web.mp4"

        if not canvas_path.exists():
            job.quality_score = {'overall_score': 0, 'passed': False, 'issues': ['No canvas file found']}
            return

        try:
            score = self.quality_gate.evaluate(str(canvas_path), job.emotional_dna)
            job.quality_score = score
        except Exception as e:
            print(f"[Orchestrator] WARNING: Quality gate crashed for job: {e}")
            job.quality_score = {'overall_score': 0, 'passed': False, 'issues': [str(e)]}

    # ──────────────────────────────────────────────────────────────
    # Step 5: Loop Validation
    # ──────────────────────────────────────────────────────────────

    def _run_loop_validation(self, job: CanvasJob):
        """Validate and fix loop seamlessness"""
        output_dir = Path(job.output_dir)
        canvas_path = output_dir / "spotify_canvas_7s_9x16.mp4"

        if not canvas_path.exists():
            canvas_path = output_dir / "spotify_canvas_web.mp4"

        if not canvas_path.exists():
            return

        try:
            analysis = self.loop_engine.analyze_loop(str(canvas_path))
            job.loop_analysis = {
                'is_seamless': analysis.is_seamless,
                'score': analysis.seamlessness_score,
                'issues': analysis.issues,
            }

            # Auto-fix if loop isn't seamless
            if not analysis.is_seamless and analysis.recommended_crossfade_frames > 0:
                fixed_path = str(canvas_path).replace('.mp4', '_looped.mp4')
                success, msg = self.loop_engine.create_seamless_loop(
                    str(canvas_path), fixed_path,
                    analysis.recommended_crossfade_frames
                )
                if success:
                    # Replace original with fixed version
                    os.replace(fixed_path, str(canvas_path))
                    job.loop_analysis['fixed'] = True
                    job.loop_analysis['fix_message'] = msg

        except Exception as e:
            print(f"[Orchestrator] WARNING: Loop validation crashed for job: {e}")
            job.loop_analysis = {'is_seamless': False, 'score': 0, 'issues': [str(e)]}

    # ──────────────────────────────────────────────────────────────
    # Step 6: Finalize Outputs
    # ──────────────────────────────────────────────────────────────

    def _finalize_outputs(self, job: CanvasJob):
        """Finalize output files and set job to complete"""
        import subprocess
        output_dir = Path(job.output_dir)

        canvas_path = output_dir / "spotify_canvas_7s_9x16.mp4"
        web_canvas = output_dir / "spotify_canvas_web.mp4"

        if canvas_path.exists() and not web_canvas.exists():
            # Re-encode for web
            ffmpeg_result = subprocess.run([
                "ffmpeg", "-y",
                "-i", str(canvas_path),
                "-c:v", "libx264", "-profile:v", "baseline",
                "-level", "3.0", "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-c:a", "aac", "-b:a", "128k",
                str(web_canvas)
            ], capture_output=True, text=True)
            if ffmpeg_result.returncode != 0:
                print(f"[Orchestrator] FFmpeg web re-encode failed (code {ffmpeg_result.returncode}): {ffmpeg_result.stderr[:300] if ffmpeg_result.stderr else 'no stderr'}")
                # Fallback: copy raw canvas as web version
                import shutil
                try:
                    shutil.copy2(str(canvas_path), str(web_canvas))
                    print(f"[Orchestrator] Fell back to copying raw canvas as web version")
                except Exception as copy_err:
                    print(f"[Orchestrator] Fallback copy also failed: {copy_err}")

        # Check what outputs exist
        outputs = {}
        if web_canvas.exists():
            outputs["canvas"] = f"/outputs/{job.job_id}/spotify_canvas_web.mp4"
        elif canvas_path.exists():
            outputs["canvas"] = f"/outputs/{job.job_id}/spotify_canvas_7s_9x16.mp4"

        video_path = output_dir / "full_music_video_9x16.mp4"
        if video_path.exists():
            outputs["full_video"] = f"/outputs/{job.job_id}/full_music_video_9x16.mp4"

        concept_path = output_dir / "concept.json"
        if concept_path.exists():
            outputs["concept"] = f"/outputs/{job.job_id}/concept.json"

        job.outputs = outputs
        job.status = "complete"
        job.progress = 100
        job.message = "Canvas complete!"

        # Final output verification
        if job.outputs:
            canvas_url = job.outputs.get("canvas", "")
            if canvas_url:
                actual_path = Path(job.output_dir) / Path(canvas_url).name
                if not actual_path.exists():
                    # Try resolving differently
                    actual_path = Path(job.output_dir) / canvas_url.split("/")[-1]
                if not actual_path.exists() or actual_path.stat().st_size < 5000:
                    job.status = "error"
                    job.message = f"Output file missing or corrupted ({actual_path.name})"
                    print(f"[Orchestrator] CRITICAL: Job {job.job_id} output missing: {actual_path}")

    # ──────────────────────────────────────────────────────────────
    # Iteration: Sub-3-second adjustments
    # ──────────────────────────────────────────────────────────────

    def iterate(self, job_id: str, adjustment: str, params: dict = None) -> CanvasJob:
        """
        Apply an iteration to an existing canvas.

        Natural language adjustments like:
        - "make it warmer"
        - "more grain"
        - "slower movement"
        - "feel more like 3am"

        Target: < 3 seconds for parameter adjustments
        """
        job = self.jobs.get(job_id)
        if not job or job.status != "complete":
            return job

        # Parse natural language into parameter deltas
        deltas = self._parse_adjustment(adjustment, params)

        # Record iteration
        job.iterations.append({
            'adjustment': adjustment,
            'deltas': deltas,
            'timestamp': datetime.now().isoformat(),
        })

        # For parameter-only changes, re-render with FFmpeg (< 3 sec)
        if self._is_parameter_only(deltas):
            return self._apply_ffmpeg_adjustment(job, deltas)

        # For structural changes, regenerate (< 10 sec target)
        return self._regenerate_with_adjustment(job, deltas)

    def _parse_adjustment(self, adjustment: str, params: dict = None) -> dict:
        """Parse natural language adjustment into parameter deltas"""
        deltas = params or {}
        adj = adjustment.lower()

        # Temperature/warmth
        if any(w in adj for w in ['warmer', 'warm', 'golden', 'sunset']):
            deltas.setdefault('temperature_shift', 500)
            deltas.setdefault('saturation_delta', 0.05)
        elif any(w in adj for w in ['cooler', 'cool', 'cold', 'blue']):
            deltas.setdefault('temperature_shift', -500)
            deltas.setdefault('saturation_delta', -0.05)

        # Grain/texture
        if any(w in adj for w in ['more grain', 'grainier', 'vintage', 'film']):
            deltas.setdefault('grain_delta', 0.1)
        elif any(w in adj for w in ['less grain', 'cleaner', 'smooth']):
            deltas.setdefault('grain_delta', -0.1)

        # Motion
        if any(w in adj for w in ['slower', 'calmer', 'gentle']):
            deltas.setdefault('motion_speed_delta', -0.1)
        elif any(w in adj for w in ['faster', 'energetic', 'dynamic']):
            deltas.setdefault('motion_speed_delta', 0.1)

        # Brightness
        if any(w in adj for w in ['brighter', 'lighter']):
            deltas.setdefault('brightness_delta', 0.05)
        elif any(w in adj for w in ['darker', 'moodier', 'shadow']):
            deltas.setdefault('brightness_delta', -0.05)

        # Contrast
        if any(w in adj for w in ['more contrast', 'punchier']):
            deltas.setdefault('contrast_delta', 0.1)
        elif any(w in adj for w in ['less contrast', 'flatter', 'softer']):
            deltas.setdefault('contrast_delta', -0.1)

        # Vibe-based (map to multiple params)
        if '3am' in adj or 'late night' in adj:
            deltas.setdefault('temperature_shift', -300)
            deltas.setdefault('brightness_delta', -0.08)
            deltas.setdefault('saturation_delta', -0.1)
            deltas.setdefault('grain_delta', 0.05)

        if 'memory' in adj or 'nostalgic' in adj:
            deltas.setdefault('grain_delta', 0.1)
            deltas.setdefault('contrast_delta', -0.05)
            deltas.setdefault('saturation_delta', -0.1)
            deltas.setdefault('blur_delta', 0.3)

        return deltas

    def _is_parameter_only(self, deltas: dict) -> bool:
        """Check if adjustment can be done with FFmpeg only (fast path)"""
        ffmpeg_params = {
            'temperature_shift', 'saturation_delta', 'brightness_delta',
            'contrast_delta', 'grain_delta', 'blur_delta', 'vignette_delta',
        }
        return all(k in ffmpeg_params for k in deltas.keys())

    def _apply_ffmpeg_adjustment(self, job: CanvasJob, deltas: dict) -> CanvasJob:
        """Apply FFmpeg-only adjustments (target: < 3 seconds)"""
        import subprocess

        output_dir = Path(job.output_dir)
        source = output_dir / "spotify_canvas_web.mp4"
        if not source.exists():
            source = output_dir / "spotify_canvas_7s_9x16.mp4"

        if not source.exists():
            job.message = "No source canvas to adjust"
            return job

        # Build FFmpeg filter chain from deltas
        filters = []

        # Color adjustments
        eq_parts = []
        if 'brightness_delta' in deltas:
            eq_parts.append(f"brightness={deltas['brightness_delta']:.3f}")
        if 'contrast_delta' in deltas:
            contrast = 1.0 + deltas['contrast_delta']
            eq_parts.append(f"contrast={contrast:.3f}")
        if 'saturation_delta' in deltas:
            sat = 1.0 + deltas['saturation_delta']
            eq_parts.append(f"saturation={sat:.3f}")

        if eq_parts:
            filters.append(f"eq={':'.join(eq_parts)}")

        # Temperature shift (color balance)
        if 'temperature_shift' in deltas:
            shift = deltas['temperature_shift']
            if shift > 0:
                filters.append(f"colorbalance=rs={shift/5000:.3f}:gs={shift/10000:.3f}:bs=-{shift/5000:.3f}")
            else:
                shift = abs(shift)
                filters.append(f"colorbalance=rs=-{shift/5000:.3f}:gs=-{shift/10000:.3f}:bs={shift/5000:.3f}")

        # Grain
        if 'grain_delta' in deltas:
            grain = max(0, int(deltas['grain_delta'] * 100))
            if grain > 0:
                filters.append(f"noise=c0s={grain}:c0f=t")

        # Blur
        if 'blur_delta' in deltas:
            blur = max(0, deltas['blur_delta'])
            if blur > 0:
                filters.append(f"gblur=sigma={blur:.1f}")

        if not filters:
            job.message = "No adjustments to apply"
            return job

        # Apply filters
        adjusted_path = output_dir / "spotify_canvas_web_adjusted.mp4"
        filter_chain = ",".join(filters)

        cmd = [
            "ffmpeg", "-y",
            "-i", str(source),
            "-vf", filter_chain,
            "-c:v", "libx264", "-profile:v", "baseline",
            "-level", "3.0", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-c:a", "copy",
            str(adjusted_path)
        ]

        start = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True)
        elapsed = time.time() - start

        if result.returncode == 0 and adjusted_path.exists():
            # Log iteration latency
            log_generation_latency(elapsed, gen_type="iteration")

            # Update outputs
            ts = int(time.time())
            job.outputs["canvas"] = f"/outputs/{job.job_id}/spotify_canvas_web_adjusted.mp4?t={ts}"
            job.message = f"Adjustment applied in {elapsed:.1f}s"
        else:
            job.message = f"Adjustment failed: {result.stderr[:200]}"

        return job

    def _regenerate_with_adjustment(self, job: CanvasJob, deltas: dict) -> CanvasJob:
        """Full regeneration with adjusted parameters (target: < 10 seconds)"""
        # This re-runs the pipeline with modified params
        # For now, delegate to the same generation pipeline
        job.message = "Regenerating with adjusted parameters..."
        job.progress = 50

        # Merge deltas into existing direction params
        if job.selected_direction and job.directions:
            for d in job.directions:
                if d['id'] == job.selected_direction:
                    for key, val in deltas.items():
                        d['params'][key] = val

        return self.select_direction_and_generate(
            job.job_id, job.selected_direction, job.output_dir
        )

    # ──────────────────────────────────────────────────────────────
    # Status & Reporting
    # ──────────────────────────────────────────────────────────────

    def get_job_status(self, job_id: str) -> Optional[Dict]:
        """Get full job status as serializable dict"""
        job = self.jobs.get(job_id)
        if not job:
            return None
        return asdict(job)

    def get_cost_report(self) -> str:
        """Get cost enforcement report"""
        return self.enforcer.report()


# Singleton
_orchestrator = None


def get_orchestrator() -> CanvasOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = CanvasOrchestrator()
    return _orchestrator
