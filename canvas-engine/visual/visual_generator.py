#!/usr/bin/env python3
"""
Canvas Visual Generation Module

Bridges the Director Philosophy Engine to the actual SDXL + SVD pipeline.

Takes:
- Emotional DNA from Audio Intelligence
- Director style from Philosophy Engine
- Generation parameters from Orchestrator

Outputs:
- SDXL keyframe (image)
- SVD video clip (animated)
- Post-processed canvas with FFmpeg

Uses the existing loopcanvas_engine.py for style definitions and
loopcanvas_grammy.py for the full pipeline, but adds director-informed
prompt enhancement and parameter injection.

$0 cost on local/fast mode. Cloud mode uses Modal credits.
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass

# Add root for engine imports
ROOT_DIR = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))


@dataclass
class GenerationConfig:
    """Configuration for visual generation"""
    style: str = "memory_in_motion"
    director_style: str = "observed_moment"
    prompt: str = ""
    negative_prompt: str = ""

    # SDXL parameters
    width: int = 720
    height: int = 1280
    guidance_scale: float = 7.5
    num_inference_steps: int = 30
    seed: int = -1  # -1 = random

    # Post-processing
    grain: float = 0.18
    blur: float = 1.0
    contrast: float = 0.80
    saturation: float = 0.75
    vignette: float = 0.9
    brightness: float = -0.03

    # Motion
    motion_intensity: float = 0.4
    motion_type: str = "ken_burns"  # "ken_burns", "svd", "hybrid"

    # Output
    duration: float = 7.0
    fps: int = 24
    output_format: str = "mp4"


# Map director styles to Observed Moment visual styles
DIRECTOR_TO_STYLE = {
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

# Negative prompts by style (things to avoid)
STYLE_NEGATIVES = {
    'observed_moment': "text, watermark, logo, digital art, illustration, anime, "
                       "centered composition, perfect symmetry, studio lighting, "
                       "neon colors, pure black, pure white, sharp focus, "
                       "high contrast, HDR, oversaturated",
    'default': "text, watermark, logo, digital art, illustration, anime, "
               "low quality, blurry, deformed, ugly, duplicate",
}


class VisualGenerator:
    """
    Visual generation engine for Canvas.

    Supports three generation tiers:
    - Fast: SDXL + Ken Burns (local, ~90 sec)
    - Local: SDXL + SVD (local CPU, ~30 min)
    - Cloud: SDXL + SVD on Modal H100 (~30 sec)
    """

    def __init__(self, mode: str = None):
        self.mode = mode or os.environ.get("LOOPCANVAS_MODE", "fast")

    def generate(self, config: GenerationConfig, output_dir: str) -> Tuple[bool, Dict]:
        """
        Generate visual content based on configuration.

        Returns:
            (success, outputs_dict)
        """
        os.makedirs(output_dir, exist_ok=True)

        # Build the FFmpeg post-processing filter chain
        post_filters = self._build_post_filters(config)

        if self.mode == "fast":
            return self._generate_fast(config, output_dir, post_filters)
        elif self.mode == "cloud":
            return self._generate_cloud(config, output_dir, post_filters)
        else:
            return self._generate_local(config, output_dir, post_filters)

    def _generate_fast(self, config: GenerationConfig, output_dir: str,
                        post_filters: str) -> Tuple[bool, Dict]:
        """Fast mode: SDXL keyframe + Ken Burns motion via FFmpeg"""
        # Delegate to existing fast_ai_video_gen.py
        script = ROOT_DIR / "fast_ai_video_gen.py"

        if not script.exists():
            return False, {"error": "fast_ai_video_gen.py not found"}

        env = os.environ.copy()
        env["LOOPCANVAS_MODE"] = "fast"
        env["LOOPCANVAS_GRAIN"] = str(config.grain)
        env["LOOPCANVAS_CONTRAST"] = str(config.contrast)
        env["LOOPCANVAS_SATURATION"] = str(config.saturation)
        env["LOOPCANVAS_BLUR"] = str(config.blur)
        env["LOOPCANVAS_MOTION_INTENSITY"] = str(config.motion_intensity)

        cmd = [
            sys.executable, str(script),
            "--prompt", config.prompt,
            "--output", output_dir,
        ]

        if config.seed >= 0:
            cmd.extend(["--seed", str(config.seed)])

        result = subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=str(ROOT_DIR), env=env, timeout=300
        )

        if result.returncode == 0:
            outputs = self._find_outputs(output_dir)
            return True, outputs
        else:
            return False, {"error": result.stderr[:500]}

    def _generate_cloud(self, config: GenerationConfig, output_dir: str,
                         post_filters: str) -> Tuple[bool, Dict]:
        """Cloud mode: Modal H100 GPU for full SDXL + SVD"""
        from agents.cost_enforcer import can_spend, get_free_alternative

        if not can_spend("modal", 0.12):
            alt = get_free_alternative("modal")
            return False, {"error": f"Cloud blocked by $0 rule. Use: {alt}"}

        script = ROOT_DIR / "cloud_video_gen.py"
        if not script.exists():
            # Fallback to fast mode
            return self._generate_fast(config, output_dir, post_filters)

        env = os.environ.copy()
        env["LOOPCANVAS_MODE"] = "cloud"

        cmd = [
            sys.executable, str(script),
            "--prompt", config.prompt,
            "--output", output_dir,
        ]

        result = subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=str(ROOT_DIR), env=env, timeout=120
        )

        if result.returncode == 0:
            outputs = self._find_outputs(output_dir)
            return True, outputs
        else:
            return False, {"error": result.stderr[:500]}

    def _generate_local(self, config: GenerationConfig, output_dir: str,
                         post_filters: str) -> Tuple[bool, Dict]:
        """Local mode: Full SDXL + SVD on local hardware"""
        script = ROOT_DIR / "local_ai_video_gen.py"

        if not script.exists():
            return self._generate_fast(config, output_dir, post_filters)

        env = os.environ.copy()
        env["LOOPCANVAS_MODE"] = "local"

        cmd = [
            sys.executable, str(script),
            "--prompt", config.prompt,
            "--output", output_dir,
        ]

        result = subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=str(ROOT_DIR), env=env, timeout=3600
        )

        if result.returncode == 0:
            outputs = self._find_outputs(output_dir)
            return True, outputs
        else:
            return False, {"error": result.stderr[:500]}

    def _build_post_filters(self, config: GenerationConfig) -> str:
        """Build FFmpeg post-processing filter chain from config"""
        filters = []

        # Color grading
        eq_parts = []
        if config.contrast != 1.0:
            eq_parts.append(f"contrast={config.contrast:.2f}")
        if config.saturation != 1.0:
            eq_parts.append(f"saturation={config.saturation:.2f}")
        if config.brightness != 0:
            eq_parts.append(f"brightness={config.brightness:.3f}")
        if eq_parts:
            filters.append(f"eq={':'.join(eq_parts)}")

        # Lifted blacks, lowered whites (Observed Moment signature)
        filters.append("curves=master='0.08/0.12 0.25/0.28 0.5/0.5 0.75/0.72 0.92/0.88'")

        # Soft focus
        if config.blur > 0:
            filters.append(f"gblur=sigma={config.blur:.1f}")

        # Film grain
        if config.grain > 0:
            noise = int(config.grain * 100)
            filters.append(f"noise=c0s={noise}:c1s={noise//2}:c2s={noise//2}:c0f=t:c1f=t:c2f=t")

        # Vignette
        if config.vignette > 0:
            filters.append(f"vignette=PI/{3 + (1 - config.vignette) * 2:.1f}:a={config.vignette:.1f}")

        return ",".join(filters) if filters else ""

    def apply_post_processing(self, video_path: str, output_path: str,
                                config: GenerationConfig) -> bool:
        """Apply post-processing filters to an existing video"""
        filters = self._build_post_filters(config)

        if not filters:
            # No filters to apply, just copy
            import shutil
            shutil.copy(video_path, output_path)
            return True

        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", filters,
            "-c:v", "libx264", "-profile:v", "high",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            "-crf", "18",
            "-c:a", "copy",
            output_path,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return result.returncode == 0

    def _find_outputs(self, output_dir: str) -> Dict:
        """Find generated output files in directory"""
        outputs = {}
        od = Path(output_dir)

        for pattern, key in [
            ("spotify_canvas_web.mp4", "canvas"),
            ("spotify_canvas_7s_9x16.mp4", "canvas_raw"),
            ("full_music_video_9x16.mp4", "full_video"),
            ("*_keyframe.png", "keyframe"),
            ("concept.json", "concept"),
        ]:
            matches = list(od.glob(pattern))
            if matches:
                outputs[key] = str(matches[0])

        return outputs

    @staticmethod
    def config_from_direction(direction: dict, emotional_dna: dict = None) -> GenerationConfig:
        """Create a GenerationConfig from a visual direction and emotional DNA"""
        params = direction.get('params', {})
        style = DIRECTOR_TO_STYLE.get(direction.get('director_style', ''), 'memory_in_motion')

        config = GenerationConfig(
            style=style,
            director_style=direction.get('director_style', 'observed_moment'),
            prompt=direction.get('preview_prompt', ''),
            negative_prompt=STYLE_NEGATIVES.get(
                direction.get('director_style', ''),
                STYLE_NEGATIVES['default']
            ),
            grain=params.get('grain', 0.18),
            blur=params.get('blur', 1.0),
            contrast=params.get('contrast', 0.80),
            saturation=params.get('saturation', 0.75),
            motion_intensity=params.get('motion_intensity', 0.4),
        )

        # Adjust based on emotional DNA
        if emotional_dna:
            arousal = emotional_dna.get('arousal', 0.5)
            config.motion_intensity = max(0.2, min(0.8,
                config.motion_intensity + (arousal - 0.5) * 0.3
            ))

        return config
