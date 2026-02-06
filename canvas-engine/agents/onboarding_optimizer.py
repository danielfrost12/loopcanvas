#!/usr/bin/env python3
"""
Onboarding Optimizer — Autonomous UX Agent

Reduces drop-off in the upload → generate → export funnel by analyzing
where users abandon, then shipping config changes that improve each stage.

Capabilities:
- Funnel analysis: identifies biggest drop-off point
- Smart tooltips: adjusts which tips show at which stage
- Demo-first flow: shows pre-generated canvases when GPU unavailable
- Landing page A/B testing: rotates hero variants, CTA copy, section order
- Progress celebration: canvas completion animations + share prompts

Runs daily via GitHub Actions. Changes auto-deploy via Vercel. $0 cost.
"""

import os
import json
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field

# ─── Paths ──────────────────────────────────────────────────────────
ENGINE_DIR = Path(__file__).parent.parent
APP_DIR = ENGINE_DIR.parent
DATA_DIR = ENGINE_DIR / "checklist_data"
TEMPLATE_DIR = APP_DIR / "templates"
ONBOARDING_CONFIG_PATH = APP_DIR / "onboarding_config.json"
LANDING_CONFIG_PATH = APP_DIR / "landing_config.json"

DATA_DIR.mkdir(exist_ok=True)
TEMPLATE_DIR.mkdir(exist_ok=True)


# ─── Funnel Stages ─────────────────────────────────────────────────
FUNNEL_STAGES = [
    "page_load",
    "upload_start",
    "upload_complete",
    "analyze_start",
    "director_select",
    "generate_start",
    "generate_complete",
    "export",
]


# ─── Data Models ────────────────────────────────────────────────────
@dataclass
class FunnelMetrics:
    """Conversion rates between each funnel stage"""
    stage_counts: Dict[str, int] = field(default_factory=dict)
    stage_rates: Dict[str, float] = field(default_factory=dict)
    biggest_dropoff: str = ""
    biggest_dropoff_rate: float = 0.0
    overall_conversion: float = 0.0
    avg_time_to_export: float = 0.0
    bounce_rate: float = 0.0
    demo_conversion: float = 0.0
    # Mobile-specific metrics
    mobile_ratio: float = 0.0  # % of traffic from mobile
    mobile_bounce_rate: float = 0.0
    mobile_conversion: float = 0.0
    mobile_biggest_dropoff: str = ""
    mobile_biggest_dropoff_rate: float = 0.0


@dataclass
class OnboardingDecision:
    """What the optimizer decided to change"""
    timestamp: str = ""
    bottleneck: str = ""
    action_taken: str = ""
    config_changes: Dict = field(default_factory=dict)
    landing_changes: Dict = field(default_factory=dict)
    reasoning: str = ""
    metrics_snapshot: Dict = field(default_factory=dict)


# ─── Templates ──────────────────────────────────────────────────────
ONBOARDING_TIPS_TEMPLATE = """<!-- Onboarding Tips — Injected by Onboarding Optimizer -->
<div id="lc-onboarding-tips" style="display:none;">
  <style>
    .lc-tip-overlay {
      position: fixed;
      z-index: 9999;
      pointer-events: none;
      opacity: 0;
      transition: opacity 0.4s ease;
    }
    .lc-tip-overlay.active {
      opacity: 1;
      pointer-events: auto;
    }
    .lc-tip-bubble {
      background: rgba(29,185,84,0.95);
      color: white;
      font-family: 'Inter', sans-serif;
      font-size: 13px;
      line-height: 1.4;
      padding: 12px 16px;
      border-radius: 12px;
      max-width: 280px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.3);
      position: relative;
    }
    .lc-tip-bubble::after {
      content: '';
      position: absolute;
      bottom: -6px;
      left: 24px;
      width: 12px;
      height: 12px;
      background: rgba(29,185,84,0.95);
      transform: rotate(45deg);
    }
    .lc-tip-dismiss {
      display: inline-block;
      margin-top: 8px;
      font-size: 11px;
      opacity: 0.7;
      cursor: pointer;
      pointer-events: auto;
    }
    .lc-tip-dismiss:hover { opacity: 1; }
    .lc-tip-step {
      font-size: 10px;
      opacity: 0.6;
      margin-bottom: 4px;
    }
  </style>
</div>
<script>
(function() {
  const TIPS = {
    'upload': {
      text: 'Drop any audio file here — MP3, WAV, FLAC all work. We analyze the mood automatically.',
      target: '.upload-zone, #upload-area, [data-upload]',
      step: '1 of 4'
    },
    'analyzing': {
      text: 'Our AI is listening to your track — detecting tempo, energy, mood, and emotional arc.',
      target: '.analysis-status, #analysis-progress',
      step: '2 of 4'
    },
    'directors': {
      text: 'Each director has a unique visual philosophy. Pick the one that matches your vision.',
      target: '.director-grid, #direction-picker',
      step: '3 of 4'
    },
    'generating': {
      text: 'Your canvas is being crafted. This takes about 20-30 seconds for the best quality.',
      target: '.generation-progress, #generate-status',
      step: '3 of 4'
    },
    'export': {
      text: 'Download your Spotify Canvas-ready video. It loops perfectly!',
      target: '.export-modal, #export-section',
      step: '4 of 4'
    }
  };

  window.lcShowTip = function(stage) {
    const tip = TIPS[stage];
    if (!tip) return;

    // Don't show if user dismissed tips
    if (localStorage.getItem('lc_tips_dismissed') === 'true') return;
    
    // Don't show same tip twice in a session
    const shown = JSON.parse(sessionStorage.getItem('lc_tips_shown') || '[]');
    if (shown.includes(stage)) return;

    // Remove existing tips
    document.querySelectorAll('.lc-tip-overlay').forEach(el => el.remove());

    const overlay = document.createElement('div');
    overlay.className = 'lc-tip-overlay';
    overlay.innerHTML = \`
      <div class="lc-tip-bubble">
        <div class="lc-tip-step">Step \${tip.step}</div>
        \${tip.text}
        <div class="lc-tip-dismiss" onclick="this.closest('.lc-tip-overlay').remove()">Got it ✓</div>
      </div>
    \`;

    // Position near target element
    const target = document.querySelector(tip.target);
    if (target) {
      const rect = target.getBoundingClientRect();
      overlay.style.position = 'fixed';
      overlay.style.top = (rect.top - 80) + 'px';
      overlay.style.left = rect.left + 'px';
    } else {
      overlay.style.position = 'fixed';
      overlay.style.bottom = '100px';
      overlay.style.left = '50%';
      overlay.style.transform = 'translateX(-50%)';
    }

    document.body.appendChild(overlay);
    requestAnimationFrame(() => overlay.classList.add('active'));

    shown.push(stage);
    sessionStorage.setItem('lc_tips_shown', JSON.stringify(shown));

    // Auto-dismiss after 8 seconds
    setTimeout(() => {
      if (overlay.parentNode) {
        overlay.classList.remove('active');
        setTimeout(() => overlay.remove(), 400);
      }
    }, 8000);
  };

  window.lcDismissAllTips = function() {
    localStorage.setItem('lc_tips_dismissed', 'true');
    document.querySelectorAll('.lc-tip-overlay').forEach(el => el.remove());
  };
})();
</script>
"""

LANDING_HERO_TEMPLATE = """<!-- Landing Hero Variant — Injected by Onboarding Optimizer -->
<div id="lc-hero-variant" style="display:none;">
  <style>
    .lc-hero-variant { text-align: center; padding: 60px 20px 40px; }
    .lc-hero-variant h1 {
      font-family: 'Inter', sans-serif;
      font-size: clamp(28px, 5vw, 48px);
      font-weight: 700;
      color: white;
      line-height: 1.15;
      margin: 0 0 16px;
    }
    .lc-hero-variant .subtitle {
      font-family: 'Inter', sans-serif;
      font-size: clamp(14px, 2vw, 18px);
      color: rgba(255,255,255,0.6);
      max-width: 500px;
      margin: 0 auto 28px;
      line-height: 1.5;
    }
    .lc-hero-cta {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      background: #1db954;
      color: white;
      font-family: 'Inter', sans-serif;
      font-size: 16px;
      font-weight: 600;
      padding: 14px 28px;
      border-radius: 14px;
      border: none;
      cursor: pointer;
      transition: all 0.3s ease;
    }
    .lc-hero-cta:hover {
      background: #1ed760;
      transform: translateY(-1px);
      box-shadow: 0 8px 24px rgba(29,185,84,0.3);
    }
    .lc-hero-demo-reel {
      margin-top: 32px;
      display: flex;
      gap: 12px;
      justify-content: center;
      flex-wrap: wrap;
    }
    .lc-hero-demo-thumb {
      width: 80px; height: 80px;
      border-radius: 12px;
      object-fit: cover;
      border: 2px solid rgba(255,255,255,0.1);
      transition: all 0.3s ease;
      cursor: pointer;
    }
    .lc-hero-demo-thumb:hover {
      border-color: rgba(29,185,84,0.5);
      transform: scale(1.05);
    }
  </style>
</div>
<script>
(function() {
  window.lcApplyHeroVariant = function(config) {
    if (!config || !config.hero_variant) return;

    const variant = config.hero_variant;
    const heroEl = document.querySelector('.hero, #hero-section, [data-hero]');
    if (!heroEl) return;

    // Apply CTA text override
    if (config.cta_text) {
      const ctaBtn = heroEl.querySelector('button, .cta, [data-cta]');
      if (ctaBtn) ctaBtn.textContent = config.cta_text;
    }

    // Apply headline override
    if (config.headline) {
      const h1 = heroEl.querySelector('h1');
      if (h1) h1.textContent = config.headline;
    }

    // Apply subtitle override
    if (config.subtitle) {
      const sub = heroEl.querySelector('.subtitle, p');
      if (sub) sub.textContent = config.subtitle;
    }

    // Show demo reel if configured
    if (config.show_demo_reel) {
      const demoReel = document.getElementById('lc-hero-variant');
      if (demoReel) demoReel.style.display = 'block';
    }

    // Track which variant was shown
    fetch('/api/track', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        event: 'page_load',
        data: { hero_variant: variant, cta_text: config.cta_text || '' },
        ts: Date.now()
      })
    }).catch(() => {});
  };
})();
</script>
"""


# ─── Bottleneck Remediation Strategies ──────────────────────────────
REMEDIATION_STRATEGIES = {
    "page_load→upload_start": {
        "name": "Landing page bounce",
        "actions": [
            {"type": "landing", "key": "hero_variant", "options": ["default", "video_first", "social_proof", "minimal"]},
            {"type": "landing", "key": "cta_text", "options": [
                "Upload Your Track",
                "Drop a beat, get a video",
                "Free Spotify Canvas — 30 seconds",
                "Turn your music into art",
            ]},
            {"type": "landing", "key": "show_demo_reel", "options": [True, False]},
            {"type": "onboarding", "key": "show_upload_tip", "value": True},
        ],
    },
    "upload_start→upload_complete": {
        "name": "Upload abandonment",
        "actions": [
            {"type": "onboarding", "key": "upload_encouragement", "value": True},
            {"type": "onboarding", "key": "supported_formats_prominent", "value": True},
            {"type": "onboarding", "key": "max_file_size_display", "value": True},
        ],
    },
    "upload_complete→analyze_start": {
        "name": "Post-upload confusion",
        "actions": [
            {"type": "onboarding", "key": "auto_analyze", "value": True},
            {"type": "onboarding", "key": "show_analysis_tip", "value": True},
        ],
    },
    "analyze_start→director_select": {
        "name": "Director selection paralysis",
        "actions": [
            {"type": "onboarding", "key": "highlight_recommended_director", "value": True},
            {"type": "onboarding", "key": "director_previews", "value": True},
            {"type": "onboarding", "key": "show_director_tip", "value": True},
        ],
    },
    "director_select→generate_start": {
        "name": "Pre-generation hesitation",
        "actions": [
            {"type": "onboarding", "key": "auto_generate_on_select", "value": False},
            {"type": "onboarding", "key": "generation_time_estimate", "value": True},
            {"type": "onboarding", "key": "show_generate_tip", "value": True},
        ],
    },
    "generate_start→generate_complete": {
        "name": "Generation wait abandonment",
        "actions": [
            {"type": "onboarding", "key": "progress_animation", "value": True},
            {"type": "onboarding", "key": "show_facts_during_wait", "value": True},
            {"type": "onboarding", "key": "estimated_time_remaining", "value": True},
        ],
    },
    "generate_complete→export": {
        "name": "Export friction",
        "actions": [
            {"type": "onboarding", "key": "celebration_animation", "value": True},
            {"type": "onboarding", "key": "auto_show_export", "value": True},
            {"type": "onboarding", "key": "show_export_tip", "value": True},
            {"type": "onboarding", "key": "share_prompt_after_export", "value": True},
        ],
    },
}

# ─── Mobile-Specific Remediation Strategies ─────────────────────────
MOBILE_REMEDIATION = {
    "high_mobile_bounce": {
        "name": "Mobile bounce rate too high",
        "threshold": 0.6,  # > 60% mobile bounce triggers this
        "actions": [
            {"type": "mobile", "key": "enlarge_upload_button", "value": True},
            {"type": "mobile", "key": "simplify_hero", "value": True},
            {"type": "mobile", "key": "sticky_cta", "value": True},
            {"type": "mobile", "key": "reduce_above_fold_content", "value": True},
        ],
    },
    "mobile_upload_friction": {
        "name": "Mobile upload drop-off",
        "threshold": 0.5,  # < 50% mobile upload→complete rate
        "actions": [
            {"type": "mobile", "key": "show_file_picker_hint", "value": True},
            {"type": "mobile", "key": "compress_before_upload", "value": True},
            {"type": "mobile", "key": "show_upload_progress_fullscreen", "value": True},
        ],
    },
    "mobile_director_confusion": {
        "name": "Mobile director selection paralysis",
        "threshold": 0.4,  # < 40% director select rate on mobile
        "actions": [
            {"type": "mobile", "key": "swipeable_directors", "value": True},
            {"type": "mobile", "key": "auto_recommend_director", "value": True},
            {"type": "mobile", "key": "director_preview_autoplay", "value": True},
        ],
    },
    "mobile_generation_abandonment": {
        "name": "Mobile users leave during generation",
        "threshold": 0.5,  # < 50% generate→complete on mobile
        "actions": [
            {"type": "mobile", "key": "push_notification_on_complete", "value": True},
            {"type": "mobile", "key": "keep_screen_active", "value": True},
            {"type": "mobile", "key": "show_mini_player_during_wait", "value": True},
        ],
    },
    "mobile_export_friction": {
        "name": "Mobile export drop-off",
        "threshold": 0.5,  # < 50% complete→export on mobile
        "actions": [
            {"type": "mobile", "key": "one_tap_export", "value": True},
            {"type": "mobile", "key": "share_sheet_native", "value": True},
            {"type": "mobile", "key": "save_to_photos_option", "value": True},
        ],
    },
}


class OnboardingOptimizer:
    """
    Autonomous agent that optimizes the onboarding funnel.

    Pipeline: Read funnel JSONL → Find bottleneck → Apply remediation → Write configs
    """

    def __init__(self):
        self.metrics = FunnelMetrics()
        self.onboarding_config = self._load_config(ONBOARDING_CONFIG_PATH, self._default_onboarding())
        self.landing_config = self._load_config(LANDING_CONFIG_PATH, self._default_landing())

    def _default_onboarding(self) -> Dict:
        return {
            "version": 1,
            "tips_enabled": True,
            "tip_stages": ["upload", "directors", "export"],
            "show_upload_tip": True,
            "show_analysis_tip": False,
            "show_director_tip": True,
            "show_generate_tip": False,
            "show_export_tip": True,
            "auto_analyze": True,
            "auto_generate_on_select": False,
            "auto_show_export": True,
            "highlight_recommended_director": True,
            "director_previews": True,
            "celebration_animation": True,
            "share_prompt_after_export": True,
            "progress_animation": True,
            "show_facts_during_wait": False,
            "estimated_time_remaining": True,
            "upload_encouragement": False,
            "supported_formats_prominent": True,
            "max_file_size_display": True,
            "generation_time_estimate": True,
            "demo_mode_enabled": True,
            "demo_canvases": [
                {"mood": "ethereal", "director": "Kubrick", "thumb": "/mood_demos/ethereal.jpg"},
                {"mood": "aggressive", "director": "Fincher", "thumb": "/mood_demos/aggressive.jpg"},
                {"mood": "melancholic", "director": "Wong Kar-wai", "thumb": "/mood_demos/melancholic.jpg"},
            ],
            "last_updated": "",
            "last_bottleneck": "",
        }

    def _default_landing(self) -> Dict:
        return {
            "version": 1,
            "hero_variant": "default",
            "headline": "Turn Your Music Into Living Art",
            "subtitle": "AI-powered Spotify Canvas videos that move with your sound",
            "cta_text": "Upload Your Track",
            "show_demo_reel": False,
            "show_social_proof_above_fold": True,
            "section_order": ["hero", "mood_library", "social_proof", "how_it_works"],
            "stats_source": "real",
            "ab_test_id": "",
            "last_updated": "",
            "last_change": "",
        }

    def _load_config(self, path: Path, defaults: Dict) -> Dict:
        if path.exists():
            try:
                return json.loads(path.read_text())
            except (json.JSONDecodeError, IOError):
                pass
        return defaults

    def _read_jsonl(self, filepath: Path) -> List[Dict]:
        entries = []
        if not filepath.exists():
            return entries
        try:
            with open(filepath, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except IOError:
            pass
        return entries

    # ─── Funnel Analysis ────────────────────────────────────────────
    def analyze_funnel(self) -> FunnelMetrics:
        """Analyze the full funnel from JSONL data"""
        funnel_data = self._read_jsonl(DATA_DIR / "onboarding_funnel.jsonl")

        # Count events per stage
        stage_counts = {}
        for stage in FUNNEL_STAGES:
            stage_counts[stage] = sum(1 for e in funnel_data if e.get("event") == stage)

        # Ensure page_load is at least 1 to avoid division by zero
        stage_counts["page_load"] = max(stage_counts.get("page_load", 0), 1)

        # Calculate conversion rates between consecutive stages
        stage_rates = {}
        for i in range(len(FUNNEL_STAGES) - 1):
            current = FUNNEL_STAGES[i]
            next_stage = FUNNEL_STAGES[i + 1]
            current_count = max(stage_counts.get(current, 0), 1)
            next_count = stage_counts.get(next_stage, 0)
            rate = next_count / current_count
            stage_rates[f"{current}→{next_stage}"] = rate

        # Find biggest drop-off
        biggest_dropoff = ""
        biggest_dropoff_rate = 1.0
        for transition, rate in stage_rates.items():
            if rate < biggest_dropoff_rate:
                biggest_dropoff_rate = rate
                biggest_dropoff = transition

        # Overall conversion
        exports = stage_counts.get("export", 0)
        loads = stage_counts.get("page_load", 1)
        overall = exports / loads

        # Bounce rate (loaded but never uploaded)
        uploads = stage_counts.get("upload_start", 0)
        bounce = 1.0 - (uploads / loads) if loads > 0 else 1.0

        # Demo conversion
        demo_events = sum(1 for e in funnel_data if e.get("data", {}).get("mode") == "demo")
        demo_uploads = sum(1 for e in funnel_data
                          if e.get("event") == "upload_start"
                          and e.get("data", {}).get("from_demo", False))
        demo_conv = demo_uploads / max(demo_events, 1)

        # ─── Mobile-specific metrics ───────────────────────────────
        mobile_events = [e for e in funnel_data if e.get("data", {}).get("is_mobile", False)]
        mobile_loads = sum(1 for e in mobile_events if e.get("event") == "page_load")
        mobile_loads = max(mobile_loads, 1)
        mobile_ratio = mobile_loads / loads if loads > 0 else 0.0

        mobile_uploads = sum(1 for e in mobile_events if e.get("event") == "upload_start")
        mobile_exports = sum(1 for e in mobile_events if e.get("event") == "export")
        mobile_bounce = 1.0 - (mobile_uploads / mobile_loads) if mobile_loads > 0 else 1.0
        mobile_conversion = mobile_exports / mobile_loads if mobile_loads > 0 else 0.0

        # Mobile funnel drop-off analysis
        mobile_stage_counts = {}
        for stage in FUNNEL_STAGES:
            mobile_stage_counts[stage] = sum(
                1 for e in mobile_events if e.get("event") == stage
            )
        mobile_stage_counts["page_load"] = max(mobile_stage_counts.get("page_load", 0), 1)

        mobile_biggest_dropoff = ""
        mobile_biggest_dropoff_rate = 1.0
        for i in range(len(FUNNEL_STAGES) - 1):
            curr = FUNNEL_STAGES[i]
            nxt = FUNNEL_STAGES[i + 1]
            curr_c = max(mobile_stage_counts.get(curr, 0), 1)
            nxt_c = mobile_stage_counts.get(nxt, 0)
            rate = nxt_c / curr_c
            if rate < mobile_biggest_dropoff_rate:
                mobile_biggest_dropoff_rate = rate
                mobile_biggest_dropoff = f"{curr}→{nxt}"

        self.metrics = FunnelMetrics(
            stage_counts=stage_counts,
            stage_rates=stage_rates,
            biggest_dropoff=biggest_dropoff,
            biggest_dropoff_rate=biggest_dropoff_rate,
            overall_conversion=overall,
            avg_time_to_export=0.0,
            bounce_rate=bounce,
            demo_conversion=demo_conv,
            mobile_ratio=mobile_ratio,
            mobile_bounce_rate=mobile_bounce,
            mobile_conversion=mobile_conversion,
            mobile_biggest_dropoff=mobile_biggest_dropoff,
            mobile_biggest_dropoff_rate=mobile_biggest_dropoff_rate,
        )

        return self.metrics

    def identify_bottleneck(self) -> Tuple[str, Dict]:
        """Identify the biggest bottleneck and return remediation strategy"""
        bottleneck = self.metrics.biggest_dropoff

        if bottleneck in REMEDIATION_STRATEGIES:
            strategy = REMEDIATION_STRATEGIES[bottleneck]
            return bottleneck, strategy

        # Default: focus on landing page
        return "page_load→upload_start", REMEDIATION_STRATEGIES["page_load→upload_start"]

    # ─── Optimization Engine ────────────────────────────────────────
    def optimize(self) -> OnboardingDecision:
        """Run optimization cycle: analyze → identify → remediate"""
        metrics = self.analyze_funnel()
        bottleneck, strategy = self.identify_bottleneck()

        onboarding_changes = {}
        landing_changes = {}

        # Apply remediation actions
        for action in strategy["actions"]:
            if action["type"] == "onboarding":
                if "value" in action:
                    onboarding_changes[action["key"]] = action["value"]
                elif "options" in action:
                    # Rotate through options based on day
                    day = datetime.utcnow().timetuple().tm_yday
                    idx = day % len(action["options"])
                    onboarding_changes[action["key"]] = action["options"][idx]
            elif action["type"] == "landing":
                if "value" in action:
                    landing_changes[action["key"]] = action["value"]
                elif "options" in action:
                    day = datetime.utcnow().timetuple().tm_yday
                    idx = day % len(action["options"])
                    landing_changes[action["key"]] = action["options"][idx]

        # If bounce rate > 70%, force demo-first mode
        if metrics.bounce_rate > 0.7:
            onboarding_changes["demo_mode_enabled"] = True
            landing_changes["show_demo_reel"] = True
            landing_changes["show_social_proof_above_fold"] = True

        # ─── Mobile-specific optimizations ────────────────────────
        mobile_changes = {}
        if metrics.mobile_ratio > 0.3:  # >30% mobile traffic = worth optimizing
            for rule_name, rule in MOBILE_REMEDIATION.items():
                triggered = False
                if rule_name == "high_mobile_bounce" and metrics.mobile_bounce_rate > rule["threshold"]:
                    triggered = True
                elif rule_name == "mobile_upload_friction":
                    # Check upload_start→upload_complete on mobile
                    mob_rate = 0.0
                    if metrics.mobile_biggest_dropoff == "upload_start→upload_complete":
                        mob_rate = metrics.mobile_biggest_dropoff_rate
                    if mob_rate < rule["threshold"] and mob_rate > 0:
                        triggered = True
                elif rule_name == "mobile_director_confusion":
                    if metrics.mobile_biggest_dropoff == "analyze_start→director_select":
                        triggered = True
                elif rule_name == "mobile_generation_abandonment":
                    if metrics.mobile_biggest_dropoff == "generate_start→generate_complete":
                        triggered = True
                elif rule_name == "mobile_export_friction":
                    if metrics.mobile_biggest_dropoff == "generate_complete→export":
                        triggered = True

                if triggered:
                    for action in rule["actions"]:
                        mobile_changes[action["key"]] = action["value"]

        if mobile_changes:
            onboarding_changes["mobile"] = mobile_changes

        # Build reasoning
        rates_str = ", ".join(f"{k}: {v:.0%}" for k, v in sorted(metrics.stage_rates.items()))
        reasoning = (
            f"Bottleneck: {strategy['name']} ({bottleneck}, "
            f"rate: {metrics.biggest_dropoff_rate:.0%}). "
            f"Overall conversion: {metrics.overall_conversion:.1%}. "
            f"Bounce: {metrics.bounce_rate:.0%}. "
            f"Applied {len(onboarding_changes) + len(landing_changes)} config changes."
        )

        decision = OnboardingDecision(
            timestamp=datetime.utcnow().isoformat() + "Z",
            bottleneck=bottleneck,
            action_taken=strategy["name"],
            config_changes=onboarding_changes,
            landing_changes=landing_changes,
            reasoning=reasoning,
            metrics_snapshot=asdict(metrics),
        )

        return decision

    # ─── Config Writers ─────────────────────────────────────────────
    def write_configs(self, decision: OnboardingDecision) -> List[Path]:
        """Write updated config files"""
        written = []

        # Update onboarding config
        for key, value in decision.config_changes.items():
            self.onboarding_config[key] = value
        self.onboarding_config["last_updated"] = decision.timestamp
        self.onboarding_config["last_bottleneck"] = decision.bottleneck

        ONBOARDING_CONFIG_PATH.write_text(json.dumps(self.onboarding_config, indent=2) + "\n")
        written.append(ONBOARDING_CONFIG_PATH)
        print(f"[OnboardingOptimizer] Config written → {ONBOARDING_CONFIG_PATH}")

        # Update landing config
        for key, value in decision.landing_changes.items():
            self.landing_config[key] = value
        self.landing_config["last_updated"] = decision.timestamp
        self.landing_config["last_change"] = decision.action_taken
        self.landing_config["ab_test_id"] = f"ab_{datetime.utcnow().strftime('%Y%m%d')}"

        LANDING_CONFIG_PATH.write_text(json.dumps(self.landing_config, indent=2) + "\n")
        written.append(LANDING_CONFIG_PATH)
        print(f"[OnboardingOptimizer] Landing config written → {LANDING_CONFIG_PATH}")

        return written

    def write_templates(self) -> List[Path]:
        """Write HTML template files"""
        written = []

        tips_path = TEMPLATE_DIR / "onboarding_tips.html"
        tips_path.write_text(ONBOARDING_TIPS_TEMPLATE)
        written.append(tips_path)

        hero_path = TEMPLATE_DIR / "landing_hero_variant.html"
        hero_path.write_text(LANDING_HERO_TEMPLATE)
        written.append(hero_path)

        print(f"[OnboardingOptimizer] Templates written: {[p.name for p in written]}")
        return written

    def _log_decision(self, decision: OnboardingDecision):
        log_path = DATA_DIR / "onboarding_decisions.jsonl"
        with open(log_path, "a") as f:
            f.write(json.dumps(asdict(decision)) + "\n")

    # ─── Main Entry ─────────────────────────────────────────────────
    def run(self) -> Dict:
        """Execute full onboarding optimization cycle"""
        print("\n" + "=" * 65)
        print("  ONBOARDING OPTIMIZER — Autonomous Cycle")
        print("=" * 65)

        # 1. Analyze funnel
        metrics = self.analyze_funnel()
        print(f"\n[Funnel] Stages: {json.dumps(metrics.stage_counts)}")
        print(f"[Funnel] Biggest drop-off: {metrics.biggest_dropoff} "
              f"({metrics.biggest_dropoff_rate:.0%})")
        print(f"[Funnel] Overall conversion: {metrics.overall_conversion:.1%}, "
              f"Bounce: {metrics.bounce_rate:.0%}")

        # 2. Optimize
        decision = self.optimize()
        print(f"\n[Optimize] {decision.reasoning}")

        # 3. Write configs
        configs = self.write_configs(decision)

        # 4. Write templates
        templates = self.write_templates()

        # 5. Log decision
        self._log_decision(decision)

        result = {
            "status": "success",
            "bottleneck": decision.bottleneck,
            "action": decision.action_taken,
            "configs_written": [str(c) for c in configs],
            "templates_written": [str(t) for t in templates],
            "changes": {**decision.config_changes, **decision.landing_changes},
            "metrics": asdict(metrics),
            "reasoning": decision.reasoning,
        }

        print(f"\n{'─' * 65}")
        print(f"  RESULT: Fixed '{decision.action_taken}' | "
              f"{len(decision.config_changes) + len(decision.landing_changes)} changes | "
              f"{len(templates)} templates")
        print(f"{'=' * 65}\n")

        return result


def main():
    """Run onboarding optimizer (called by GitHub Actions)"""
    optimizer = OnboardingOptimizer()
    result = optimizer.run()

    summary_path = DATA_DIR / "onboarding_summary.json"
    summary_path.write_text(json.dumps(result, indent=2) + "\n")
    print(f"\nSummary saved to {summary_path}")


if __name__ == "__main__":
    main()
