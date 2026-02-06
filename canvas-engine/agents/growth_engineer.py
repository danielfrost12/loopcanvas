#!/usr/bin/env python3
"""
Growth Engineer Agent — Autonomous Viral Growth System

Runs daily in GitHub Actions. Ships real product changes to improve viral growth.
Target: K-factor from 0.0 to 0.5 (each user brings half a new user).

Phased approach — only enables features when metrics justify them:
  Phase 1 (k < 0.1): Share button + copy link (minimum viable sharing)
  Phase 2 (k 0.1-0.3): Referral bonuses + platform sharing
  Phase 3 (k 0.3-0.5): Social proof with real data + watermark
  Phase 4 (k > 0.5): Public gallery + optimize share copy

Data sources:
  checklist_data/referral_data.jsonl    — share/signup/referral events
  checklist_data/user_activity.jsonl    — session events
  checklist_data/onboarding_funnel.jsonl — funnel stage progression
  optimization_data/canvas_results.jsonl — generation quality + exports

Outputs:
  growth_config.json       — feature flags, copy, thresholds
  templates/share_modal.html — share dialog UI fragment

Cost: $0 — all local file inspection, no APIs
"""

import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# ══════════════════════════════════════════════════════════════
# Paths
# ══════════════════════════════════════════════════════════════

ENGINE_DIR = Path(__file__).parent.parent
APP_DIR = ENGINE_DIR.parent
DATA_DIR = ENGINE_DIR / "checklist_data"
OPT_DIR = ENGINE_DIR / "optimization_data"
CONFIG_DIR = APP_DIR
TEMPLATE_DIR = APP_DIR / "templates"

sys.path.insert(0, str(ENGINE_DIR))


# ══════════════════════════════════════════════════════════════
# Data Structures
# ══════════════════════════════════════════════════════════════

@dataclass
class GrowthMetrics:
    """Computed viral growth metrics."""
    k_factor: float = 0.0
    share_rate: float = 0.0
    share_to_signup: float = 0.0
    referral_bonus_claims: int = 0
    total_shares_by_platform: Dict[str, int] = field(default_factory=dict)
    total_canvases: int = 0
    total_exports: int = 0
    total_shares: int = 0
    total_signups_from_shares: int = 0
    completed_canvases: int = 0
    onboarding_completion_rate: float = 0.0
    avg_quality_score: float = 0.0
    computed_at: str = ""

    def __post_init__(self):
        if not self.computed_at:
            self.computed_at = datetime.now().isoformat()


# ══════════════════════════════════════════════════════════════
# JSONL Reader Utility
# ══════════════════════════════════════════════════════════════

def _read_jsonl(path, days=30):
    """Read JSONL file, filter to last N days. Silently returns [] on missing files."""
    if not path.exists():
        return []
    cutoff = datetime.now() - timedelta(days=days)
    rows = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    ts_str = data.get("timestamp", "")
                    if ts_str:
                        ts = datetime.fromisoformat(ts_str)
                        if ts < cutoff:
                            continue
                    rows.append(data)
                except (json.JSONDecodeError, ValueError):
                    continue
    except OSError:
        pass
    return rows


# ══════════════════════════════════════════════════════════════
# Share Modal HTML Template
# ══════════════════════════════════════════════════════════════

_SHARE_MODAL_CSS = """  <style>
    .share-modal {
      position: fixed; inset: 0; z-index: 9999;
      display: flex; align-items: center; justify-content: center;
      font-family: 'Inter', -apple-system, sans-serif;
    }
    .share-modal__backdrop {
      position: absolute; inset: 0;
      background: rgba(0,0,0,0.7); backdrop-filter: blur(8px);
    }
    .share-modal__panel {
      position: relative; z-index: 1;
      background: rgba(20,20,20,0.95);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 16px; padding: 32px;
      max-width: 420px; width: 90%;
      box-shadow: 0 24px 80px rgba(0,0,0,0.6);
    }
    .share-modal__close {
      position: absolute; top: 12px; right: 16px;
      background: none; border: none; color: #999;
      font-size: 24px; cursor: pointer; padding: 4px 8px;
    }
    .share-modal__close:hover { color: #fff; }
    .share-modal__title {
      margin: 0 0 20px; color: #fff; font-size: 20px; font-weight: 600;
    }
    .share-modal__preview {
      width: 100%; aspect-ratio: 9/16; max-height: 200px;
      background: rgba(255,255,255,0.05); border-radius: 10px;
      margin-bottom: 20px; overflow: hidden;
      display: flex; align-items: center; justify-content: center;
    }
    .share-preview-thumb img,
    .share-preview-thumb video {
      width: 100%; height: 100%; object-fit: cover;
    }
    .share-modal__buttons {
      display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px;
    }
    .share-btn {
      flex: 1; min-width: 90px; padding: 10px 14px;
      border: none; border-radius: 8px; color: #fff;
      font-family: inherit; font-size: 13px; font-weight: 500;
      cursor: pointer; transition: opacity 0.15s;
    }
    .share-btn:hover { opacity: 0.85; }
    .share-referral {
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 10px; padding: 12px 16px;
      margin-bottom: 16px; text-align: center;
    }
    .share-referral p {
      margin: 0; color: #aaa; font-size: 13px;
    }
    .share-referral strong { color: #fff; }
    .share-modal__link {
      display: flex; gap: 8px;
    }
    .share-modal__link input {
      flex: 1; padding: 8px 12px; border-radius: 8px;
      border: 1px solid rgba(255,255,255,0.1);
      background: rgba(255,255,255,0.05); color: #ccc;
      font-family: inherit; font-size: 12px;
    }
    .share-btn--copy {
      background: #333; min-width: auto; flex: 0;
    }
    .share-modal__copied {
      text-align: center; color: #4ecdc4; font-size: 12px;
      margin-top: 8px;
    }
  </style>"""


def _share_modal_js(share_message_json):
    """Return the inline <script> block for the share modal."""
    return """  <script>
    (function() {
      var modal   = document.getElementById('share-modal');
      var backdrop = modal.querySelector('.share-modal__backdrop');
      var closeBtn = modal.querySelector('.share-modal__close');
      var copyBtn  = document.getElementById('share-copy-btn');
      var linkInput = document.getElementById('share-link-input');
      var copiedMsg = document.getElementById('share-copied-msg');
      var shareMsg = """ + share_message_json + """;

      function closeModal() { modal.style.display = 'none'; }
      backdrop.addEventListener('click', closeModal);
      closeBtn.addEventListener('click', closeModal);

      document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') closeModal();
      });

      /* Copy link */
      copyBtn.addEventListener('click', function() {
        var url = linkInput.value;
        if (!url) return;
        if (navigator.clipboard) {
          navigator.clipboard.writeText(url).then(function() {
            copiedMsg.style.display = 'block';
            setTimeout(function() { copiedMsg.style.display = 'none'; }, 2000);
          });
        } else {
          linkInput.select();
          document.execCommand('copy');
          copiedMsg.style.display = 'block';
          setTimeout(function() { copiedMsg.style.display = 'none'; }, 2000);
        }
      });

      /* Platform share buttons */
      modal.querySelectorAll('.share-btn[data-platform]').forEach(function(btn) {
        btn.addEventListener('click', function() {
          var platform = btn.dataset.platform;
          var url = linkInput.value || window.location.href;
          var encoded = encodeURIComponent(url);
          var msg = encodeURIComponent(shareMsg);

          if (platform === 'twitter') {
            window.open('https://twitter.com/intent/tweet?text=' + msg + '&url=' + encoded, '_blank');
          } else if (platform === 'discord') {
            navigator.clipboard.writeText(shareMsg + ' ' + url);
            copiedMsg.textContent = 'Copied for Discord!';
            copiedMsg.style.display = 'block';
            setTimeout(function() {
              copiedMsg.textContent = 'Link copied!';
              copiedMsg.style.display = 'none';
            }, 2000);
          } else if (platform === 'instagram') {
            navigator.clipboard.writeText(shareMsg + ' ' + url);
            copiedMsg.textContent = 'Copied for Instagram!';
            copiedMsg.style.display = 'block';
            setTimeout(function() {
              copiedMsg.textContent = 'Link copied!';
              copiedMsg.style.display = 'none';
            }, 2000);
          } else if (platform === 'copy_link') {
            copyBtn.click();
          }
        });
      });

      /* Public API: window.openShareModal(canvasUrl, thumbnailEl) */
      window.openShareModal = function(canvasUrl, thumbEl) {
        linkInput.value = canvasUrl || window.location.href;
        var preview = document.getElementById('share-preview-thumb');
        if (thumbEl) { preview.innerHTML = ''; preview.appendChild(thumbEl.cloneNode(true)); }
        modal.style.display = 'flex';
      };
    })();
  </script>"""


# ══════════════════════════════════════════════════════════════
# Growth Engineer
# ══════════════════════════════════════════════════════════════

class GrowthEngineer:
    """
    Autonomous agent that analyzes viral metrics and ships growth features.

    Run daily via GitHub Actions. Reads local JSONL telemetry, computes
    K-factor and funnel metrics, then writes config + templates that the
    app consumes at runtime.
    """

    REFERRAL_DATA = DATA_DIR / "referral_data.jsonl"
    USER_ACTIVITY = DATA_DIR / "user_activity.jsonl"
    ONBOARDING_FUNNEL = DATA_DIR / "onboarding_funnel.jsonl"
    CANVAS_RESULTS = OPT_DIR / "canvas_results.jsonl"

    CONFIG_PATH = CONFIG_DIR / "growth_config.json"
    SHARE_MODAL_PATH = TEMPLATE_DIR / "share_modal.html"

    def __init__(self):
        self.metrics = None  # type: Optional[GrowthMetrics]
        self.config = self._default_config()  # type: dict

    # ── Analysis ───────────────────────────────────────────────

    def analyze(self):
        """Read all JSONL data sources and compute viral growth metrics."""
        referral_rows = _read_jsonl(self.REFERRAL_DATA)
        activity_rows = _read_jsonl(self.USER_ACTIVITY)
        funnel_rows = _read_jsonl(self.ONBOARDING_FUNNEL)
        canvas_rows = _read_jsonl(self.CANVAS_RESULTS)

        # -- shares by platform --
        shares_by_platform = defaultdict(int)
        share_events = [r for r in referral_rows if r.get("action") == "share"]
        for row in share_events:
            platform = row.get("platform", "unknown")
            shares_by_platform[platform] += 1
        total_shares = len(share_events)

        # -- signups from shares --
        signup_events = [r for r in referral_rows if r.get("action") == "signup_from_share"]
        total_signups_from_shares = len(signup_events)

        # -- referral bonus claims --
        bonus_events = [r for r in referral_rows if r.get("action") == "referral_bonus_claimed"]
        referral_bonus_claims = len(bonus_events)

        # -- canvas counts --
        total_canvases = len(canvas_rows)
        total_exports = sum(1 for r in canvas_rows if r.get("exported"))
        quality_scores = [r.get("quality_score", 0.0) for r in canvas_rows
                          if r.get("quality_score")]
        avg_quality = (sum(quality_scores) / len(quality_scores)
                       if quality_scores else 0.0)

        # -- completed canvases (quality_passed or exported) --
        completed = sum(1 for r in canvas_rows
                        if r.get("quality_passed") or r.get("exported"))

        # -- unique active sessions --
        active_sessions = set()
        for row in activity_rows:
            sid = row.get("session_id") or row.get("user_id", "")
            if sid:
                active_sessions.add(sid)
        total_active = len(active_sessions) or 1  # avoid div/0

        # -- share rate: pct of completed canvases that were shared --
        share_rate = ((total_shares / completed * 100)
                      if completed > 0 else 0.0)

        # -- share-to-signup conversion --
        share_to_signup = ((total_signups_from_shares / total_shares * 100)
                           if total_shares > 0 else 0.0)

        # -- K-factor: invites_sent_per_user * conversion_rate --
        shares_per_user = total_shares / total_active
        conversion = (total_signups_from_shares / total_shares
                      if total_shares > 0 else 0.0)
        k_factor = shares_per_user * conversion

        # -- onboarding completion --
        started = sum(1 for r in funnel_rows if r.get("stage") == "started")
        completed_onboarding = sum(1 for r in funnel_rows
                                   if r.get("stage") == "completed")
        onboarding_rate = ((completed_onboarding / started * 100)
                           if started > 0 else 0.0)

        self.metrics = GrowthMetrics(
            k_factor=round(k_factor, 4),
            share_rate=round(share_rate, 2),
            share_to_signup=round(share_to_signup, 2),
            referral_bonus_claims=referral_bonus_claims,
            total_shares_by_platform=dict(shares_by_platform),
            total_canvases=total_canvases,
            total_exports=total_exports,
            total_shares=total_shares,
            total_signups_from_shares=total_signups_from_shares,
            completed_canvases=completed,
            onboarding_completion_rate=round(onboarding_rate, 2),
            avg_quality_score=round(avg_quality, 2),
        )
        return self.metrics

    # ── Decision Logic ─────────────────────────────────────────

    def decide(self):
        """Based on current metrics, decide which features to enable."""
        if self.metrics is None:
            self.analyze()
        m = self.metrics
        k = m.k_factor
        config = self._default_config()

        # Phase 1 (k < 0.1): Minimum viable sharing
        config["share"]["enabled"] = True
        config["share"]["platforms"] = ["copy_link"]
        config["share"]["button_text"] = "Share this canvas"
        config["referral"]["enabled"] = False
        config["social_proof"]["use_real_data"] = False
        config["watermark"]["enabled"] = False
        config["gallery_page"]["enabled"] = False

        # Phase 2 (k >= 0.1): Referral bonuses + full platform sharing
        if k >= 0.1:
            config["share"]["platforms"] = [
                "twitter", "instagram", "discord", "copy_link"]
            config["referral"]["enabled"] = True
            config["referral"]["bonus_exports"] = 3
            config["referral"]["minimum_shares_to_unlock"] = 1

        # Phase 3 (k >= 0.3): Social proof with real data + watermark
        if k >= 0.3:
            config["watermark"]["enabled"] = True
            config["watermark"]["opacity"] = 0.15
            self.update_social_proof(config, m)

        # Phase 4 (k >= 0.5): Public gallery + optimized share copy
        if k >= 0.5:
            config["gallery_page"]["enabled"] = True
            config["gallery_page"]["max_items"] = 50
            config["gallery_page"]["sort_by"] = "quality_score"
            canvas_count = "{:,}".format(m.total_canvases)
            config["share"]["share_message_template"] = (
                "I just made this with @LoopCanvas "
                "\u2014 AI turned my track into a cinematic canvas "
                "in 30 seconds \U0001f3ac\n\n"
                "Join " + canvas_count + "+ canvases created"
            )

        # Always write current metrics into config
        config["metrics"] = {
            "k_factor": m.k_factor,
            "share_rate": m.share_rate,
            "share_to_signup": m.share_to_signup,
            "referral_claims": m.referral_bonus_claims,
            "shares_by_platform": m.total_shares_by_platform,
        }
        config["updated_at"] = datetime.now().isoformat()

        self.config = config
        return config

    def update_social_proof(self, config, m):
        """Switch from fallback stats to real stats when enough data exists."""
        has_enough = m.total_canvases >= 100 and m.total_shares >= 10
        config["social_proof"]["use_real_data"] = has_enough
        config["social_proof"]["real_stats"] = {
            "total_canvases": m.total_canvases,
            "total_shares": m.total_shares,
            "total_exports": m.total_exports,
        }
        if has_enough:
            export_pct = (
                "{:.0f}%".format(m.total_exports / m.total_canvases * 100)
                if m.total_canvases > 0 else "0%"
            )
            config["social_proof"]["fallback_stats"] = {
                "canvases_this_month": self._human_number(m.total_canvases),
                "active_artists": str(len(m.total_shares_by_platform)),
                "export_rate": export_pct,
            }

    # ── Config Writer ──────────────────────────────────────────

    def write_config(self):
        """Write growth_config.json to the app root."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.CONFIG_PATH, "w") as f:
            json.dump(self.config, f, indent=2)
        print("[GrowthEngineer] Config written: " + str(self.CONFIG_PATH))

    # ── Template Writer ────────────────────────────────────────

    def write_templates(self):
        """Write share_modal.html template."""
        TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
        c = self.config

        platforms = c.get("share", {}).get("platforms", ["copy_link"])
        referral_enabled = c.get("referral", {}).get("enabled", False)
        bonus_exports = c.get("referral", {}).get("bonus_exports", 3)
        share_message = c.get("share", {}).get(
            "share_message_template",
            "I just made this with @LoopCanvas "
            "\u2014 AI turned my track into a cinematic canvas "
            "in 30 seconds \U0001f3ac",
        )

        # Build platform buttons HTML
        platform_buttons = []
        platform_meta = {
            "twitter": ("Twitter / X", "#1DA1F2"),
            "instagram": ("Instagram", "#E4405F"),
            "discord": ("Discord", "#5865F2"),
            "copy_link": ("Copy Link", "#8B8B8B"),
        }
        for p in platforms:
            label, color = platform_meta.get(p, (p.title(), "#666"))
            platform_buttons.append(
                '      <button class="share-btn share-btn--' + p
                + '" data-platform="' + p
                + '" style="background:' + color + '">'
                + label + '</button>'
            )
        buttons_html = "\n".join(platform_buttons)

        referral_section = ""
        if referral_enabled:
            referral_section = (
                '\n    <div class="share-referral">\n'
                '      <p>Share your canvas to unlock <strong>'
                + str(bonus_exports)
                + '</strong> more free exports</p>\n'
                '    </div>'
            )

        share_message_json = json.dumps(share_message)

        lines = [
            '<!-- Growth Engineer: share_modal.html -- auto-generated '
            + datetime.now().isoformat() + ' -->',
            '<div id="share-modal" class="share-modal" role="dialog" '
            'aria-label="Share your canvas" style="display:none">',
            '  <div class="share-modal__backdrop"></div>',
            '  <div class="share-modal__panel">',
            '    <button class="share-modal__close" aria-label="Close">'
            '&times;</button>',
            '',
            '    <h2 class="share-modal__title">Share your canvas</h2>',
            '',
            '    <div class="share-modal__preview">',
            '      <div class="share-preview-thumb" id="share-preview-thumb">',
            '        <!-- Canvas thumbnail injected by app -->',
            '      </div>',
            '    </div>',
            '',
            '    <div class="share-modal__buttons">',
            buttons_html,
            '    </div>',
            referral_section,
            '    <div class="share-modal__link">',
            '      <input type="text" id="share-link-input" readonly value="" />',
            '      <button id="share-copy-btn" class="share-btn share-btn--copy">'
            'Copy</button>',
            '    </div>',
            '',
            '    <p class="share-modal__copied" id="share-copied-msg" '
            'style="display:none">Link copied!</p>',
            '  </div>',
            '',
            _SHARE_MODAL_CSS,
            '',
            _share_modal_js(share_message_json),
            '</div>',
            '',
        ]

        html = "\n".join(lines)
        with open(self.SHARE_MODAL_PATH, "w") as f:
            f.write(html)
        print("[GrowthEngineer] Template written: " + str(self.SHARE_MODAL_PATH))

    # ── Full Pipeline ──────────────────────────────────────────

    def run(self):
        """Full pipeline: analyze -> decide -> write config -> write templates."""
        sep = "=" * 60
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print("\n" + sep)
        print("  GROWTH ENGINEER \u2014 " + now_str)
        print(sep)

        metrics = self.analyze()
        self._print_metrics(metrics)

        config = self.decide()
        phase = self._current_phase(metrics.k_factor)
        print("\n  Phase: " + phase)
        print("  Features enabled:")
        print("    Share:        " + str(config['share']['enabled'])
              + " (" + ', '.join(config['share']['platforms']) + ")")
        print("    Referral:     " + str(config['referral']['enabled']))
        print("    Social proof: "
              + str(config['social_proof']['use_real_data']))
        print("    Watermark:    " + str(config['watermark']['enabled']))
        print("    Gallery:      " + str(config['gallery_page']['enabled']))

        self.write_config()
        self.write_templates()

        print("\n" + sep)
        print("  GROWTH ENGINEER COMPLETE")
        print(sep + "\n")

    # ── Report ─────────────────────────────────────────────────

    def report(self):
        """Print a human-readable growth report from current or saved data."""
        saved_metrics = {}
        if self.CONFIG_PATH.exists():
            try:
                with open(self.CONFIG_PATH) as f:
                    saved = json.load(f)
                saved_metrics = saved.get("metrics", {})
            except (json.JSONDecodeError, OSError):
                pass

        metrics = self.analyze()

        sep = "=" * 60
        print("\n" + sep)
        print("  GROWTH REPORT \u2014 " + datetime.now().strftime('%Y-%m-%d'))
        print(sep)
        self._print_metrics(metrics)

        if saved_metrics:
            prev_k = saved_metrics.get("k_factor", 0)
            delta = metrics.k_factor - prev_k
            direction = "+" if delta >= 0 else ""
            print("\n  K-factor change since last run: "
                  + direction + "{:.4f}".format(delta))

        phase = self._current_phase(metrics.k_factor)
        print("  Current phase: " + phase)
        print("  Target: K > 0.5")

        gap = max(0, 0.5 - metrics.k_factor)
        print("  Gap to target: {:.4f}".format(gap))
        print(sep + "\n")

    # ── Helpers ────────────────────────────────────────────────

    def _print_metrics(self, m):
        """Print metrics summary to stdout."""
        print("\n  Metrics:")
        print("    K-factor:             {:.4f}  (target >0.5)".format(
            m.k_factor))
        print("    Share rate:           {:.2f}%  (target >10%)".format(
            m.share_rate))
        print("    Share-to-signup:      {:.2f}%  (target >5%)".format(
            m.share_to_signup))
        print("    Referral claims:      " + str(m.referral_bonus_claims))
        print("    Total shares:         " + str(m.total_shares))
        print("    Total canvases:       " + str(m.total_canvases))
        print("    Total exports:        " + str(m.total_exports))
        print("    Completed canvases:   " + str(m.completed_canvases))
        print("    Onboarding rate:      {:.1f}%".format(
            m.onboarding_completion_rate))
        print("    Avg quality:          {:.2f}/10".format(
            m.avg_quality_score))
        if m.total_shares_by_platform:
            print("    Shares by platform:   "
                  + str(m.total_shares_by_platform))

    @staticmethod
    def _current_phase(k):
        if k >= 0.5:
            return "4 \u2014 Gallery + optimized copy (K >= 0.5)"
        if k >= 0.3:
            return "3 \u2014 Social proof + watermark (K >= 0.3)"
        if k >= 0.1:
            return "2 \u2014 Referral bonuses + platform sharing (K >= 0.1)"
        return "1 \u2014 Minimum viable sharing (K < 0.1)"

    @staticmethod
    def _human_number(n):
        if n >= 1_000_000:
            return "{:.1f}M".format(n / 1_000_000)
        if n >= 1_000:
            return "{:.0f}K".format(n / 1_000)
        return str(n)

    @staticmethod
    def _default_config():
        return {
            "version": 1,
            "updated_at": datetime.now().isoformat(),
            "share": {
                "enabled": True,
                "button_text": "Share this canvas",
                "platforms": [
                    "twitter", "instagram", "discord", "copy_link"],
                "share_message_template": (
                    "I just made this with @LoopCanvas "
                    "\u2014 AI turned my track into a cinematic canvas "
                    "in 30 seconds \U0001f3ac"
                ),
                "og_tags": {
                    "title": "Check out this AI-generated music canvas",
                    "description": (
                        "Made with LoopCanvas \u2014 upload your track, "
                        "get a cinematic Spotify Canvas in seconds"
                    ),
                    "image_path": "/api/og-image",
                },
            },
            "referral": {
                "enabled": True,
                "bonus_exports": 3,
                "message":
                    "Share your canvas to unlock {bonus} more free exports",
                "minimum_shares_to_unlock": 1,
            },
            "social_proof": {
                "use_real_data": False,
                "fallback_stats": {
                    "canvases_this_month": "847K",
                    "active_artists": "32",
                    "export_rate": "94%",
                },
                "real_stats": {
                    "total_canvases": 0,
                    "total_shares": 0,
                    "total_exports": 0,
                },
            },
            "watermark": {
                "enabled": False,
                "text": "Made with LoopCanvas",
                "opacity": 0.15,
                "position": "bottom_right",
            },
            "gallery_page": {
                "enabled": False,
                "max_items": 50,
                "sort_by": "quality_score",
            },
            "metrics": {
                "k_factor": 0.0,
                "share_rate": 0.0,
                "share_to_signup": 0.0,
                "referral_claims": 0,
                "shares_by_platform": {},
            },
        }


# ══════════════════════════════════════════════════════════════
# Event Logging Helpers (called by the app at runtime)
# ══════════════════════════════════════════════════════════════

def log_share(session_id, referrer_id="", platform="copy_link"):
    """Log a share event."""
    _append_jsonl(DATA_DIR / "referral_data.jsonl", {
        "session_id": session_id,
        "action": "share",
        "referrer_id": referrer_id,
        "timestamp": datetime.now().isoformat(),
        "platform": platform,
    })


def log_signup_from_share(session_id, referrer_id=""):
    """Log a new signup that came from a shared link."""
    _append_jsonl(DATA_DIR / "referral_data.jsonl", {
        "session_id": session_id,
        "action": "signup_from_share",
        "referrer_id": referrer_id,
        "timestamp": datetime.now().isoformat(),
        "platform": "",
    })


def log_referral_bonus(session_id):
    """Log a referral bonus claim."""
    _append_jsonl(DATA_DIR / "referral_data.jsonl", {
        "session_id": session_id,
        "action": "referral_bonus_claimed",
        "referrer_id": "",
        "timestamp": datetime.now().isoformat(),
        "platform": "",
    })


def log_onboarding_event(session_id, stage):
    """Log an onboarding funnel event."""
    _append_jsonl(DATA_DIR / "onboarding_funnel.jsonl", {
        "session_id": session_id,
        "event": "onboarding",
        "stage": stage,
        "timestamp": datetime.now().isoformat(),
    })


def _append_jsonl(path, data):
    """Append a JSON line to a file, creating directories as needed."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as f:
            f.write(json.dumps(data) + "\n")
    except OSError:
        pass


# ══════════════════════════════════════════════════════════════
# Singleton
# ══════════════════════════════════════════════════════════════

_instance = None


def get_growth_engineer():
    """Get the global GrowthEngineer instance."""
    global _instance
    if _instance is None:
        _instance = GrowthEngineer()
    return _instance


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"

    agent = GrowthEngineer()

    if cmd == "report":
        agent.report()
    elif cmd == "run":
        agent.run()
    else:
        print("Usage: python -m agents.growth_engineer [run|report]")
        print("  run    -- Full pipeline (analyze, decide, write config + templates)")
        print("  report -- Print growth metrics report")
        sys.exit(1)
