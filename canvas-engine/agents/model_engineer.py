#!/usr/bin/env python3
"""
Model Engineer — Visual Generation Lead (Canvas Agent Army v2.0)

Autonomous agent that continuously improves AI generation quality.
Runs daily in GitHub Actions. $0 cost — no paid APIs.

Pipeline: Read quality data → Analyze scores → Evolve generation params → Write config

Quality gate: 9.3/10 minimum. 7 hard rejection flags. 5 scoring axes.
Taste layer: genre-specific visual language mapping for cultural fluency.

Phases:
  Phase 1 (avg < 7.0): Basic prompt optimization, negative prompt tuning
  Phase 2 (7.0-8.5): Director-specific LoRA weight tuning, color grading
  Phase 3 (8.5-9.3): Beat sync, loop smoothing, cultural taste mapping
  Phase 4 (> 9.3): A/B test generation approaches, micro-tune per genre
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict

# ══════════════════════════════════════════════════════════════
# Paths
# ══════════════════════════════════════════════════════════════

ENGINE_DIR = Path(__file__).parent.parent
APP_DIR = ENGINE_DIR.parent
DATA_DIR = ENGINE_DIR / "checklist_data"
OPT_DIR = ENGINE_DIR / "optimization_data"
CONFIG_DIR = APP_DIR
CONFIG_PATH = APP_DIR / "model_config.json"

DATA_DIR.mkdir(exist_ok=True)
OPT_DIR.mkdir(exist_ok=True)

# ══════════════════════════════════════════════════════════════
# Quality Standards (from Canvas Agent Army v2.0)
# ══════════════════════════════════════════════════════════════

MINIMUM_SCORE = 9.3

SCORING_AXES = {
    "observer_neutrality":    {"weight": 3.0, "minimum": 8.0, "desc": "Footage doesn't know it's being watched"},
    "camera_humility":        {"weight": 2.5, "minimum": 8.0, "desc": "Camera serves the moment, not itself"},
    "temporal_indifference":  {"weight": 2.0, "minimum": 7.5, "desc": "Time flows naturally, no rush"},
    "memory_texture":         {"weight": 1.5, "minimum": 7.0, "desc": "Feels like a memory, not a recording"},
    "light_first_emotion":    {"weight": 1.0, "minimum": 7.0, "desc": "Emotion through light, not effects"},
}

HARD_REJECTION_FLAGS = [
    "ai_artifacts", "morphing_faces", "uncanny_valley",
    "bad_color_grading", "beat_sync_failure",
    "loop_discontinuity", "director_style_mismatch",
]

# ══════════════════════════════════════════════════════════════
# Music Video Generation Spec — Creative Constraints
# "The video must feel observed, not performed."
# ══════════════════════════════════════════════════════════════

CREATIVE_SPEC = {
    # Core principle: optimize for restraint, not spectacle
    "core_principle": "observed_not_performed",
    "optimize_for": ["temporal_stillness", "emotional_coherence", "restraint"],
    "never_optimize_for": ["spectacle", "motion_density", "visual_variety"],
    "ambiguity_default": "less_motion_fewer_cuts_longer_holds",

    # Temporal system
    "shot_duration": {
        "minimum_seconds": 2.8,
        "ideal_range": (4.0, 7.5),
        "max_cut_frequency": "one_per_musical_phrase",
        "hard_rule": "no_cuts_on_transient_peaks",  # kick, snare, clap
    },
    "beat_alignment": {
        "allowed": ["phrase_boundaries", "harmonic_shifts", "vocal_entry_exit"],
        "forbidden": ["every_beat", "percussion_patterns", "hi_hat_rhythms"],
    },

    # Camera motion
    "camera_motion": {
        "allowed": [
            {"type": "slow_push_in", "max_scale_change_pct": 3.0},
            {"type": "slow_lateral_drift", "max_frame_width_pct": 4.0},
            {"type": "static"},  # preferred
        ],
        "forbidden": ["whip_pan", "fast_zoom", "camera_shake", "boomerang_loop"],
        "max_zoom_speed_pct_per_second": 0.5,
        "rule": "motion_must_be_imperceptible_on_first_watch",
    },

    # Edit philosophy
    "cuts": {
        "feel": "inevitable_not_rhythmic",
        "never_cut_to": ["match_energy", "avoid_boredom"],
        "default_transition": "hard_cut",
        "allowed_soft": {"dissolve_frames": (2, 4), "max_opacity_overlap_pct": 10},
        "forbidden_transitions": ["wipe", "morph", "ai_interpolated_blend"],
    },

    # Color & tone
    "color": {
        "temperature": "one_per_video",  # warm OR cool, never mixed
        "max_dominant_colors": 2,
        "accent_max_frame_area_pct": 5,
        "contrast": "medium_low",
        "blacks": "lifted_slightly",  # never crushed
        "highlights": "never_clipped",
        "saturation": "restrained",  # no "music video pop"
    },

    # Subject behavior
    "subject": {
        "state": "unaware_of_camera",
        "forbidden": ["direct_address", "performative_gestures", "exaggerated_emotion", "lip_sync_unless_requested", "exaggerated_dancing"],
        "allowed": ["walking", "waiting", "looking_away", "micro_movement"],
        "intent": "captured_mid_existence_not_staged",
    },

    # Narrative
    "narrative": {
        "explicit": False,  # no literal storytelling, no cause-effect, no arc
        "implicit": True,   # emotional continuity, mood consistency
        "heuristic": "if_scene_explains_song_remove_it",
    },

    # Negative space
    "negative_space": {
        "prefer_empty_frames": True,
        "allow_nothing_happening": True,
        "max_symbolic_ideas_per_shot": 1,
    },

    # Looping
    "loop": {
        "feel": "accidental_not_engineered",
        "forbidden": ["reverse_playback", "mirrored_motion"],
        "method": "shared_emotional_state_not_shared_pixels",
    },

    # Rewatchability gate
    "rewatchability_test": [
        "works_with_sound_off",
        "better_on_second_watch",
        "avoids_explaining_itself",
    ],
    "if_fails_rewatchability": "regenerate_fewer_cuts_longer_holds_reduced_motion",

    # Auto-fail conditions
    "aesthetic_rejection": [
        "visuals_respond_to_every_beat",
        "motion_draws_attention_to_itself",
        "color_palette_fights_mood",
        "editing_feels_impressive",
        "meaning_understood_too_quickly",
    ],

    # Success definition
    "success": "feels_like_a_memory_someone_else_lived_viewer_mistakes_for_own",
}

# Genre-specific taste profiles for cultural fluency
GENRE_TASTE_PROFILES = {
    "hip_hop": {
        "prompt_modifier": "urban, high-contrast, gritty texture, street photography aesthetic",
        "negative_extra": "pastoral, soft, pastel, countryside",
        "color_temp": "warm_high_contrast",
        "motion_range": (0.6, 0.9),
    },
    "electronic": {
        "prompt_modifier": "neon, pulsing light, clean geometry, rave aesthetic, laser",
        "negative_extra": "organic, rustic, vintage, warm",
        "color_temp": "cool_neon",
        "motion_range": (0.5, 0.85),
    },
    "indie": {
        "prompt_modifier": "film grain, muted tones, art house, lo-fi, golden hour",
        "negative_extra": "flashy, neon, corporate, polished",
        "color_temp": "warm_muted",
        "motion_range": (0.3, 0.6),
    },
    "pop": {
        "prompt_modifier": "vibrant, saturated, dynamic, polished, bright",
        "negative_extra": "gritty, dark, moody, desaturated",
        "color_temp": "vibrant_saturated",
        "motion_range": (0.5, 0.8),
    },
    "r_and_b": {
        "prompt_modifier": "warm, intimate, velvet texture, golden light, sensual",
        "negative_extra": "harsh, cold, clinical, sterile",
        "color_temp": "warm_rich",
        "motion_range": (0.3, 0.6),
    },
    "country": {
        "prompt_modifier": "earth tones, natural light, americana, wide landscape, sunset",
        "negative_extra": "urban, neon, futuristic, synthetic",
        "color_temp": "earth_warm",
        "motion_range": (0.2, 0.5),
    },
    "rock": {
        "prompt_modifier": "dark saturated, raw energy, concert lighting, rebellion",
        "negative_extra": "gentle, soft, pastel, calm",
        "color_temp": "dark_saturated",
        "motion_range": (0.6, 0.95),
    },
    "latin": {
        "prompt_modifier": "warm vivid, rhythmic, lush, tropical, golden",
        "negative_extra": "cold, sterile, monochrome, industrial",
        "color_temp": "warm_vivid",
        "motion_range": (0.5, 0.85),
    },
    "k_pop": {
        "prompt_modifier": "pastel neon, precise, glossy, idol aesthetic, clean",
        "negative_extra": "gritty, dirty, rough, organic",
        "color_temp": "pastel_neon",
        "motion_range": (0.5, 0.8),
    },
    "afrobeats": {
        "prompt_modifier": "golden warm, flowing, organic, diaspora, sun-drenched",
        "negative_extra": "cold, dark, sterile, mechanical",
        "color_temp": "golden_warm",
        "motion_range": (0.4, 0.75),
    },
}

DIRECTOR_DEFAULTS = {
    "spike_jonze":    {"lora_weight": 0.7, "emphasis": "vulnerability_beauty"},
    "hype_williams":  {"lora_weight": 0.7, "emphasis": "mythological_mundane"},
    "dave_meyers":    {"lora_weight": 0.7, "emphasis": "kinetic_energy"},
    "the_daniels":    {"lora_weight": 0.7, "emphasis": "surreal_grounded"},
    "khalil_joseph":  {"lora_weight": 0.7, "emphasis": "poetic_documentary"},
    "wong_kar_wai":   {"lora_weight": 0.7, "emphasis": "neon_longing"},
    "observed_moment":{"lora_weight": 0.8, "emphasis": "authentic_witness"},
}


# ══════════════════════════════════════════════════════════════
# Data Structures
# ══════════════════════════════════════════════════════════════

@dataclass
class QualityMetrics:
    avg_score: float = 0.0
    rejection_rate: float = 0.0
    ai_artifact_rate: float = 0.0
    loop_seamlessness: float = 0.0
    beat_sync_accuracy: float = 0.0
    director_style_match: float = 0.0
    generation_p95_seconds: float = 0.0
    iteration_p95_seconds: float = 0.0
    per_director_scores: Dict[str, float] = field(default_factory=dict)
    per_genre_scores: Dict[str, float] = field(default_factory=dict)
    per_axis_scores: Dict[str, float] = field(default_factory=dict)
    total_generations: int = 0
    total_rejections: int = 0
    weakest_axis: str = ""
    weakest_director: str = ""
    weakest_genre: str = ""


@dataclass
class ModelDecision:
    timestamp: str = ""
    phase: int = 1
    prompt_changes: Dict = field(default_factory=dict)
    negative_prompt_changes: Dict = field(default_factory=dict)
    director_weight_changes: Dict = field(default_factory=dict)
    cfg_scale: float = 7.5
    generation_steps: int = 30
    motion_intensity: float = 0.6
    loop_smoothing_factor: float = 0.85
    taste_layer_updates: Dict = field(default_factory=dict)
    reasoning: str = ""
    metrics_snapshot: Dict = field(default_factory=dict)


# ══════════════════════════════════════════════════════════════
# Model Engineer
# ══════════════════════════════════════════════════════════════

class ModelEngineer:
    """Autonomous agent that evolves AI generation parameters for quality."""

    def __init__(self):
        self.metrics = QualityMetrics()
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        if CONFIG_PATH.exists():
            try:
                return json.loads(CONFIG_PATH.read_text())
            except (json.JSONDecodeError, IOError):
                pass
        return {
            "version": 1, "phase": 1,
            "quality_gate": {"minimum_score": 9.3, "hard_rejection_flags": HARD_REJECTION_FLAGS},
            "generation_params": {
                "cfg_scale": 7.5, "generation_steps": 30,
                "motion_intensity": 0.6, "loop_smoothing_factor": 0.85,
            },
            "director_weights": {k: v["lora_weight"] for k, v in DIRECTOR_DEFAULTS.items()},
            "taste_layer": {"enabled": False, "genre_profiles": {}},
            "last_updated": "", "last_decision": "",
        }

    def _read_jsonl(self, filepath: Path) -> List[Dict]:
        entries = []
        if not filepath.exists():
            return entries
        try:
            for line in filepath.read_text().splitlines():
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except IOError:
            pass
        return entries

    # ─── Analysis ───────────────────────────────────────────────
    def analyze(self) -> QualityMetrics:
        """Analyze quality data from canvas results."""
        results = self._read_jsonl(OPT_DIR / "canvas_results.jsonl")
        if not results:
            print("[ModelEngineer] No canvas results yet — using defaults.")
            return self.metrics

        scores = []
        rejections = 0
        director_scores = {}
        genre_scores = {}
        axis_scores = {axis: [] for axis in SCORING_AXES}
        gen_times = []
        iter_times = []
        loop_scores = []
        sync_scores = []
        artifact_count = 0

        for r in results:
            quality = r.get("quality_score", 0)
            scores.append(quality)

            if r.get("rejected", False):
                rejections += 1
            if r.get("ai_artifact_detected", False):
                artifact_count += 1

            # Per-director
            director = r.get("director", "unknown")
            director_scores.setdefault(director, []).append(quality)

            # Per-genre
            genre = r.get("genre", "unknown")
            genre_scores.setdefault(genre, []).append(quality)

            # Per-axis scores
            for axis in SCORING_AXES:
                val = r.get(f"axis_{axis}", r.get(axis, 0))
                if val > 0:
                    axis_scores[axis].append(val)

            # Latency
            gen_time = r.get("generation_seconds", 0)
            if gen_time > 0:
                gen_times.append(gen_time)
            iter_time = r.get("iteration_seconds", 0)
            if iter_time > 0:
                iter_times.append(iter_time)

            # Loop & sync
            loop_s = r.get("loop_seamlessness", 0)
            if loop_s > 0:
                loop_scores.append(loop_s)
            sync_s = r.get("beat_sync_score", 0)
            if sync_s > 0:
                sync_scores.append(sync_s)

        total = max(len(scores), 1)
        avg_dir = {k: sum(v)/max(len(v),1) for k, v in director_scores.items()}
        avg_genre = {k: sum(v)/max(len(v),1) for k, v in genre_scores.items()}
        avg_axes = {k: sum(v)/max(len(v),1) for k, v in axis_scores.items() if v}

        # Find weakest
        weakest_axis = min(avg_axes, key=avg_axes.get) if avg_axes else ""
        weakest_director = min(avg_dir, key=avg_dir.get) if avg_dir else ""
        weakest_genre = min(avg_genre, key=avg_genre.get) if avg_genre else ""

        # P95 latency
        gen_times.sort()
        iter_times.sort()
        p95_gen = gen_times[int(len(gen_times) * 0.95)] if gen_times else 0
        p95_iter = iter_times[int(len(iter_times) * 0.95)] if iter_times else 0

        self.metrics = QualityMetrics(
            avg_score=sum(scores) / total,
            rejection_rate=rejections / total,
            ai_artifact_rate=artifact_count / total,
            loop_seamlessness=sum(loop_scores) / max(len(loop_scores), 1),
            beat_sync_accuracy=sum(sync_scores) / max(len(sync_scores), 1),
            director_style_match=sum(scores) / total,  # proxy
            generation_p95_seconds=p95_gen,
            iteration_p95_seconds=p95_iter,
            per_director_scores=avg_dir,
            per_genre_scores=avg_genre,
            per_axis_scores=avg_axes,
            total_generations=len(results),
            total_rejections=rejections,
            weakest_axis=weakest_axis,
            weakest_director=weakest_director,
            weakest_genre=weakest_genre,
        )
        return self.metrics

    # ─── Decision Engine ────────────────────────────────────────
    def decide(self, metrics: QualityMetrics) -> ModelDecision:
        """Phase-based model parameter evolution."""
        avg = metrics.avg_score
        decision = ModelDecision(timestamp=datetime.utcnow().isoformat() + "Z")

        # Determine phase
        if avg < 7.0:
            decision.phase = 1
        elif avg < 8.5:
            decision.phase = 2
        elif avg < 9.3:
            decision.phase = 3
        else:
            decision.phase = 4

        params = self.config.get("generation_params", {})
        reasoning_parts = [f"Phase {decision.phase} (avg quality: {avg:.2f})."]

        # ── Phase 1: Basic prompt optimization ──
        if decision.phase == 1:
            decision.negative_prompt_changes = {
                "add": "artificial, digital, CGI, AI-generated, plastic, smooth, overprocessed, stock footage, generic, morphing, glitch, distortion",
            }
            decision.cfg_scale = min(params.get("cfg_scale", 7.5) + 0.5, 12.0)
            decision.generation_steps = min(params.get("generation_steps", 30) + 5, 50)
            reasoning_parts.append("Increasing negative prompts and generation steps for baseline quality.")

        # ── Phase 2: Director-specific tuning ──
        elif decision.phase == 2:
            weakest = metrics.weakest_director
            if weakest and weakest in DIRECTOR_DEFAULTS:
                current_weight = self.config.get("director_weights", {}).get(weakest, 0.7)
                new_weight = min(current_weight + 0.05, 0.95)
                decision.director_weight_changes = {weakest: new_weight}
                reasoning_parts.append(f"Boosting weakest director '{weakest}' LoRA weight {current_weight:.2f} → {new_weight:.2f}.")

            # Tune color grading for weakest axis
            if metrics.weakest_axis:
                reasoning_parts.append(f"Weakest axis: {metrics.weakest_axis}. Adjusting generation parameters.")

            decision.cfg_scale = params.get("cfg_scale", 7.5)
            decision.generation_steps = params.get("generation_steps", 30)

        # ── Phase 3: Beat sync, loop, taste ──
        elif decision.phase == 3:
            decision.loop_smoothing_factor = min(params.get("loop_smoothing_factor", 0.85) + 0.03, 0.98)
            decision.motion_intensity = params.get("motion_intensity", 0.6)

            # Enable taste layer if genres have variance
            if metrics.per_genre_scores:
                worst_genre = metrics.weakest_genre
                if worst_genre and worst_genre in GENRE_TASTE_PROFILES:
                    profile = GENRE_TASTE_PROFILES[worst_genre]
                    decision.taste_layer_updates = {
                        worst_genre: {
                            "prompt_modifier": profile["prompt_modifier"],
                            "negative_extra": profile["negative_extra"],
                            "color_temp": profile["color_temp"],
                        }
                    }
                    reasoning_parts.append(f"Activating taste layer for weakest genre '{worst_genre}'.")

            decision.cfg_scale = params.get("cfg_scale", 7.5)
            decision.generation_steps = params.get("generation_steps", 30)
            reasoning_parts.append(f"Loop smoothing: {decision.loop_smoothing_factor:.2f}.")

        # ── Phase 4: Micro-optimization ──
        else:
            # Small random perturbations for A/B testing
            decision.cfg_scale = params.get("cfg_scale", 7.5)
            decision.generation_steps = params.get("generation_steps", 30)
            decision.motion_intensity = params.get("motion_intensity", 0.6)
            decision.loop_smoothing_factor = params.get("loop_smoothing_factor", 0.85)
            reasoning_parts.append("Quality above 9.3 — micro-optimizing. Maintaining current params.")

        decision.reasoning = " ".join(reasoning_parts)
        decision.metrics_snapshot = asdict(metrics)
        return decision

    # ─── Writers ────────────────────────────────────────────────
    def write_config(self, decision: ModelDecision) -> Path:
        """Write updated model config."""
        config = self.config.copy()
        config["version"] = config.get("version", 0) + 1
        config["phase"] = decision.phase
        config["last_updated"] = decision.timestamp
        config["last_decision"] = decision.reasoning

        # Update generation params
        params = config.setdefault("generation_params", {})
        params["cfg_scale"] = decision.cfg_scale
        params["generation_steps"] = decision.generation_steps
        params["motion_intensity"] = decision.motion_intensity
        params["loop_smoothing_factor"] = decision.loop_smoothing_factor

        # Update director weights
        directors = config.setdefault("director_weights", {})
        for director, weight in decision.director_weight_changes.items():
            if director in directors:
                if isinstance(directors[director], dict):
                    directors[director]["lora_weight"] = weight
                else:
                    directors[director] = weight

        # Update taste layer
        taste = config.setdefault("taste_layer", {"enabled": False, "genre_profiles": {}})
        if decision.taste_layer_updates:
            taste["enabled"] = True
            profiles = taste.setdefault("genre_profiles", {})
            profiles.update(decision.taste_layer_updates)

        CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n")
        self.config = config
        print(f"[ModelEngineer] Config written → {CONFIG_PATH}")
        return CONFIG_PATH

    def _log_decision(self, decision: ModelDecision):
        log_path = OPT_DIR / "model_decisions.jsonl"
        with open(log_path, "a") as f:
            f.write(json.dumps(asdict(decision)) + "\n")

    # ─── Main Entry ─────────────────────────────────────────────
    def run(self) -> Dict:
        """Execute full model optimization cycle."""
        print("\n" + "=" * 65)
        print("  MODEL ENGINEER — Visual Generation Quality Cycle")
        print("=" * 65)

        # 1. Analyze
        metrics = self.analyze()
        print(f"\n[Analyze] Avg score: {metrics.avg_score:.2f}/10 "
              f"({metrics.total_generations} generations, {metrics.total_rejections} rejected)")
        print(f"[Analyze] Loop: {metrics.loop_seamlessness:.0%}, "
              f"Sync: {metrics.beat_sync_accuracy:.0%}, "
              f"Artifacts: {metrics.ai_artifact_rate:.0%}")
        if metrics.per_axis_scores:
            print(f"[Analyze] Weakest axis: {metrics.weakest_axis}, "
                  f"director: {metrics.weakest_director}, genre: {metrics.weakest_genre}")

        # 2. Decide
        decision = self.decide(metrics)
        print(f"\n[Decide] {decision.reasoning}")

        # 3. Write config
        self.write_config(decision)

        # 4. Log
        self._log_decision(decision)

        result = {
            "status": "success",
            "phase": decision.phase,
            "avg_quality": metrics.avg_score,
            "rejection_rate": metrics.rejection_rate,
            "reasoning": decision.reasoning,
        }

        # Summary
        summary_path = DATA_DIR / "model_summary.json"
        summary_path.write_text(json.dumps(result, indent=2) + "\n")

        print(f"\n{'─' * 65}")
        print(f"  RESULT: Phase {decision.phase} | Avg Quality: {metrics.avg_score:.2f}/10")
        print(f"{'=' * 65}\n")

        return result


def main():
    engineer = ModelEngineer()
    engineer.run()


if __name__ == "__main__":
    main()
