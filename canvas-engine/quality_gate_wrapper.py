#!/usr/bin/env python3
"""
Quality Gate Wrapper — Bridges the QualityGate into the orchestrator pipeline.

Provides a simplified evaluate() interface that returns a dict
instead of requiring direct QualityScore handling.
"""

from pathlib import Path
from typing import Dict, Optional

# Import the actual quality gate
from quality_gate import ai_detector


class QualityGateWrapper:
    """Wrapper around CanvasQualityGate for orchestrator integration"""

    def __init__(self):
        self.gate = ai_detector.CanvasQualityGate()

    def evaluate(self, video_path: str, audio_dna: dict = None) -> Dict:
        """
        Evaluate a canvas video and return a serializable dict.

        Returns:
            {
                'overall_score': float,
                'passed': bool,
                'ai_artifact_score': float,
                'cinematic_quality': float,
                'loop_seamlessness': float,
                'temporal_consistency': float,
                'color_grading_quality': float,
                'motion_naturalness': float,
                'issues': list,
                'recommendations': list,
            }
        """
        if not Path(video_path).exists():
            return {
                'overall_score': 0.0,
                'passed': False,
                'issues': [f'Video file not found: {video_path}'],
                'recommendations': ['Check generation pipeline output'],
            }

        try:
            score = self.gate.evaluate_canvas(video_path, audio_dna)
            return {
                'overall_score': score.overall_score,
                'passed': score.passed,
                'ai_artifact_score': score.ai_artifact_score,
                'cinematic_quality': score.cinematic_quality,
                'loop_seamlessness': score.loop_seamlessness,
                'temporal_consistency': score.temporal_consistency,
                'color_grading_quality': score.color_grading_quality,
                'motion_naturalness': score.motion_naturalness,
                'issues': score.issues,
                'recommendations': score.recommendations,
                'worst_frames': score.worst_frames,
            }
        except Exception as e:
            return {
                'overall_score': 0.0,
                'passed': False,
                'issues': [f'Quality evaluation error: {str(e)}'],
                'recommendations': ['Check video format and dependencies'],
            }
