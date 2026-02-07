#!/usr/bin/env python3
"""
Audio Intelligence Lead — Canvas Agent Army v2.0

Builds the world's best audio-to-emotion understanding system.
The Taste Gap is the hardest unsolved problem: cultural fluency across genres.

"The hardest problem is not generation quality. It is taste. An AI can generate
a technically perfect visual that has no soul. Your system needs a taste layer
that understands cultural context: what looks cool in Atlanta hip-hop is different
from London grime, K-pop, Nashville country." — Canvas Agent Army Spec

Pipeline:
  1. ANALYZE: Read canvas results and artist preference signals
  2. CALIBRATE: Adjust emotion-to-visual mappings based on accept/reject data
  3. PROFILE: Update genre-specific visual language profiles
  4. TASTE: Build cultural fluency score, track cross-genre patterns
  5. CONFIGURE: Write audio_config.json + emotion_mappings.json

Phases:
  Phase 1 (accuracy < 0.5): Baseline BPM/key detection, emotion mapping
  Phase 2 (0.5-0.7): Genre-specific calibration, director-emotion alignment
  Phase 3 (0.7-0.85): Cultural taste mapping, artist preference learning
  Phase 4 (> 0.85): Micro-genre detection, cross-genre fusion
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional
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
CONFIG_PATH = APP_DIR / "audio_config.json"

DATA_DIR.mkdir(exist_ok=True)
OPT_DIR.mkdir(exist_ok=True)

# ══════════════════════════════════════════════════════════════
# Emotion → Visual Mapping (Proprietary Layer 2)
# ══════════════════════════════════════════════════════════════

EMOTION_TO_VISUAL = {
    "valence": {
        "desc": "Color warmth: low valence = cool blues/grays, high = warm golds/ambers",
        "low":  {"color_temp": "cool", "palette": ["#1a1a2e", "#16213e", "#0f3460"], "mood": "melancholic"},
        "mid":  {"color_temp": "neutral", "palette": ["#2d3436", "#636e72", "#b2bec3"], "mood": "contemplative"},
        "high": {"color_temp": "warm", "palette": ["#f9ca24", "#f0932b", "#eb4d4b"], "mood": "euphoric"},
    },
    "arousal": {
        "desc": "Motion intensity: low = gentle drift, high = rapid cuts/energy",
        "low":  {"motion": 0.15, "cut_freq": 0.1, "camera": "static"},
        "mid":  {"motion": 0.45, "cut_freq": 0.3, "camera": "slow_drift"},
        "high": {"motion": 0.75, "cut_freq": 0.5, "camera": "tracking"},
    },
    "tension": {
        "desc": "Visual complexity: low = minimal, high = layered/dense",
        "low":  {"complexity": 0.2, "depth_layers": 1, "negative_space": 0.7},
        "mid":  {"complexity": 0.5, "depth_layers": 2, "negative_space": 0.4},
        "high": {"complexity": 0.8, "depth_layers": 3, "negative_space": 0.15},
    },
    "release": {
        "desc": "Spatial openness: low = tight framing, high = wide/expansive",
        "low":  {"framing": "close_up", "focal_length": 85, "depth_of_field": "shallow"},
        "mid":  {"framing": "medium", "focal_length": 50, "depth_of_field": "moderate"},
        "high": {"framing": "wide", "focal_length": 24, "depth_of_field": "deep"},
    },
}

# ══════════════════════════════════════════════════════════════
# Genre Visual Language (The Taste Layer)
# ══════════════════════════════════════════════════════════════

GENRE_VISUAL_LANGUAGE = {
    "hip_hop": {
        "color_palette": "high_contrast",
        "motion_style": "kinetic",
        "texture": "gritty",
        "camera_movement": "handheld_subtle",
        "editing_rhythm": "syncopated",
        "cultural_references": "street_art, urban_landscape, luxury_contrast",
        "prompt_modifier": "urban cinematography, high contrast, gritty texture, 35mm film",
        "negative_modifier": "pastoral, soft focus, countryside, gentle",
    },
    "electronic": {
        "color_palette": "neon_cool",
        "motion_style": "pulsing",
        "texture": "clean_synthetic",
        "camera_movement": "smooth_glide",
        "editing_rhythm": "pulse_driven",
        "cultural_references": "rave_culture, light_installation, abstract_geometry",
        "prompt_modifier": "neon lighting, clean geometry, pulsing light, club aesthetic",
        "negative_modifier": "organic, rustic, vintage, warm tones",
    },
    "indie": {
        "color_palette": "muted_warm",
        "motion_style": "gentle_drift",
        "texture": "film_grain",
        "camera_movement": "static_contemplative",
        "editing_rhythm": "breath_paced",
        "cultural_references": "art_house, zine_culture, analog_nostalgia",
        "prompt_modifier": "film grain, muted tones, golden hour, lo-fi, art house cinema",
        "negative_modifier": "flashy, neon, corporate, polished, digital",
    },
    "pop": {
        "color_palette": "vibrant_saturated",
        "motion_style": "dynamic",
        "texture": "polished",
        "camera_movement": "dolly_smooth",
        "editing_rhythm": "hook_driven",
        "cultural_references": "fashion, pop_art, aspirational",
        "prompt_modifier": "vibrant, saturated colors, dynamic movement, polished aesthetic",
        "negative_modifier": "gritty, dark, moody, desaturated, rough",
    },
    "r_and_b": {
        "color_palette": "warm_rich",
        "motion_style": "smooth_languid",
        "texture": "velvet",
        "camera_movement": "slow_push",
        "editing_rhythm": "groove_led",
        "cultural_references": "intimacy, golden_hour, luxury_soft",
        "prompt_modifier": "warm golden light, intimate framing, velvet texture, sensual",
        "negative_modifier": "harsh, cold, clinical, sterile, bright",
    },
    "country": {
        "color_palette": "earth_tones",
        "motion_style": "steady_unhurried",
        "texture": "natural",
        "camera_movement": "wide_establishing",
        "editing_rhythm": "storytelling",
        "cultural_references": "americana, open_road, small_town, sunset",
        "prompt_modifier": "earth tones, natural light, wide landscape, americana, golden hour",
        "negative_modifier": "urban, neon, futuristic, synthetic, digital",
    },
    "rock": {
        "color_palette": "dark_saturated",
        "motion_style": "aggressive_raw",
        "texture": "raw_gritty",
        "camera_movement": "handheld_urgent",
        "editing_rhythm": "impact_driven",
        "cultural_references": "rebellion, live_stage, distortion, analog",
        "prompt_modifier": "dark saturated, raw energy, concert lighting, analog grain",
        "negative_modifier": "gentle, soft, pastel, calm, clean",
    },
    "latin": {
        "color_palette": "warm_vivid",
        "motion_style": "rhythmic_flowing",
        "texture": "lush_organic",
        "camera_movement": "fluid_tracking",
        "editing_rhythm": "clave_synced",
        "cultural_references": "tropicalia, carnival, sun_drenched, barrio",
        "prompt_modifier": "warm vivid colors, rhythmic movement, lush, tropical, sun-drenched",
        "negative_modifier": "cold, sterile, monochrome, industrial, minimal",
    },
    "k_pop": {
        "color_palette": "pastel_neon",
        "motion_style": "precise_choreographed",
        "texture": "glossy_clean",
        "camera_movement": "dynamic_angles",
        "editing_rhythm": "beat_precise",
        "cultural_references": "idol_culture, seoul, kawaii_meets_edge",
        "prompt_modifier": "pastel and neon, precise framing, glossy, clean aesthetic",
        "negative_modifier": "gritty, dirty, rough, organic, vintage",
    },
    "afrobeats": {
        "color_palette": "golden_warm",
        "motion_style": "flowing_joyful",
        "texture": "organic_rich",
        "camera_movement": "celebratory_wide",
        "editing_rhythm": "polyrhythmic",
        "cultural_references": "diaspora, lagos, celebration, community",
        "prompt_modifier": "golden warm light, flowing movement, organic, community, celebration",
        "negative_modifier": "cold, dark, isolating, mechanical, sterile",
    },
}

# ══════════════════════════════════════════════════════════════
# Data Structures
# ══════════════════════════════════════════════════════════════

@dataclass
class AudioMetrics:
    total_tracks_analyzed: int = 0
    avg_bpm_accuracy: float = 0.0
    avg_key_accuracy: float = 0.0
    avg_genre_accuracy: float = 0.0
    avg_emotion_accuracy: float = 0.0
    avg_beat_sync_score: float = 0.0
    taste_layer_score: float = 0.0
    genre_distribution: Dict[str, int] = field(default_factory=dict)
    emotion_distribution: Dict[str, float] = field(default_factory=dict)
    artist_preference_signals: int = 0
    weakest_genre: str = ""
    genre_satisfaction: Dict[str, float] = field(default_factory=dict)


@dataclass
class AudioDecision:
    timestamp: str = ""
    phase: int = 1
    emotion_calibration: Dict = field(default_factory=dict)
    genre_profile_updates: Dict = field(default_factory=dict)
    taste_layer_updates: Dict = field(default_factory=dict)
    reasoning: str = ""
    metrics_snapshot: Dict = field(default_factory=dict)


# ══════════════════════════════════════════════════════════════
# Audio Intelligence Agent
# ══════════════════════════════════════════════════════════════

class AudioIntelligence:
    """Autonomous agent that builds the audio-to-emotion understanding system."""

    def __init__(self):
        self.metrics = AudioMetrics()
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        if CONFIG_PATH.exists():
            try:
                return json.loads(CONFIG_PATH.read_text())
            except (json.JSONDecodeError, IOError):
                pass
        return {
            "version": 1, "phase": 1,
            "emotion_mapping": EMOTION_TO_VISUAL,
            "genre_profiles": {k: {"satisfaction": 0.0} for k in GENRE_VISUAL_LANGUAGE},
            "taste_layer": {"enabled": False, "cultural_fluency_score": 0.0, "artist_preference_signals": 0},
            "detection_accuracy": {"bpm": 0.0, "key": 0.0, "genre": 0.0, "emotion": 0.0, "beat_sync": 0.0},
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
    def analyze(self) -> AudioMetrics:
        """Analyze audio quality from canvas results and artist preferences."""
        results = self._read_jsonl(OPT_DIR / "canvas_results.jsonl")
        funnel = self._read_jsonl(DATA_DIR / "onboarding_funnel.jsonl")

        if not results and not funnel:
            print("[AudioIntelligence] No data yet — using defaults.")
            return self.metrics

        # Track accuracy from canvas results
        bpm_scores = []
        key_scores = []
        genre_scores = []
        emotion_scores = []
        sync_scores = []
        genre_counts = {}
        genre_satisfaction = {}
        preference_signals = 0

        for r in results:
            # BPM accuracy
            bpm_acc = r.get("bpm_accuracy", r.get("audio_bpm_accuracy", 0))
            if bpm_acc > 0:
                bpm_scores.append(bpm_acc)

            # Key accuracy
            key_acc = r.get("key_accuracy", r.get("audio_key_accuracy", 0))
            if key_acc > 0:
                key_scores.append(key_acc)

            # Genre accuracy
            genre_acc = r.get("genre_accuracy", 0)
            if genre_acc > 0:
                genre_scores.append(genre_acc)

            # Emotion accuracy
            emotion_acc = r.get("emotion_accuracy", r.get("audio_emotion_match", 0))
            if emotion_acc > 0:
                emotion_scores.append(emotion_acc)

            # Beat sync
            sync = r.get("beat_sync_score", r.get("beat_sync_accuracy", 0))
            if sync > 0:
                sync_scores.append(sync)

            # Genre distribution
            genre = r.get("genre", "unknown")
            genre_counts[genre] = genre_counts.get(genre, 0) + 1

            # Genre satisfaction (quality per genre)
            quality = r.get("quality_score", 0)
            if quality > 0:
                genre_satisfaction.setdefault(genre, []).append(quality)

            # Artist preference signals
            if r.get("accepted", False) or r.get("rejected", False):
                preference_signals += 1

        # Also count preference signals from funnel
        for e in funnel:
            if e.get("event") in ("director_select", "direction_accept", "direction_reject"):
                preference_signals += 1

        # Compute averages
        def safe_avg(lst):
            return sum(lst) / max(len(lst), 1)

        avg_genre_sat = {k: safe_avg(v) for k, v in genre_satisfaction.items()}
        weakest_genre = min(avg_genre_sat, key=avg_genre_sat.get) if avg_genre_sat else ""

        # Overall accuracy
        all_accuracies = [
            safe_avg(bpm_scores),
            safe_avg(key_scores),
            safe_avg(genre_scores),
            safe_avg(emotion_scores),
        ]
        overall_accuracy = safe_avg([a for a in all_accuracies if a > 0]) if any(a > 0 for a in all_accuracies) else 0.0

        # Taste layer score: how well we understand cultural context
        genre_coverage = len(genre_satisfaction) / max(len(GENRE_VISUAL_LANGUAGE), 1)
        taste_score = (overall_accuracy * 0.6 + genre_coverage * 0.4)

        self.metrics = AudioMetrics(
            total_tracks_analyzed=len(results),
            avg_bpm_accuracy=safe_avg(bpm_scores),
            avg_key_accuracy=safe_avg(key_scores),
            avg_genre_accuracy=safe_avg(genre_scores),
            avg_emotion_accuracy=safe_avg(emotion_scores),
            avg_beat_sync_score=safe_avg(sync_scores),
            taste_layer_score=taste_score,
            genre_distribution=genre_counts,
            genre_satisfaction=avg_genre_sat,
            artist_preference_signals=preference_signals,
            weakest_genre=weakest_genre,
        )
        return self.metrics

    # ─── Emotion Calibration ────────────────────────────────────
    def calibrate_emotions(self, metrics: AudioMetrics) -> Dict:
        """Adjust emotion-to-visual mappings based on artist accept/reject signals."""
        calibration = {}

        # If emotion accuracy is low, widen the mapping ranges
        if 0 < metrics.avg_emotion_accuracy < 0.5:
            calibration["action"] = "widen_ranges"
            calibration["detail"] = "Emotion accuracy below 50% — widening valence/arousal ranges for more forgiving mapping."
        elif metrics.avg_emotion_accuracy >= 0.7:
            calibration["action"] = "tighten_ranges"
            calibration["detail"] = "Emotion accuracy above 70% — tightening ranges for more precise emotional targeting."
        else:
            calibration["action"] = "maintain"
            calibration["detail"] = "Emotion accuracy in transition range — maintaining current mappings."

        # Specific axis calibration
        if metrics.avg_beat_sync_score > 0 and metrics.avg_beat_sync_score < 0.6:
            calibration["beat_sync_fix"] = "Reduce arousal→cut_freq mapping. Current beat sync too aggressive."

        return calibration

    # ─── Genre Profile Updates ──────────────────────────────────
    def update_genre_profiles(self, metrics: AudioMetrics) -> Dict:
        """Refine genre profiles based on which genres have lowest satisfaction."""
        updates = {}

        if not metrics.genre_satisfaction:
            return updates

        # Find underperforming genres
        for genre, satisfaction in metrics.genre_satisfaction.items():
            if satisfaction < 7.0 and genre in GENRE_VISUAL_LANGUAGE:
                profile = GENRE_VISUAL_LANGUAGE[genre]
                updates[genre] = {
                    "action": "refine",
                    "current_satisfaction": satisfaction,
                    "suggestion": f"Increase cultural specificity for {genre}. "
                                  f"Current prompt: '{profile['prompt_modifier'][:60]}...'. "
                                  f"Add more genre-specific negative prompts.",
                }

        return updates

    # ─── Taste Layer ────────────────────────────────────────────
    def update_taste_layer(self, metrics: AudioMetrics) -> Dict:
        """Build cultural fluency: the hardest problem in the system."""
        taste = {}

        taste["cultural_fluency_score"] = metrics.taste_layer_score
        taste["artist_preference_signals"] = metrics.artist_preference_signals
        taste["genres_with_data"] = len(metrics.genre_satisfaction)
        taste["total_genres"] = len(GENRE_VISUAL_LANGUAGE)
        taste["coverage"] = len(metrics.genre_satisfaction) / max(len(GENRE_VISUAL_LANGUAGE), 1)

        # Taste maturity assessment
        if metrics.taste_layer_score < 0.3:
            taste["maturity"] = "nascent"
            taste["action"] = "Collect more artist preference signals. Need 100+ signals per genre."
        elif metrics.taste_layer_score < 0.6:
            taste["maturity"] = "developing"
            taste["action"] = "Begin cross-genre analysis. Look for shared visual patterns."
        elif metrics.taste_layer_score < 0.85:
            taste["maturity"] = "refined"
            taste["action"] = "Micro-genre detection. Distinguish sub-genres (e.g., trap vs boom-bap)."
        else:
            taste["maturity"] = "expert"
            taste["action"] = "Cross-genre fusion. Blend visual languages for genre-crossing artists."

        return taste

    # ─── Decision Engine ────────────────────────────────────────
    def decide(self, metrics: AudioMetrics) -> AudioDecision:
        """Phase-based audio intelligence evolution."""
        # Compute overall accuracy
        accuracies = [
            metrics.avg_bpm_accuracy, metrics.avg_key_accuracy,
            metrics.avg_genre_accuracy, metrics.avg_emotion_accuracy,
        ]
        avg_accuracy = sum(a for a in accuracies if a > 0) / max(sum(1 for a in accuracies if a > 0), 1)

        decision = AudioDecision(timestamp=datetime.utcnow().isoformat() + "Z")
        reasoning_parts = []

        if avg_accuracy < 0.5:
            decision.phase = 1
            reasoning_parts.append(f"Phase 1 (accuracy {avg_accuracy:.0%}): Focus on baseline BPM/key detection.")
        elif avg_accuracy < 0.7:
            decision.phase = 2
            reasoning_parts.append(f"Phase 2 (accuracy {avg_accuracy:.0%}): Genre-specific calibration.")
        elif avg_accuracy < 0.85:
            decision.phase = 3
            reasoning_parts.append(f"Phase 3 (accuracy {avg_accuracy:.0%}): Cultural taste mapping.")
        else:
            decision.phase = 4
            reasoning_parts.append(f"Phase 4 (accuracy {avg_accuracy:.0%}): Micro-genre and cross-genre fusion.")

        # Calibrate emotions
        decision.emotion_calibration = self.calibrate_emotions(metrics)
        if decision.emotion_calibration.get("action") != "maintain":
            reasoning_parts.append(f"Emotion calibration: {decision.emotion_calibration.get('action', 'none')}.")

        # Update genre profiles
        decision.genre_profile_updates = self.update_genre_profiles(metrics)
        if decision.genre_profile_updates:
            reasoning_parts.append(f"Refining {len(decision.genre_profile_updates)} underperforming genres.")

        # Update taste layer
        decision.taste_layer_updates = self.update_taste_layer(metrics)
        if decision.taste_layer_updates:
            maturity = decision.taste_layer_updates.get("maturity", "unknown")
            reasoning_parts.append(f"Taste layer: {maturity} ({metrics.taste_layer_score:.0%} fluency).")

        decision.reasoning = " ".join(reasoning_parts)
        decision.metrics_snapshot = asdict(metrics)
        return decision

    # ─── Writers ────────────────────────────────────────────────
    def write_config(self, decision: AudioDecision) -> Path:
        config = self.config.copy()
        config["version"] = config.get("version", 0) + 1
        config["phase"] = decision.phase
        config["last_updated"] = decision.timestamp
        config["last_decision"] = decision.reasoning

        # Update detection accuracy
        config["detection_accuracy"] = {
            "bpm": self.metrics.avg_bpm_accuracy,
            "key": self.metrics.avg_key_accuracy,
            "genre": self.metrics.avg_genre_accuracy,
            "emotion": self.metrics.avg_emotion_accuracy,
            "beat_sync": self.metrics.avg_beat_sync_score,
        }

        # Update taste layer
        taste = config.setdefault("taste_layer", {})
        taste["enabled"] = decision.phase >= 3
        taste["cultural_fluency_score"] = self.metrics.taste_layer_score
        taste["artist_preference_signals"] = self.metrics.artist_preference_signals

        # Update genre profiles with satisfaction scores
        profiles = config.setdefault("genre_profiles", {})
        for genre, sat in self.metrics.genre_satisfaction.items():
            if genre in profiles:
                if isinstance(profiles[genre], dict):
                    profiles[genre]["satisfaction"] = sat
                else:
                    profiles[genre] = {"satisfaction": sat}

        CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n")
        print(f"[AudioIntelligence] Config written → {CONFIG_PATH}")
        return CONFIG_PATH

    def write_emotion_mappings(self) -> Path:
        """Write the emotion-to-visual mapping data for other agents to consume."""
        mappings = {
            "emotion_to_visual": EMOTION_TO_VISUAL,
            "genre_visual_language": {
                k: {
                    "prompt_modifier": v["prompt_modifier"],
                    "negative_modifier": v["negative_modifier"],
                    "color_palette": v["color_palette"],
                    "motion_style": v["motion_style"],
                }
                for k, v in GENRE_VISUAL_LANGUAGE.items()
            },
            "genre_satisfaction": self.metrics.genre_satisfaction,
            "taste_score": self.metrics.taste_layer_score,
            "last_updated": datetime.utcnow().isoformat() + "Z",
        }
        out_path = OPT_DIR / "emotion_mappings.json"
        out_path.write_text(json.dumps(mappings, indent=2) + "\n")
        print(f"[AudioIntelligence] Emotion mappings written → {out_path}")
        return out_path

    def _log_decision(self, decision: AudioDecision):
        log_path = DATA_DIR / "audio_decisions.jsonl"
        with open(log_path, "a") as f:
            f.write(json.dumps(asdict(decision)) + "\n")

    # ─── Main Entry ─────────────────────────────────────────────
    def run(self) -> Dict:
        print("\n" + "=" * 65)
        print("  AUDIO INTELLIGENCE — Emotion Mapping & Taste Layer Cycle")
        print("=" * 65)

        metrics = self.analyze()
        print(f"\n[Analyze] {metrics.total_tracks_analyzed} tracks analyzed")
        print(f"[Analyze] BPM: {metrics.avg_bpm_accuracy:.0%}, Key: {metrics.avg_key_accuracy:.0%}, "
              f"Genre: {metrics.avg_genre_accuracy:.0%}, Emotion: {metrics.avg_emotion_accuracy:.0%}")
        print(f"[Analyze] Taste layer score: {metrics.taste_layer_score:.0%}")
        print(f"[Analyze] Preference signals: {metrics.artist_preference_signals}")
        if metrics.weakest_genre:
            print(f"[Analyze] Weakest genre: {metrics.weakest_genre}")

        decision = self.decide(metrics)
        print(f"\n[Decide] {decision.reasoning}")

        self.write_config(decision)
        self.write_emotion_mappings()
        self._log_decision(decision)

        result = {
            "status": "success",
            "phase": decision.phase,
            "taste_score": metrics.taste_layer_score,
            "tracks_analyzed": metrics.total_tracks_analyzed,
            "reasoning": decision.reasoning,
        }

        summary_path = DATA_DIR / "audio_summary.json"
        summary_path.write_text(json.dumps(result, indent=2) + "\n")

        print(f"\n{'─' * 65}")
        print(f"  RESULT: Phase {decision.phase} | Taste: {metrics.taste_layer_score:.0%}")
        print(f"{'=' * 65}\n")

        return result


def main():
    agent = AudioIntelligence()
    agent.run()


if __name__ == "__main__":
    main()
