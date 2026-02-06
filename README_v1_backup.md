# LoopCanvas — AI-Powered Music Video Generator

> **Turn a 7-second canvas into a full-length custom music video.**

LoopCanvas is a proprietary **AI video generation system** that creates $500K director-quality music videos from audio files alone. It uses **Stable Diffusion XL** for photorealistic key frames and **Stable Video Diffusion** for cinematic animation.

---

## Table of Contents

1. [Core Philosophy](#core-philosophy)
2. [Features](#features)
3. [Architecture](#architecture)
4. [Generation Modes](#generation-modes)
5. [Observed Moment Mode](#observed-moment-mode)
6. [Visual Styles](#visual-styles)
7. [Quality Validation](#quality-validation)
8. [Installation](#installation)
9. [Usage](#usage)
10. [API Reference](#api-reference)
11. [File Structure](#file-structure)
12. [Cost Analysis](#cost-analysis)

---

## Core Philosophy

### The $500K Director Insight

> **Generate footage that does not know it is being watched.**

This is the fundamental principle that separates LoopCanvas from every other music video generator. We don't create "music videos" — we create **Observed Moments**.

**What this means:**
- The footage appears to have existed independently of the music
- It would continue existing if the music were removed
- No one in frame knows they're being filmed
- The camera doesn't call attention to itself
- Motion doesn't sync to beats or rhythms
- There's no narrative arc or emotional payoff

**Why this matters:**
- Music videos that feel "designed" trigger viewer skepticism
- Authentic footage creates emotional resonance
- The best cinematographers (Lubezki, Malick, Tarkovsky) understood this
- This is what makes the difference between $500 and $500K quality

---

## Features

### Core Capabilities

| Feature | Description |
|---------|-------------|
| **AI Video Generation** | Real photorealistic footage via SDXL + SVD |
| **Spotify Canvas Ready** | 7-second seamless loops at 720x1280 |
| **Full Music Videos** | Extend canvas to track-length videos |
| **12 Visual Styles** | Cinematographer-inspired aesthetics |
| **CapCut-Style Editor** | Real-time color grading and adjustments |
| **Quality Validation** | Two-phase scoring with 9.3/10 minimum |
| **3-Tier Pipeline** | Fast local dev, quality validation, cloud production |

### What It Generates

| Output | Format | Description |
|--------|--------|-------------|
| `spotify_canvas_7s_9x16.mp4` | 720x1280, 7s | Seamless loop for Spotify Canvas |
| `spotify_canvas_web.mp4` | 720x1280, 7s | Web-optimized version |
| `full_music_video_9x16.mp4` | 720x1280, full | Full-length video synced to track |
| `concept.json` | JSON | Visual thesis, motif, act themes |
| `*_keyframe.png` | PNG | AI-generated key frame |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           LoopCanvas System                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────────┐    ┌──────────────────────────┐   │
│  │   Frontend   │───▶│    server.py     │───▶│  loopcanvas_grammy.py    │   │
│  │  index.html  │    │    (HTTP API)    │    │   (Pipeline Orchestrator)│   │
│  └──────────────┘    └──────────────────┘    └────────────┬─────────────┘   │
│         │                                                  │                 │
│         │                                                  ▼                 │
│         │                                    ┌──────────────────────────┐   │
│         │                                    │   loopcanvas_engine.py   │   │
│         │                                    │   (Style Definitions +   │   │
│         │                                    │    Observed Moment Mode) │   │
│         │                                    └────────────┬─────────────┘   │
│         │                                                  │                 │
│         │                      ┌───────────────────────────┼───────────────┐│
│         │                      │                           │               ││
│         │                      ▼                           ▼               ││
│         │         ┌─────────────────────┐    ┌─────────────────────────┐  ││
│         │         │  fast_ai_video_gen  │    │   cloud_video_gen.py    │  ││
│         │         │  (SDXL + Ken Burns) │    │   (Modal H100 GPU)      │  ││
│         │         │  ~90 sec / canvas   │    │   ~30 sec / canvas      │  ││
│         │         └─────────────────────┘    └─────────────────────────┘  ││
│         │                                                                  ││
│         └──────────────────────────────────────────────────────────────────┘│
│                            Vision OS 2 + Apple Marketing UI                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Image Generation** | Stable Diffusion XL | Photorealistic key frames |
| **Video Animation** | Stable Video Diffusion XT | 25-frame cinematic motion |
| **Post-Processing** | FFmpeg | Color grading, grain, seamless loops |
| **Cloud GPU** | Modal H100 | Production-grade rendering |
| **Frontend** | Vanilla JS + CSS | Apple-inspired glass UI |
| **Backend** | Python HTTP Server | API + file serving |

---

## Generation Modes

LoopCanvas supports **3 generation tiers** via `LOOPCANVAS_MODE` environment variable:

| Mode | Speed | Quality | Hardware | Use Case |
|------|-------|---------|----------|----------|
| `fast` | ~90 sec | SDXL + Ken Burns | Local MPS | UI iteration, demos |
| `local` | ~30 min | Full SDXL + SVD | Local CPU | Quality validation |
| `cloud` | ~30 sec | Full SDXL + SVD | H100 GPU | Production |

### Mode Details

#### Fast Mode (`LOOPCANVAS_MODE=fast`)
- SDXL generates 768x768 keyframe on Apple Silicon MPS
- FFmpeg applies Ken Burns zoom/pan motion
- Total time: ~90 seconds
- Use for: UI development, rapid iteration

#### Local Mode (`LOOPCANVAS_MODE=local`)
- SDXL generates 1024x576 keyframe on MPS
- SVD animates on CPU (memory-constrained)
- Total time: ~30-45 minutes
- Use for: Quality validation before cloud deployment

#### Cloud Mode (`LOOPCANVAS_MODE=cloud`)
- SDXL + SVD both run on H100 GPU
- 2 SVD sequences for 49 frames of unique motion
- Forward-only cross-fade for seamless loops
- Total time: ~30-60 seconds
- Cost: ~$0.10-0.15 per canvas
- Use for: Production

---

## Observed Moment Mode

### Core Directive

> **Generate footage that does not know it is being watched.**

This generator produces OBSERVED MOMENTS, not music videos. Its purpose is to generate footage that appears to have existed independently of the music, and would continue existing if the music were removed.

**Any output that feels designed, performed, presented, or optimized must be rejected.**

### Hard Rejection Flags

If ANY of these flags are triggered, the output is **instantly rejected**:

| Flag | Description | Detection |
|------|-------------|-----------|
| `FLAG_VIEWER_AWARENESS` | Eye contact, posing, performing, storytelling framing | Subject appears aware of camera |
| `FLAG_CAMERA_INTENT` | Push-ins, zooms, clever framing, perfect centering | Camera moves with purpose |
| `FLAG_MUSIC_SYNC` | BPM alignment, rhythmic cuts, energy matching | Motion syncs to audio |
| `FLAG_NARRATIVE_STRUCTURE` | Story arc, climax, emotional payoff, resolution | Feels like it's going somewhere |
| `FLAG_DIGITAL_POLISH` | Ultra-sharp, high contrast, modern clean look | Looks "professional" |
| `FLAG_ATTENTION_OPTIMIZATION` | Hooks, interesting moments, engagement tricks | Tries to be interesting |
| `FLAG_LOOP_DETECTED` | Perceptible loop boundary, direction reversal, jump | You can see where it loops |

### Scoring Axes

Each output is scored on 5 axes. All must pass their minimum threshold:

| Axis | Weight | Minimum | What It Measures |
|------|--------|---------|------------------|
| **Observer Neutrality** | ×3.0 | 1.0 | Does anyone in frame "know" they're being filmed? **BINARY** — any awareness = 0.0 |
| **Camera Humility** | ×2.5 | 0.75 | Does the camera call attention to itself? Start at 1.0, subtract 0.25 per violation |
| **Temporal Indifference** | ×2.0 | 0.80 | Does the footage acknowledge time or music? Start at 1.0, subtract 0.5 per violation |
| **Memory Texture** | ×1.5 | 0.80 | Does the image feel like memory, not documentation? Requires grain, softness, vignette |
| **Light-First Emotion** | ×1.0 | 0.75 | Does emotion come from light, not subject? Measures lighting-driven mood |

**Scoring Formula:**
```
Total = Σ(axis_score × weight) / Σ(weights) × 10.0
Minimum passing: 9.3/10.0
```

### Required Visual Qualities

If ANY of these are missing, the output is **rejected**:

1. **Observational Framing**
   - Off-center composition
   - Partial obstruction acceptable
   - Lingers past "useful" moment
   - Never perfectly composed

2. **Light as Primary Emotion**
   - Natural light drift
   - Sun flare acceptable
   - Exposure breathing
   - Light carries the mood, not subject

3. **Time Indifference**
   - Motion doesn't react to music
   - No loop acknowledgment
   - No rhythm sync
   - Feels like it would continue forever

4. **Memory Texture**
   - Film grain: `c0s=18+` (heavy)
   - Soft focus: `sigma=1.0+`
   - Reduced contrast: `0.80`
   - Muted saturation: `0.75`
   - Lifted blacks, lowered whites

### Forbidden Visual Elements

These elements will trigger **instant rejection**:

| Element | Why It's Forbidden |
|---------|-------------------|
| Pure black (#000000) | Memory doesn't have pure black |
| Pure white (#FFFFFF) | Memory doesn't have pure white |
| Neon colors (saturated cyan, magenta, lime) | Too attention-grabbing |
| High contrast (>0.90) | Too punchy, too intentional |
| Sharp focus / digital crispness | Memory isn't sharp |
| Centered subjects | Too composed, too intentional |
| Perfect symmetry | Too designed |
| Studio lighting | Too artificial |
| Specific locations (warehouses, streets) | Too literal |

### FFmpeg Post-Processing Parameters

```bash
# Color grading
eq=contrast=0.80:saturation=0.75:brightness=-0.03:gamma=1.08

# Lift blacks, lower whites (no pure black/white)
curves=master='0.08/0.12 0.25/0.28 0.5/0.5 0.75/0.72 0.92/0.88'

# Soft focus
gblur=sigma=1.2

# Heavy film grain
noise=c0s=18:c1s=12:c2s=12:c0f=t:c1f=t:c2f=t

# Strong vignette
vignette=PI/3.5:a=0.9
```

### Prompt Requirements

Prompts must be **ABSTRACT and MOOD-DRIVEN**, never literal scenes:

```python
# GOOD PROMPT:
"Warm golden light drifting across soft textured surface, dust particles
floating in amber sunbeams, gentle movement, soft focus throughout, heavy
35mm film grain, lifted shadows, muted warm tones, memory-like quality"

# BAD PROMPT:
"Warehouse with boxes and windows, figure standing in doorway"
# Why bad: Too literal, specific location, recognizable scene
```

**Every prompt MUST include:**
- Abstract lighting/atmosphere (not specific locations)
- "soft focus" and "film grain"
- "lifted shadows" (no pure black)
- "muted colors" or "desaturated"
- Natural/warm light, never studio/artificial
- NO specific objects, locations, or recognizable scenes

---

## Visual Styles

### 12 Cinematographer-Inspired Styles

| Style | Cinematographer | Visual Signature | Best For |
|-------|-----------------|------------------|----------|
| **Memory in Motion** | Emmanuel Lubezki | Golden hour warmth, dust particles, amber | Nostalgic, emotional tracks |
| **Afterglow Ritual** | Terrence Malick | Sacred ember glow, candlelight, smoke | Intimate, spiritual songs |
| **Midnight City** | Wong Kar-wai | Soft bokeh, rain reflections, muted neon | Urban, melancholic vibes |
| **Analog Memory** | Terrence Malick | Super 8 texture, light leaks, faded cream | Nostalgic, vintage feel |
| **Sunrise Departure** | Emmanuel Lubezki | Pale gradients, mist, ethereal light | Hopeful, airy tracks |
| **Desert Drive** | Andrei Tarkovsky | Heat haze, dust, earth tones, vast depth | Journey, contemplative |
| **Velvet Dark** | David Lynch | Deep shadows, lifted blacks, purple tones | Dark, mysterious songs |
| **Ghost Room** | Andrei Tarkovsky | Cold pale light, dust motes, grey-blue | Haunting, isolated moods |
| **Euphoric Drift** | Emmanuel Lubezki | Warm bloom, particles rising, peach tones | Uplifting, emotional peaks |
| **Concrete Heat** | Christopher Doyle | Harsh sunlight, rough texture, documentary | Raw, physical energy |
| **Neon Calm** | Wong Kar-wai | Soft gradients, muted cyan-magenta, minimal | Cool, modern atmosphere |
| **Peak Transmission** | Christopher Doyle | Red-gold pulses, controlled energy, amber | High-energy climax |

### Style Selection

Styles are automatically selected based on audio analysis:
- **BPM** — Tempo influences energy level
- **Key** — Major/minor affects warmth
- **Mood tags** — CLAP semantic analysis
- **Energy curve** — Dynamic range mapping

---

## Quality Validation

### Two-Phase Validation

Every output goes through two validation phases:

#### Phase 1: Observed Moment Authenticity (9.3/10.0 minimum)

| Axis | Weight | Minimum | Fail Condition |
|------|--------|---------|----------------|
| Observer Neutrality | ×3.0 | 1.0 | Any viewer awareness |
| Camera Humility | ×2.5 | 0.75 | Camera feels smart |
| Temporal Indifference | ×2.0 | 0.80 | Syncs to music |
| Memory Texture | ×1.5 | 0.80 | Too clean/sharp |
| Light-First Emotion | ×1.0 | 0.75 | Subject-driven emotion |

#### Phase 2: Technical Quality (95/100 minimum)

| Criterion | Weight | Description |
|-----------|--------|-------------|
| Thesis Coherence | 15 | Visual concept holds throughout |
| Look Adherence | 10 | Cinematographer style consistent |
| Motif Recurrence | 10 | Visual themes repeat naturally |
| Phrase Editing | 15 | Cuts respect musical phrases |
| Shot Grammar | 10 | Professional composition rules |
| Breath & Restraint | 15 | Empty space, slow moments |
| Iconic Frames | 5 | At least one memorable still |
| Canvas Loop | 10 | Seamless 7s loop |
| Arc Progression | 5 | Subtle build over duration |
| Anti-Stock | 5 | Never feels generic |

### Validation Outcomes

| Outcome | Action |
|---------|--------|
| Both phases pass | Output delivered |
| Phase 1 fails | Regenerate with adjusted parameters |
| Phase 2 fails | Regenerate with different prompt |
| Hard flag triggered | Instant reject, regenerate |

---

## Installation

### Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| macOS | Apple Silicon (M1+) | M2 Pro or better |
| RAM | 32GB | 64GB |
| Python | 3.11+ | 3.11 |
| FFmpeg | 7.0+ | Latest |
| Storage | 50GB | 100GB |

### Python Dependencies

```bash
pip install torch diffusers transformers accelerate pillow librosa modal numpy scipy soundfile tqdm
```

### FFmpeg Installation

```bash
brew install ffmpeg
```

### Modal Setup (for cloud mode)

```bash
pip install modal
modal token new
modal deploy cloud_video_gen.py
```

---

## Usage

### Quick Start

```bash
# Fast mode for development (default)
cd loopcanvas_app
LOOPCANVAS_MODE=fast python3 server.py

# Open in browser
open http://localhost:8888
```

### CLI Usage

```bash
# Generate from audio file
python3 loopcanvas_grammy.py --audio "track.mp3" --out output_dir

# Options
--style STYLE    # Override visual style (e.g., memory_in_motion)
--dry_run        # Generate concept only, skip rendering
--ai_shots N     # Number of AI-generated clips (default: 3)
--regen_limit N  # Regeneration attempts per clip (default: 2)
```

### Production Deployment

```bash
# Deploy to Modal (cloud GPU)
modal deploy cloud_video_gen.py

# Run with cloud backend
LOOPCANVAS_MODE=cloud python3 server.py
```

---

## API Reference

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/upload` | POST | Upload audio file |
| `/api/generate` | POST | Start AI generation job |
| `/api/regenerate` | POST | Regenerate with parameters |
| `/api/status/{job_id}` | GET | Check job status |
| `/cms/moods.json` | GET | Get mood library |

### Upload Request

```json
POST /api/upload
Content-Type: multipart/form-data

file: <audio_file>
```

### Generate Request

```json
POST /api/generate
Content-Type: application/json

{
  "job_id": "abc123"
}
```

### Status Response

```json
{
  "status": "complete",
  "progress": 100,
  "outputs": {
    "canvas": "/outputs/abc123/spotify_canvas_web.mp4",
    "full_video": "/outputs/abc123/full_music_video_9x16.mp4",
    "concept": "/outputs/abc123/concept.json"
  },
  "track_info": {
    "theme": "longing",
    "thesis": "Visual thesis statement..."
  }
}
```

---

## File Structure

```
loopcanvas_app/
├── index.html              # Main web UI with CapCut editor
├── admin.html              # CMS admin panel
├── server.py               # Python backend
├── cms/
│   └── moods.json          # Mood preset data
├── mood_demos/             # Pre-generated demo videos
├── uploads/                # Uploaded audio files
└── outputs/                # Generated videos

/Developer/
├── loopcanvas_engine.py    # AI video generation engine
├── loopcanvas_grammy.py    # Grammy-grade pipeline
├── fast_ai_video_gen.py    # SDXL + Ken Burns (fast mode)
├── cloud_video_gen.py      # Modal H100 deployment (cloud mode)
├── generate_cloud_demos.py # Batch demo regeneration
├── validate_demos.py       # Quality validation runner
├── optimize_observed_moment.py  # Auto-optimization loop
└── LOOPCANVAS_MASTER_PLAN.md    # Development journey
```

### Core Files

| File | Purpose |
|------|---------|
| `loopcanvas_engine.py` | Style definitions, fingerprinting, Observed Moment Mode |
| `loopcanvas_grammy.py` | Full pipeline: transcription → concept → assets → render |
| `fast_ai_video_gen.py` | FastCinematicGenerator (SDXL + Ken Burns motion) |
| `cloud_video_gen.py` | VideoGenerator class for Modal H100 deployment |
| `server.py` | HTTP server with threading, API endpoints, job management |

---

## Cost Analysis

### Cloud Mode Economics

| Volume | Cost/Canvas | Monthly | Margin at $4.99 |
|--------|-------------|---------|-----------------|
| 100 canvases | $0.12 | $12 | 97.6% |
| 1,000 canvases | $0.10 | $100 | 98.0% |
| 10,000 canvases | $0.08 | $800 | 98.4% |

### Time Investment

| Mode | Time/Canvas | Best For |
|------|-------------|----------|
| Fast | ~90 sec | Development |
| Local | ~30 min | Validation |
| Cloud | ~30 sec | Production |

---

## What Makes This $500K Quality

1. **Real AI video** — SDXL + SVD, not procedural particles
2. **Observed Moment Mode** — Footage that doesn't know it's being watched
3. **Cinematographer prompts** — Inspired by Lubezki, Wong Kar-wai, Tarkovsky, Malick
4. **No fallbacks** — AI required, old generator removed
5. **Strict validation** — Two-phase quality gates (9.3/10 minimum)
6. **Photorealistic output** — Indistinguishable from professional footage
7. **Memory texture** — Heavy grain, soft focus, muted colors
8. **Forward-only loops** — No perceptible direction reversal
9. **49 frames of unique motion** — 2 SVD sequences, not 14
10. **Abstract prompts** — Mood-driven, never literal scenes

---

## License

Proprietary. All rights reserved.

---

*Built with LoopCanvas Proprietary AI Engine v3.0*
*Powered by Stable Diffusion XL + Stable Video Diffusion*
*Production: Modal H100 Cloud GPU*
*Philosophy: Generate footage that does not know it is being watched.*
