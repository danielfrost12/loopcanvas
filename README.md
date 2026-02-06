# LoopCanvas v2.0 — Canvas Agent Army

> **What if the AI understood your music the way a director does?**

> Canvas doesn't pick a filter. It extracts emotional DNA from your audio, assigns a director philosophy, and generates footage that doesn't know it's being watched.

LoopCanvas is a proprietary AI video generation system that creates director-quality Spotify Canvas loops and full-length music videos from audio files alone. Upload a track. Get a 7-second masterpiece. Expand it into a complete visual album.

v2.0 integrates the **Canvas Agent Army** — a self-optimizing orchestration layer with Audio Intelligence, Director Philosophy, Quality Gate, Real-Time Iteration, Intent Editing, Multi-Platform Export, and a continuous optimization seed runner that improves output quality 24/7 with zero human input.

---

## Table of Contents

1. [Architecture](#architecture)
2. [v2.0 Pipeline](#v20-pipeline)
3. [Canvas Engine Modules](#canvas-engine-modules)
4. [API Reference](#api-reference)
5. [Observed Moment Mode](#observed-moment-mode)
6. [Visual Styles](#visual-styles)
7. [7 Patentable Innovations](#7-patentable-innovations)
8. [Installation](#installation)
9. [Usage](#usage)
10. [Cost Analysis](#cost-analysis)

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     LoopCanvas v2.0 System                        │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌──────────┐   ┌──────────────────────────────────────────────┐ │
│  │ Frontend  │──▶│              server.py v2.0                  │ │
│  │index.html │   │   v1 API + v2 API (12 endpoints)            │ │
│  └──────────┘   └─────────────────┬────────────────────────────┘ │
│                                    │                               │
│                    ┌───────────────▼───────────────┐              │
│                    │    canvas-engine/              │              │
│                    │    orchestrator.py             │              │
│                    │    (Master Orchestrator)       │              │
│                    └───┬───┬───┬───┬───┬───┬───┬──┘              │
│                        │   │   │   │   │   │   │                  │
│  ┌─────────┐  ┌───────┴┐ ┌┴──┐│┌──┴─┐│┌──┴─┐ │ ┌────────────┐ │
│  │  Cost   │  │ Audio  ││ │Dir││ │Qual││ │Loop│ │ │  Iterator  │ │
│  │Enforcer │  │ Intel  ││ │Eng││ │Gate││ │Eng │ │ │  (< 3 sec) │ │
│  └─────────┘  └────────┘│ └───┘│ └────┘│ └────┘ │ └────────────┘ │
│                          │      │       │        │                 │
│              ┌───────────┴┐  ┌──┴──┐  ┌─┴──────┐│                │
│              │   Visual   │  │Edit │  │ Export  ││                │
│              │  Generator │  │(NL) │  │(Multi) ││                │
│              └────────────┘  └─────┘  └────────┘│                │
│                                                   │                │
│  ┌────────────────────────────────────────────────┘               │
│  │  Pipeline: loopcanvas_grammy.py + loopcanvas_engine.py         │
│  │  Generation: SDXL + SVD (Fast/Local/Cloud)                     │
│  └────────────────────────────────────────────────────────────────┤
│                    $0 Cost Ceiling Until Revenue                    │
└──────────────────────────────────────────────────────────────────┘
```

---

## v2.0 Pipeline — Canvas Engine

The Canvas Engine is a full-screen 5-stage processing experience:

| Stage | Module | What Happens | Time |
|-------|--------|-------------|------|
| **1. Upload** | server.py | Artist drops a track | instant |
| **2. Feel** | Audio Intelligence | Extract emotional DNA (BPM, key, energy, valence, warmth) | ~10 sec |
| **3. Direct** | Philosophy Engine | Match to director (Lubezki, Spike Jonze, Wong Kar-wai...) — artist picks | ~3 sec + choice |
| **4. Generate** | SDXL + SVD + Grammy Pipeline | Generate canvas with selected director philosophy | 30-90 sec |
| **5. Validate** | Quality Gate (9.3/10 min) | Score on 6 axes, reject AI artifacts, verify loop seamlessness | ~5 sec |

After validation, the artist enters the **Editor Workspace**:

| Feature | Module | Description | Time |
|---------|--------|-------------|------|
| **Iterate** | Real-Time Iterator | "Make it warmer" → sub-3-second FFmpeg adjustments | < 3 sec |
| **Edit** | Intent Editor | "Cut the intro" → natural language video editing | < 10 sec |
| **Expand** | Grammy Pipeline | 7s canvas becomes a full-length music video | 5-10 min |
| **Export** | Multi-Platform Exporter | Spotify, Instagram, TikTok, YouTube, Apple Music, X | ~15 sec |

### Self-Optimization (Seed Runner)

The **Seed Runner** bootstraps the system from day one — no waiting for user uploads:

1. Discovers all audio files in the library
2. Runs every track through all 9 director styles
3. Quality gate scores every output
4. Optimization loop analyzes patterns and evolves parameters
5. Next batch uses evolved params — the system gets better every cycle

After ~50 generations, LoopCanvas converges on optimal params per genre/mood.

---

## Canvas Engine Modules

All modules live in `canvas-engine/`:

| Module | File | Patent # | Status |
|--------|------|----------|--------|
| **Orchestrator** | `orchestrator.py` | — | Active |
| **Cost Enforcer** | `agents/cost_enforcer.py` | — | Active |
| **Audio Intelligence** | `audio/audio_analyzer.py` | #1 | Active |
| **Director Philosophy** | `director/philosophy_engine.py` | #2 | Active |
| **Seamless Loop** | `loop/seamless_loop.py` | #3 | Active |
| **Real-Time Iteration** | `iteration/realtime_iterator.py` | #4 | Active |
| **Multi-Platform Export** | `export/multi_platform.py` | #5 | Active |
| **Intent-Based Editing** | `editor/intent_editor.py` | #6 | Active |
| **Quality Gate** | `quality_gate/ai_detector.py` | #7 | Active |
| **Seed Runner** | `agents/seed_runner.py` | — | Active |
| **Optimization Loop** | `agents/optimization_loop.py` | — | Active |
| **Visual Generator** | `visual/visual_generator.py` | — | Active |

---

## API Reference

### v1 Endpoints (preserved)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/upload` | POST | Upload audio file |
| `/api/generate` | POST | Start generation (direct pipeline) |
| `/api/regenerate` | POST | Regenerate with parameters |
| `/api/status/{job_id}` | GET | Check job status |
| `/api/cms/save` | POST | Save CMS data |

### v2 Endpoints (new)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v2/analyze` | POST | Extract emotional DNA + generate visual directions |
| `/api/v2/directions/{job_id}` | GET | Get visual directions for a job |
| `/api/v2/select` | POST | Select direction, start generation |
| `/api/v2/iterate` | POST | Real-time adjustment (< 3 sec) |
| `/api/v2/edit` | POST | Intent-based video editing |
| `/api/v2/export` | POST | Multi-platform export |
| `/api/v2/platforms` | GET | List supported platforms |
| `/api/v2/cost-report` | GET | Cost enforcement status |
| `/api/v2/status/{job_id}` | GET | Full v2 job status |
| `/api/v2/undo` | POST | Undo last iteration |
| `/api/v2/queue/claim` | POST | GPU worker claims next job |
| `/api/v2/queue/progress` | POST | Worker reports progress |
| `/api/v2/queue/complete` | POST | Worker marks job complete |
| `/api/v2/queue/submit` | POST | Submit job to distributed queue |
| `/api/v2/queue/stats` | GET | Queue health metrics |
| `/api/v2/seed/status` | GET | Seed runner optimization status |

### v2 Flow Example

```bash
# 1. Upload
curl -X POST http://localhost:8888/api/upload -F "file=@track.mp3"
# → {"job_id": "abc123"}

# 2. Analyze (emotional DNA + directions)
curl -X POST http://localhost:8888/api/v2/analyze -d '{"job_id":"abc123"}'
# → {"emotional_dna": {...}, "directions": [{...}, {...}, ...]}

# 3. Select direction
curl -X POST http://localhost:8888/api/v2/select \
  -d '{"job_id":"abc123", "direction_id":"dir_0_spike_jonze"}'
# → {"status": "generating"}

# 4. Poll status
curl http://localhost:8888/api/v2/status/abc123
# → {"status": "complete", "outputs": {"canvas": "/outputs/abc123/..."}}

# 5. Iterate
curl -X POST http://localhost:8888/api/v2/iterate \
  -d '{"job_id":"abc123", "adjustment":"make it warmer"}'
# → {"elapsed_seconds": 1.8, "outputs": {...}}

# 6. Export
curl -X POST http://localhost:8888/api/v2/export \
  -d '{"job_id":"abc123", "platforms":["spotify_canvas","instagram_reels"]}'
# → {"exports": {"spotify_canvas": {...}, "instagram_reels": {...}}}
```

---

## Observed Moment Mode

> **Generate footage that does not know it is being watched.**

### Hard Rejection Flags

| Flag | Trigger |
|------|---------|
| `FLAG_VIEWER_AWARENESS` | Subject appears aware of camera |
| `FLAG_CAMERA_INTENT` | Camera moves with purpose |
| `FLAG_MUSIC_SYNC` | Motion syncs to audio |
| `FLAG_NARRATIVE_STRUCTURE` | Feels like it's going somewhere |
| `FLAG_DIGITAL_POLISH` | Looks "professional" |
| `FLAG_ATTENTION_OPTIMIZATION` | Tries to be interesting |
| `FLAG_LOOP_DETECTED` | Perceptible loop boundary |

### Quality Scoring

| Axis | Weight | Minimum |
|------|--------|---------|
| Observer Neutrality | x3.0 | 1.0 (binary) |
| Camera Humility | x2.5 | 0.75 |
| Temporal Indifference | x2.0 | 0.80 |
| Memory Texture | x1.5 | 0.80 |
| Light-First Emotion | x1.0 | 0.75 |

**Minimum passing score: 9.3/10**

---

## Visual Styles

### 12 Cinematographer-Inspired Styles

| Style | Reference | Best For |
|-------|-----------|----------|
| Memory in Motion | Lubezki | Nostalgic, emotional |
| Afterglow Ritual | Malick | Intimate, spiritual |
| Midnight City | Wong Kar-wai | Urban, melancholic |
| Analog Memory | Malick | Nostalgic, vintage |
| Sunrise Departure | Lubezki | Hopeful, airy |
| Desert Drive | Tarkovsky | Journey, contemplative |
| Velvet Dark | Lynch | Dark, mysterious |
| Ghost Room | Tarkovsky | Haunting, isolated |
| Euphoric Drift | Lubezki | Uplifting, peaks |
| Concrete Heat | Doyle | Raw, physical |
| Neon Calm | Wong Kar-wai | Cool, modern |
| Peak Transmission | Doyle | High-energy |

### Director Philosophy Engine (v2.0)

| Director | Philosophy | Emotional Approach |
|----------|-----------|-------------------|
| Spike Jonze | Beauty in vulnerability | Sincere without sentiment |
| Hype Williams | Mundane made mythological | Emotion as power |
| Dave Meyers | Controlled chaos | Energy as emotion |
| The Daniels | Absurdist emotion | Comedy and tragedy coexist |
| Khalil Joseph | Poetic intimacy | Impressionistic accumulation |
| Wong Kar-wai | Romantic longing | Melancholic beauty |

---

## 7 Patentable Innovations

**Status: DOCUMENTATION ONLY — DO NOT FILE WITHOUT FOUNDER AUTHORIZATION**

| # | Innovation | Module | Filing Cost |
|---|-----------|--------|-------------|
| 1 | Emotional Audio Decomposition | `audio/audio_analyzer.py` | $320 |
| 2 | Director DNA Visual Synthesis | `director/philosophy_engine.py` | $320 |
| 3 | Seamless Loop Generation | `loop/seamless_loop.py` | $320 |
| 4 | Real-Time Iteration Protocol | `iteration/realtime_iterator.py` | $320 |
| 5 | Multi-Platform Adaptive Export | `export/multi_platform.py` | $320 |
| 6 | Intent-Based Video Editing | `editor/intent_editor.py` | $320 |
| 7 | Quality Authentication System | `quality-gate/ai_detector.py` | $320 |

**Total when ready: $2,240** (micro entity rate)

---

## Installation

### Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| macOS | Apple Silicon (M1+) | M2 Pro+ |
| RAM | 32GB | 64GB |
| Python | 3.11+ | 3.11 |
| FFmpeg | 7.0+ | Latest |

### Setup

```bash
# Dependencies
pip install torch diffusers transformers accelerate pillow librosa numpy scipy tqdm

# Optional: Essentia for advanced audio analysis
pip install essentia

# FFmpeg
brew install ffmpeg

# Run server
cd loopcanvas_app
python3 server.py
# → http://localhost:8888
```

---

## Usage

### Quick Start (v2 pipeline)

```bash
# Start server
LOOPCANVAS_MODE=fast python3 server.py

# Open browser
open http://localhost:8888
```

### Generation Modes

| Mode | Speed | Cost | Use Case |
|------|-------|------|----------|
| `fast` | ~90 sec | $0 | Development, iteration |
| `local` | ~30 min | $0 | Quality validation |
| `cloud` | ~30 sec | $0.10-0.15 | Production (blocked until revenue) |

---

## Cost Analysis

### $0 Rule

All compute costs are $0 until revenue exceeds $0. The Cost Enforcer blocks any paid API calls.

| Service | Status | Alternative |
|---------|--------|-------------|
| OpenAI/Anthropic | BLOCKED | Llama 3.1 8B (self-hosted) |
| Replicate | BLOCKED | Modal (free credits) |
| AWS | BLOCKED | Vercel (free tier) |
| Hosting | FREE | Vercel free tier |
| Database | FREE | Supabase free tier |
| Auth | FREE | Clerk free tier |

---

## File Structure

```
loopcanvas_app/
├── server.py                   # v2.0 server (v1 + v2 API)
├── index.html                  # Frontend UI
├── admin.html                  # CMS admin
├── canvas-engine/
│   ├── orchestrator.py         # Master orchestrator
│   ├── quality_gate_wrapper.py # QG bridge
│   ├── agent-config.yaml       # Agent army config
│   ├── agents/
│   │   ├── cost_enforcer.py    # $0 rule enforcement
│   │   ├── seed_runner.py      # Continuous optimization bootstrap
│   │   └── optimization_loop.py # Self-improving parameter evolution
│   ├── audio/
│   │   └── audio_analyzer.py   # Emotional DNA extraction
│   ├── director/
│   │   └── philosophy_engine.py # Director style engine
│   ├── visual/
│   │   └── visual_generator.py # SDXL/SVD bridge
│   ├── quality_gate/
│   │   ├── __init__.py
│   │   └── ai_detector.py      # AI artifact detection (9.3/10 gate)
│   ├── loop/
│   │   └── seamless_loop.py    # Loop perfection
│   ├── iteration/
│   │   └── realtime_iterator.py # < 3 sec adjustments
│   ├── editor/
│   │   └── intent_editor.py    # NL video editing
│   ├── export/
│   │   └── multi_platform.py   # All-platform export
│   └── patents/
│       └── PATENT_PORTFOLIO.md # 7 innovations documented
├── cms/
│   └── moods.json              # Mood library
├── deploy/
│   ├── hf_spaces_worker/       # HuggingFace Spaces GPU worker (free T4)
│   │   ├── app.py              # Gradio dashboard + job processor
│   │   └── requirements.txt
│   └── supabase_migration.sql  # Distributed queue schema
├── uploads/                    # Uploaded audio
├── outputs/                    # Generated canvases
└── seed_outputs/               # Seed runner optimization data

/Developer/
├── loopcanvas_engine.py        # Core AI engine
├── loopcanvas_grammy.py        # Grammy-grade pipeline
├── fast_ai_video_gen.py        # Fast mode generator
├── cloud_video_gen.py          # Cloud mode (Modal H100)
└── LOOPCANVAS_MASTER_PLAN.md   # Development journey
```

---

## Autonomous Engineering Agents

Three autonomous agents run daily via GitHub Actions, analyze real user metrics, and ship product improvements **without human intervention**. All changes auto-deploy via Vercel.

### Architecture

```
GitHub Actions (3am UTC daily)
  ├── optimize (existing quality loop)
  ├── retention_engineer → retention_config.json + templates/
  ├── onboarding_optimizer → onboarding_config.json + landing_config.json + templates/
  ├── growth_engineer → growth_config.json + templates/
  ├── master-checklist (weekly eval)
  └── quality-report
```

**Pipeline:** Read JSONL metrics → Analyze → Write config JSON + HTML templates → Git commit → Vercel auto-deploys → Frontend reads configs on page load → Features go live

### Agents

| Agent | Target | Metric | Method |
|-------|--------|--------|--------|
| **RetentionEngineer** | 0% → 30% retention | `return_rate` | Gallery, return banners, share modal, batch teasers |
| **OnboardingOptimizer** | Reduce funnel drop-off | `bounce_rate`, `conversion` | Smart tooltips, landing A/B tests, demo-first flow, mobile optimization |
| **GrowthEngineer** | K-factor 0.0 → 0.5 | `k_factor` | Share buttons, referral bonuses, social proof, public gallery |

### Phase-Based Progressive Rollout

Each agent has 4 phases that auto-enable based on real metrics:
- **Phase 1 (Foundation):** Gallery + return banner + copy link (always on)
- **Phase 2 (Engagement):** Share modal + referral bonus + platform sharing
- **Phase 3 (Growth):** A/B testing + social proof + watermark branding
- **Phase 4 (Optimization):** Public gallery + smart prompts + fine-tuning

### Frontend Integration

- `/api/configs` — Serves merged config JSON to frontend
- `/api/track` — Receives funnel events (page_load, upload, generate, export, share)
- `templates/` — HTML components injected into DOM at runtime
- All persistence via `localStorage` — no backend database needed

### Files

```
canvas-engine/agents/
├── retention_engineer.py     # Retention 0%→30%
├── onboarding_optimizer.py   # Funnel optimization + mobile
├── growth_engineer.py        # Viral K-factor 0→0.5
├── optimization_loop.py      # Quality self-optimization (existing)
└── weekly_checklist.py       # Part VII master checklist (existing)

api/
├── configs.py                # Config serving endpoint
└── track.py                  # Event tracking endpoint

templates/
├── gallery_component.html    # Project gallery
├── return_banner.html        # Welcome back banner
├── share_modal.html          # Share/export modal
├── onboarding_tips.html      # Smart tooltips
├── landing_hero_variant.html # A/B test hero variants
└── growth_share.html         # Viral share mechanics

*_config.json                 # Agent-written configs (auto-updated daily)
```

### Cost

$0. GitHub Actions free tier (2,000 min/month, uses ~10 min/day). Vercel free tier. JSONL files. localStorage.

---

## License

Proprietary. All rights reserved.

---

*LoopCanvas v2.0 — Canvas Agent Army*
*7 Patentable Innovations. $0 Cost Ceiling. 9.3/10 Quality Minimum.*
*Philosophy: Generate footage that does not know it is being watched.*
