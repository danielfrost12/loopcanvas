#!/usr/bin/env python3
"""
Regenerate all 12 mood demos using the $500K Director-Grade Engine.

Maps audio files to visual styles and generates fresh demos.
"""

import sys
from pathlib import Path

# Add parent directory for engine import
sys.path.insert(0, str(Path(__file__).parent.parent))

from loopcanvas_engine import SongFingerprint, generate_unique_clip

# Audio file to style mapping
# Using available audio_demos files
DEMO_MAPPING = {
    "memory_in_motion": {
        "audio": "audio_demos/memory_in_motion_audio.m4a",
        "title": "Memory in Motion",
        "bpm": 122,
        "key": "Am"
    },
    "afterglow_ritual": {
        "audio": "audio_demos/rise_shine.mp3",
        "title": "Afterglow Ritual",
        "bpm": 120,
        "key": "Dm"
    },
    "midnight_city": {
        "audio": "audio_demos/night_city.mp3",
        "title": "Midnight City Pulse",
        "bpm": 126,
        "key": "Fm"
    },
    "analog_memory": {
        "audio": "audio_demos/atmospheric_techno.mp3",
        "title": "Analog Memory",
        "bpm": 118,
        "key": "Gm"
    },
    "sunrise_departure": {
        "audio": "audio_demos/ambient_sunrise.mp3",
        "title": "Sunrise Departure",
        "bpm": 115,
        "key": "C"
    },
    "desert_drive": {
        "audio": "audio_demos/water_sand.mp3",
        "title": "Desert Drive",
        "bpm": 124,
        "key": "Em"
    },
    "velvet_dark": {
        "audio": "audio_demos/end_of_night.mp3",
        "title": "Velvet Dark",
        "bpm": 120,
        "key": "Cm"
    },
    "ghost_room": {
        "audio": "audio_demos/ocean_deep.mp3",
        "title": "Ghost Room",
        "bpm": 110,
        "key": "Bm"
    },
    "euphoric_drift": {
        "audio": "audio_demos/brave_world.mp3",
        "title": "Euphoric Drift",
        "bpm": 128,
        "key": "F"
    },
    "concrete_heat": {
        "audio": "audio_demos/deep_house_congo.mp3",
        "title": "Concrete Heat",
        "bpm": 125,
        "key": "Gm"
    },
    "neon_calm": {
        "audio": "audio_demos/cool_quiet.mp3",
        "title": "Neon Calm",
        "bpm": 118,
        "key": "Am"
    },
    "peak_transmission": {
        "audio": "audio_demos/soulful_afro_house_full.mp3",
        "title": "Peak Transmission",
        "bpm": 124,
        "key": "Dm"
    },
}


def regenerate_all_demos():
    """Regenerate all mood demos with the $500K engine."""
    base_dir = Path(__file__).parent
    output_dir = base_dir / "mood_demos"
    output_dir.mkdir(exist_ok=True)

    print("=" * 60)
    print("REGENERATING ALL MOOD DEMOS WITH $500K ENGINE")
    print("=" * 60)

    success_count = 0
    fail_count = 0

    for style_name, config in DEMO_MAPPING.items():
        audio_path = base_dir / config["audio"]
        output_path = output_dir / f"{style_name}_demo.mp4"

        print(f"\n[{style_name}] {config['title']}")
        print(f"  Audio: {audio_path}")
        print(f"  Output: {output_path}")

        if not audio_path.exists():
            print(f"  ❌ SKIPPED - Audio file not found")
            fail_count += 1
            continue

        try:
            # Create fingerprint for this style
            fingerprint = SongFingerprint.from_grammy_data(
                audio_path=str(audio_path),
                concept_thesis=f"{config['title']} - Director-grade demo",
                bpm=config["bpm"],
                key=config["key"],
                duration=7.4,
                style=style_name
            )

            # Generate the clip
            result = generate_unique_clip(
                out_path=output_path,
                fingerprint=fingerprint,
                shot_type="A_motif",
                act=1,
                duration=7.4,
                fps=30,
                w=720,  # Spotify Canvas spec
                h=1280,
                enforce_observed_moment=True
            )

            if result and result.exists():
                file_size = result.stat().st_size / 1024
                print(f"  ✅ SUCCESS - {file_size:.0f} KB")
                success_count += 1
            else:
                print(f"  ❌ FAILED - No output generated")
                fail_count += 1

        except Exception as e:
            print(f"  ❌ ERROR - {e}")
            fail_count += 1

    print("\n" + "=" * 60)
    print(f"COMPLETE: {success_count} succeeded, {fail_count} failed")
    print("=" * 60)


if __name__ == "__main__":
    regenerate_all_demos()
