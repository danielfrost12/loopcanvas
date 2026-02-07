#!/usr/bin/env python3
"""
Canvas Loop Engine (Patent-Ready Innovation #3)

Seamless Loop Generation System

Every Spotify Canvas must loop perfectly. Not "good enough" - PERFECTLY.
The viewer should never see where the loop begins or ends.

This system:
1. Detects optimal loop points mathematically
2. Cross-fades frames at loop boundaries
3. Validates loop seamlessness with quality scoring
4. Auto-corrects imperfect loops

$0 cost - uses OpenCV and numpy only
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional
from pathlib import Path
import subprocess
import tempfile

# Lazy imports
cv2 = None


def _load_cv2():
    global cv2
    if cv2 is None:
        import cv2 as _cv2
        cv2 = _cv2
    return cv2


@dataclass
class LoopAnalysis:
    """Analysis result for loop quality"""
    is_seamless: bool
    seamlessness_score: float  # 0-10
    optimal_loop_start: int  # Frame index
    optimal_loop_end: int  # Frame index
    recommended_crossfade_frames: int
    issues: List[str]


@dataclass
class LoopPoint:
    """A potential loop point"""
    frame_start: int
    frame_end: int
    similarity_score: float
    motion_continuity: float
    color_match: float


class CanvasLoopEngine:
    """
    The Loop Engine - Makes every canvas loop perfectly.

    Spotify Canvas requirements:
    - 3-8 seconds long
    - Must loop seamlessly
    - No visible jump or cut

    This engine ensures mathematical perfection.
    """

    MINIMUM_SEAMLESSNESS = 9.0  # Out of 10

    def __init__(self):
        self.target_fps = 24  # Cinematic frame rate
        self.min_loop_duration = 3.0  # seconds
        self.max_loop_duration = 8.0  # seconds

    def analyze_loop(self, video_path: str) -> LoopAnalysis:
        """
        Analyze a video's loop quality.

        Args:
            video_path: Path to video file

        Returns:
            LoopAnalysis with quality metrics and recommendations
        """
        cv = _load_cv2()

        cap = cv.VideoCapture(video_path)
        if not cap.isOpened():
            return LoopAnalysis(
                is_seamless=False,
                seamlessness_score=0.0,
                optimal_loop_start=0,
                optimal_loop_end=0,
                recommended_crossfade_frames=0,
                issues=["Could not open video file"]
            )

        # Read all frames
        frames = []
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)
        cap.release()

        fps = cap.get(cv.CAP_PROP_FPS) or 24
        total_frames = len(frames)

        if total_frames < 30:
            return LoopAnalysis(
                is_seamless=False,
                seamlessness_score=0.0,
                optimal_loop_start=0,
                optimal_loop_end=total_frames - 1,
                recommended_crossfade_frames=0,
                issues=["Video too short for loop analysis"]
            )

        # Analyze current loop quality (first vs last frames)
        first_frame = frames[0]
        last_frame = frames[-1]

        similarity = self._calculate_frame_similarity(first_frame, last_frame)
        motion_cont = self._calculate_motion_continuity(frames)
        color_match = self._calculate_color_consistency(frames)

        # Overall seamlessness score
        seamlessness = (
            similarity * 0.5 +
            motion_cont * 0.3 +
            color_match * 0.2
        ) * 10

        issues = []
        if similarity < 0.85:
            issues.append("First and last frames don't match well")
        if motion_cont < 0.80:
            issues.append("Motion discontinuity at loop point")
        if color_match < 0.90:
            issues.append("Color shift visible across loop")

        # Find optimal loop points if current isn't good
        optimal_start = 0
        optimal_end = total_frames - 1
        crossfade_frames = 0

        if seamlessness < self.MINIMUM_SEAMLESSNESS:
            loop_points = self._find_optimal_loop_points(frames)
            if loop_points:
                best = loop_points[0]
                optimal_start = best.frame_start
                optimal_end = best.frame_end
                crossfade_frames = max(3, int(fps * 0.2))  # 0.2 second crossfade

        return LoopAnalysis(
            is_seamless=bool(seamlessness >= self.MINIMUM_SEAMLESSNESS),
            seamlessness_score=round(float(seamlessness), 2),
            optimal_loop_start=optimal_start,
            optimal_loop_end=optimal_end,
            recommended_crossfade_frames=crossfade_frames,
            issues=issues
        )

    def create_seamless_loop(self, video_path: str, output_path: str,
                              crossfade_frames: int = 6) -> Tuple[bool, str]:
        """
        Create a seamlessly looping version of a video.

        Args:
            video_path: Input video path
            output_path: Output video path
            crossfade_frames: Number of frames to crossfade

        Returns:
            (success, message)
        """
        cv = _load_cv2()

        cap = cv.VideoCapture(video_path)
        if not cap.isOpened():
            return False, "Could not open video file"

        # Read all frames
        frames = []
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)

        fps = cap.get(cv.CAP_PROP_FPS) or 24
        width = int(cap.get(cv.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv.CAP_PROP_FRAME_HEIGHT))
        cap.release()

        if len(frames) < crossfade_frames * 2:
            return False, "Video too short for crossfade"

        # Apply crossfade at loop point
        looped_frames = self._apply_crossfade(frames, crossfade_frames)

        # Write output video
        fourcc = cv.VideoWriter_fourcc(*'mp4v')
        out = cv.VideoWriter(output_path, fourcc, fps, (width, height))

        for frame in looped_frames:
            out.write(frame)

        out.release()

        # Re-encode with ffmpeg for better compatibility
        temp_path = output_path + ".temp.mp4"
        try:
            subprocess.run([
                'ffmpeg', '-y', '-i', output_path,
                '-c:v', 'libx264', '-profile:v', 'high',
                '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
                '-crf', '18', temp_path
            ], capture_output=True, check=True)

            Path(output_path).unlink()
            Path(temp_path).rename(output_path)
        except subprocess.CalledProcessError:
            pass  # Keep opencv version if ffmpeg fails

        return True, f"Created seamless loop with {crossfade_frames}-frame crossfade"

    def _calculate_frame_similarity(self, frame1: np.ndarray,
                                     frame2: np.ndarray) -> float:
        """Calculate similarity between two frames (0-1)"""
        cv = _load_cv2()

        # Convert to grayscale
        gray1 = cv.cvtColor(frame1, cv.COLOR_BGR2GRAY).astype(float)
        gray2 = cv.cvtColor(frame2, cv.COLOR_BGR2GRAY).astype(float)

        # Structural similarity approximation
        mean1, mean2 = np.mean(gray1), np.mean(gray2)
        std1, std2 = np.std(gray1), np.std(gray2)
        covariance = np.mean((gray1 - mean1) * (gray2 - mean2))

        C1, C2 = 6.5025, 58.5225  # Stability constants
        ssim = ((2 * mean1 * mean2 + C1) * (2 * covariance + C2)) / \
               ((mean1**2 + mean2**2 + C1) * (std1**2 + std2**2 + C2))

        return max(0, min(1, ssim))

    def _calculate_motion_continuity(self, frames: List[np.ndarray]) -> float:
        """Calculate motion continuity across loop point"""
        cv = _load_cv2()

        if len(frames) < 10:
            return 0.5

        # Calculate motion vectors near start and end
        def get_motion(f1, f2):
            gray1 = cv.cvtColor(f1, cv.COLOR_BGR2GRAY)
            gray2 = cv.cvtColor(f2, cv.COLOR_BGR2GRAY)
            diff = np.abs(gray2.astype(float) - gray1.astype(float))
            return np.mean(diff)

        # Motion at end of video
        end_motion = get_motion(frames[-2], frames[-1])

        # Motion at start of video (simulating loop)
        start_motion = get_motion(frames[-1], frames[0])

        # Motion should be similar
        if max(end_motion, start_motion) < 1:
            return 1.0  # Both static = perfect continuity

        continuity = 1 - abs(end_motion - start_motion) / max(end_motion, start_motion, 1)
        return max(0, min(1, continuity))

    def _calculate_color_consistency(self, frames: List[np.ndarray]) -> float:
        """Calculate color consistency across video"""
        if len(frames) < 2:
            return 1.0

        # Compare average color of first and last few frames
        first_avg = np.mean(frames[:3], axis=(0, 1, 2))
        last_avg = np.mean(frames[-3:], axis=(0, 1, 2))

        # Normalize difference
        diff = np.abs(first_avg - last_avg)
        max_diff = np.max(diff)

        consistency = 1 - (max_diff / 255)
        return max(0, min(1, consistency))

    def _find_optimal_loop_points(self, frames: List[np.ndarray],
                                   search_window: int = 30) -> List[LoopPoint]:
        """Find optimal frames for loop start/end"""
        cv = _load_cv2()

        loop_points = []
        total = len(frames)

        # Compare frames near start with frames near end
        for start_offset in range(min(search_window, total // 4)):
            for end_offset in range(min(search_window, total // 4)):
                start_frame = frames[start_offset]
                end_frame = frames[total - 1 - end_offset]

                similarity = self._calculate_frame_similarity(start_frame, end_frame)

                if similarity > 0.85:  # Threshold for consideration
                    # Check motion around these points
                    motion_cont = 1.0
                    if start_offset > 0 and end_offset > 0:
                        motion_cont = self._calculate_motion_continuity(
                            frames[max(0, total - 1 - end_offset - 5):] +
                            frames[:min(start_offset + 5, total)]
                        )

                    # Color match
                    color = self._calculate_color_consistency(
                        [end_frame, start_frame]
                    )

                    loop_points.append(LoopPoint(
                        frame_start=start_offset,
                        frame_end=total - 1 - end_offset,
                        similarity_score=similarity,
                        motion_continuity=motion_cont,
                        color_match=color
                    ))

        # Sort by combined score
        loop_points.sort(
            key=lambda p: p.similarity_score * 0.5 + p.motion_continuity * 0.3 + p.color_match * 0.2,
            reverse=True
        )

        return loop_points[:5]  # Top 5 candidates

    def _apply_crossfade(self, frames: List[np.ndarray],
                          crossfade_frames: int) -> List[np.ndarray]:
        """Apply crossfade at loop point for seamless transition"""

        if crossfade_frames < 1 or len(frames) < crossfade_frames * 2:
            return frames

        result = frames.copy()

        # Crossfade the last N frames with the first N frames
        for i in range(crossfade_frames):
            # Linear blend weight
            alpha = i / crossfade_frames

            # Blend end frames with start frames
            end_idx = len(frames) - crossfade_frames + i
            start_idx = i

            # Blend
            blended = cv2.addWeighted(
                frames[end_idx], 1 - alpha,
                frames[start_idx], alpha,
                0
            ) if cv2 else (
                (frames[end_idx] * (1 - alpha) + frames[start_idx] * alpha).astype(np.uint8)
            )

            result[end_idx] = blended

        return result

    def validate_spotify_canvas(self, video_path: str) -> Tuple[bool, List[str]]:
        """
        Validate video meets Spotify Canvas requirements.

        Requirements:
        - 3-8 seconds
        - 720x1280 or 1080x1920 (9:16)
        - Loops seamlessly
        - MP4 format
        """
        cv = _load_cv2()
        issues = []

        cap = cv.VideoCapture(video_path)
        if not cap.isOpened():
            return False, ["Could not open video file"]

        fps = cap.get(cv.CAP_PROP_FPS)
        frame_count = int(cap.get(cv.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv.CAP_PROP_FRAME_HEIGHT))
        cap.release()

        duration = frame_count / fps if fps > 0 else 0

        # Check duration
        if duration < 3.0:
            issues.append(f"Too short: {duration:.1f}s (minimum 3s)")
        elif duration > 8.0:
            issues.append(f"Too long: {duration:.1f}s (maximum 8s)")

        # Check aspect ratio (9:16)
        aspect = width / height if height > 0 else 0
        expected_aspect = 9 / 16

        if abs(aspect - expected_aspect) > 0.01:
            issues.append(f"Wrong aspect ratio: {width}x{height} (need 9:16)")

        # Check resolution
        valid_resolutions = [(720, 1280), (1080, 1920)]
        if (width, height) not in valid_resolutions:
            issues.append(f"Resolution {width}x{height} not optimal (use 720x1280 or 1080x1920)")

        # Check loop quality
        analysis = self.analyze_loop(video_path)
        if not analysis.is_seamless:
            issues.append(f"Loop not seamless (score: {analysis.seamlessness_score}/10)")
            issues.extend(analysis.issues)

        return len(issues) == 0, issues


# CLI for testing
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python seamless_loop.py <video_file> [--fix]")
        sys.exit(1)

    video_path = sys.argv[1]
    fix_mode = "--fix" in sys.argv

    engine = CanvasLoopEngine()

    print(f"\nAnalyzing: {video_path}")
    print("=" * 50)

    # Analyze
    analysis = engine.analyze_loop(video_path)

    print(f"Seamlessness Score: {analysis.seamlessness_score}/10")
    print(f"Is Seamless: {'YES' if analysis.is_seamless else 'NO'}")

    if analysis.issues:
        print("\nIssues:")
        for issue in analysis.issues:
            print(f"  - {issue}")

    if not analysis.is_seamless:
        print(f"\nRecommended fix:")
        print(f"  - Optimal loop: frames {analysis.optimal_loop_start} to {analysis.optimal_loop_end}")
        print(f"  - Crossfade frames: {analysis.recommended_crossfade_frames}")

        if fix_mode:
            output_path = video_path.replace(".mp4", "_looped.mp4")
            print(f"\nCreating fixed version: {output_path}")
            success, msg = engine.create_seamless_loop(
                video_path, output_path,
                analysis.recommended_crossfade_frames or 6
            )
            print(f"Result: {msg}")

    # Spotify validation
    print("\n" + "=" * 50)
    print("Spotify Canvas Validation:")
    valid, issues = engine.validate_spotify_canvas(video_path)
    print(f"Valid: {'YES' if valid else 'NO'}")
    if issues:
        for issue in issues:
            print(f"  - {issue}")
