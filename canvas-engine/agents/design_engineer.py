#!/usr/bin/env python3
"""
Design Engineer — Autonomous Visual UX Agent

Actually modifies the product's visual design: CSS overrides, layout adjustments,
typography hierarchy, spacing, motion, and component styling.

Unlike other agents that toggle features on/off, this agent writes CSS that changes
how the product LOOKS and FEELS. It targets specific UX problems:
- Upload zone too small on mobile → enlarge it
- Director picker overwhelming → simplify layout
- Export CTA not prominent enough → increase contrast
- Generation wait feels long → add progress animation
- Hero section bounce → restructure visual hierarchy

Runs daily via GitHub Actions. CSS overrides auto-deploy via Vercel. $0 cost.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field

# ─── Paths ──────────────────────────────────────────────────────────
ENGINE_DIR = Path(__file__).parent.parent
APP_DIR = ENGINE_DIR.parent
DATA_DIR = ENGINE_DIR / "checklist_data"
TEMPLATE_DIR = APP_DIR / "templates"
CONFIG_PATH = APP_DIR / "design_config.json"

DATA_DIR.mkdir(exist_ok=True)
TEMPLATE_DIR.mkdir(exist_ok=True)


# ─── Design Tokens (matches index.html :root) ──────────────────────
DESIGN_TOKENS = {
    "accent": "#1db954",
    "accent_hover": "#1ed760",
    "accent_glow": "rgba(29, 185, 84, 0.3)",
    "glass_bg": "rgba(255, 255, 255, 0.03)",
    "glass_border": "rgba(255, 255, 255, 0.08)",
    "text_primary": "rgba(255, 255, 255, 0.92)",
    "text_secondary": "rgba(255, 255, 255, 0.6)",
    "text_muted": "rgba(255, 255, 255, 0.35)",
    "radius_md": "16px",
    "radius_lg": "24px",
    "font": "'Inter', -apple-system, sans-serif",
}


@dataclass
class DesignMetrics:
    """UX health metrics derived from funnel + session data"""
    hero_bounce_rate: float = 0.0
    upload_zone_tap_rate: float = 0.0
    director_selection_time: float = 0.0
    generation_abandon_rate: float = 0.0
    export_cta_click_rate: float = 0.0
    mobile_completion_rate: float = 0.0
    desktop_completion_rate: float = 0.0
    avg_scroll_depth: float = 0.0
    mood_library_engagement: float = 0.0
    social_proof_view_rate: float = 0.0


@dataclass
class DesignDecision:
    """What visual changes the agent decided to make"""
    timestamp: str = ""
    css_overrides: Dict[str, str] = field(default_factory=dict)
    layout_changes: List[str] = field(default_factory=list)
    component_mods: Dict[str, Dict] = field(default_factory=dict)
    reasoning: str = ""
    metrics_snapshot: Dict = field(default_factory=dict)
    priority: str = "medium"


# ─── UX Problem → CSS Fix Mapping ──────────────────────────────────
UX_FIXES = {
    "hero_bounce": {
        "name": "Hero section bounce too high",
        "threshold": 0.6,
        "metric": "hero_bounce_rate",
        "compare": "gt",
        "css": {
            # Make CTA more prominent
            ".btn-hero-cta": "font-size: 18px; padding: 18px 36px; box-shadow: 0 0 40px rgba(29,185,84,0.4), 0 8px 32px rgba(0,0,0,0.3); animation: ctaPulse 3s ease-in-out infinite;",
            # Reduce visual noise above fold
            ".hero-features": "display: none;",
            # Make headline bigger
            ".hero h1": "font-size: 56px; line-height: 1.08; letter-spacing: -1px;",
            # Add CTA pulse animation
            "@keyframes ctaPulse": "0%,100%{box-shadow: 0 0 20px rgba(29,185,84,0.2)} 50%{box-shadow: 0 0 50px rgba(29,185,84,0.5)}",
        },
        "layout": ["hero_simplified"],
    },
    "upload_zone_small": {
        "name": "Upload zone too small on mobile",
        "threshold": 0.3,
        "metric": "upload_zone_tap_rate",
        "compare": "lt",
        "css": {
            ".upload-zone": "min-height: 240px; border: 2px dashed rgba(29,185,84,0.4); border-radius: 24px; display: flex; align-items: center; justify-content: center; flex-direction: column; gap: 16px;",
            "@media (max-width: 768px)": ".upload-zone { min-height: 300px; margin: 0 -16px; border-radius: 20px; }",
            ".upload-zone:active": "background: rgba(29,185,84,0.08); border-color: rgba(29,185,84,0.6); transform: scale(0.98);",
        },
        "layout": ["upload_enlarged"],
    },
    "director_paralysis": {
        "name": "Director selection takes too long",
        "threshold": 15.0,
        "metric": "director_selection_time",
        "compare": "gt",
        "css": {
            # Highlight recommended director
            ".ce-dir-option:first-child": "border: 2px solid rgba(29,185,84,0.5); position: relative;",
            ".ce-dir-option:first-child::after": "content: 'Recommended'; position: absolute; top: -10px; right: 12px; background: #1db954; color: white; font-size: 10px; font-weight: 600; padding: 2px 8px; border-radius: 6px; font-family: 'Inter', sans-serif;",
            # Simplify non-recommended options
            ".ce-dir-option:not(:first-child) .ce-dir-desc": "display: none;",
            ".ce-directions-list": "gap: 8px;",
        },
        "layout": ["directors_simplified"],
    },
    "generation_abandon": {
        "name": "Users abandon during generation",
        "threshold": 0.3,
        "metric": "generation_abandon_rate",
        "compare": "gt",
        "css": {
            # Better progress visualization
            ".ce-progress-bar": "height: 6px; border-radius: 3px; overflow: hidden;",
            ".ce-progress-fill": "background: linear-gradient(90deg, #1db954, #1ed760, #1db954); background-size: 200% 100%; animation: shimmer 1.5s ease-in-out infinite;",
            "@keyframes shimmer": "0%{background-position: 200% 0} 100%{background-position: -200% 0}",
            # Add time estimate
            ".ce-gen-label": "font-size: 16px; font-weight: 500;",
            ".ce-gen-overlay": "background: rgba(0,0,0,0.85); backdrop-filter: blur(20px);",
        },
        "layout": ["generation_enhanced"],
    },
    "export_friction": {
        "name": "Export CTA not getting clicks",
        "threshold": 0.4,
        "metric": "export_cta_click_rate",
        "compare": "lt",
        "css": {
            # Make export button unmissable
            ".ce-action": "background: rgba(29,185,84,0.2); border: 1px solid rgba(29,185,84,0.4); font-weight: 600; padding: 14px 24px; font-size: 15px;",
            ".ce-action:first-child": "background: #1db954; color: white; border: none; box-shadow: 0 4px 20px rgba(29,185,84,0.4);",
            ".ce-action:first-child:hover": "background: #1ed760; transform: translateY(-2px); box-shadow: 0 8px 30px rgba(29,185,84,0.5);",
            # Drawer more prominent
            "#ce-drawer": "background: rgba(10,10,10,0.95); border-top: 1px solid rgba(29,185,84,0.2); backdrop-filter: blur(40px);",
        },
        "layout": ["export_prominent"],
    },
    "mobile_ux": {
        "name": "Mobile experience needs improvement",
        "threshold": 0.3,
        "metric": "mobile_completion_rate",
        "compare": "lt",
        "css": {
            # Larger touch targets
            "@media (max-width: 768px)": """
                .btn-hero-cta { width: 100%; padding: 20px; font-size: 18px; border-radius: 16px; }
                .ce-dir-option { padding: 16px; min-height: 72px; }
                .ce-chip { padding: 10px 18px; font-size: 14px; }
                .ce-action { padding: 16px 24px; font-size: 16px; width: 100%; }
                .ce-actions { flex-direction: column; gap: 10px; }
                .ce-intent-input { font-size: 16px; padding: 14px 16px; }
                .modal { margin: 12px; border-radius: 20px; max-height: 90vh; }
                .proof-grid { gap: 16px; }
                .glass-card { border-radius: 16px; }
                .mood-card { border-radius: 12px; }
            """,
        },
        "layout": ["mobile_optimized"],
    },
    "scroll_depth_low": {
        "name": "Users not scrolling past hero",
        "threshold": 0.4,
        "metric": "avg_scroll_depth",
        "compare": "lt",
        "css": {
            # Scroll indicator
            ".hero::after": "content: ''; position: absolute; bottom: 20px; left: 50%; width: 24px; height: 40px; border: 2px solid rgba(255,255,255,0.2); border-radius: 12px; transform: translateX(-50%);",
            # Compact hero to show content below fold
            ".hero": "min-height: auto; padding-bottom: 40px;",
            ".phone-preview": "max-height: 360px;",
        },
        "layout": ["hero_compact"],
    },
    "mood_library_ignored": {
        "name": "Mood library not getting engagement",
        "threshold": 0.15,
        "metric": "mood_library_engagement",
        "compare": "lt",
        "css": {
            ".mood-card": "transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1);",
            ".mood-card:hover": "transform: translateY(-12px) scale(1.02); box-shadow: 0 20px 60px rgba(0,0,0,0.5), 0 0 40px rgba(29,185,84,0.1);",
            ".mood-card .mood-play-btn": "opacity: 0; transform: scale(0.8); transition: all 0.3s ease;",
            ".mood-card:hover .mood-play-btn": "opacity: 1; transform: scale(1);",
            "#moods .section-header": "text-align: center; margin-bottom: 40px;",
        },
        "layout": ["mood_enhanced"],
    },
    "social_proof_weak": {
        "name": "Social proof section not convincing",
        "threshold": 0.2,
        "metric": "social_proof_view_rate",
        "compare": "lt",
        "css": {
            ".proof-section": "padding: 80px 0;",
            ".stats-card .stat-value": "font-size: 40px; background: linear-gradient(135deg, #1db954, #1ed760); -webkit-background-clip: text; -webkit-text-fill-color: transparent;",
            ".proof-quote": "font-size: 18px; line-height: 1.8; font-style: italic;",
            ".author-avatar": "width: 56px; height: 56px; border: 2px solid rgba(29,185,84,0.3);",
        },
        "layout": ["proof_enhanced"],
    },
}


class DesignEngineer:
    """
    Autonomous agent that improves the product's visual design.

    Pipeline: Read UX metrics → Identify visual problems → Generate CSS fixes → Write config
    """

    def __init__(self):
        self.metrics = DesignMetrics()
        self.current_config = self._load_config()

    def _load_config(self) -> Dict:
        if CONFIG_PATH.exists():
            try:
                return json.loads(CONFIG_PATH.read_text())
            except (json.JSONDecodeError, IOError):
                pass
        return {
            "version": 1,
            "css_overrides": {},
            "active_fixes": [],
            "layout_changes": [],
            "component_mods": {},
            "last_updated": "",
            "last_decision": "",
            "history": [],
        }

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

    # ─── UX Analysis ────────────────────────────────────────────────
    def analyze(self) -> DesignMetrics:
        """Analyze UX health from funnel + session data"""
        funnel = self._read_jsonl(DATA_DIR / "onboarding_funnel.jsonl")
        activity = self._read_jsonl(DATA_DIR / "user_activity.jsonl")

        page_loads = max(sum(1 for e in funnel if e.get("event") == "page_load"), 1)
        uploads = sum(1 for e in funnel if e.get("event") == "upload_start")
        director_selects = sum(1 for e in funnel if e.get("event") == "director_select")
        gen_starts = sum(1 for e in funnel if e.get("event") == "generate_start")
        gen_completes = sum(1 for e in funnel if e.get("event") == "generate_complete")
        exports = sum(1 for e in funnel if e.get("event") == "export")

        # Mobile vs desktop
        mobile_loads = max(sum(1 for e in funnel if e.get("event") == "page_load" and e.get("data", {}).get("is_mobile")), 1)
        mobile_exports = sum(1 for e in funnel if e.get("event") == "export" and e.get("data", {}).get("is_mobile"))
        desktop_loads = max(page_loads - mobile_loads, 1)
        desktop_exports = exports - mobile_exports

        # Scroll depth from session data
        scroll_events = [e for e in activity if e.get("event") == "scroll_depth"]
        avg_scroll = sum(e.get("data", {}).get("depth", 0) for e in scroll_events) / max(len(scroll_events), 1)

        # Mood library
        mood_clicks = sum(1 for e in funnel if e.get("event") == "mood_click" or e.get("data", {}).get("section") == "moods")
        proof_views = sum(1 for e in funnel if e.get("event") == "proof_view" or e.get("data", {}).get("section") == "proof")

        self.metrics = DesignMetrics(
            hero_bounce_rate=1.0 - (uploads / page_loads),
            upload_zone_tap_rate=uploads / page_loads,
            director_selection_time=0.0,  # Would need timestamp diffs
            generation_abandon_rate=1.0 - (gen_completes / max(gen_starts, 1)),
            export_cta_click_rate=exports / max(gen_completes, 1),
            mobile_completion_rate=mobile_exports / mobile_loads,
            desktop_completion_rate=desktop_exports / desktop_loads,
            avg_scroll_depth=avg_scroll,
            mood_library_engagement=mood_clicks / page_loads,
            social_proof_view_rate=proof_views / page_loads,
        )

        return self.metrics

    # ─── Design Decision Engine ─────────────────────────────────────
    def decide(self) -> DesignDecision:
        """Identify visual problems and generate CSS fixes"""
        m = self.metrics
        all_css = {}
        all_layout = []
        all_mods = {}
        triggered_fixes = []

        for fix_name, fix in UX_FIXES.items():
            metric_val = getattr(m, fix["metric"], 0)
            threshold = fix["threshold"]
            compare = fix["compare"]

            triggered = False
            if compare == "gt" and metric_val > threshold:
                triggered = True
            elif compare == "lt" and metric_val < threshold:
                triggered = True

            if triggered:
                triggered_fixes.append(fix_name)
                for selector, css_value in fix["css"].items():
                    all_css[selector] = css_value
                all_layout.extend(fix.get("layout", []))

        # Determine priority
        priority = "low"
        if len(triggered_fixes) >= 5:
            priority = "critical"
        elif len(triggered_fixes) >= 3:
            priority = "high"
        elif len(triggered_fixes) >= 1:
            priority = "medium"

        reasoning = (
            f"Triggered {len(triggered_fixes)} design fixes: {', '.join(triggered_fixes)}. "
            f"Hero bounce: {m.hero_bounce_rate:.0%}, Upload tap: {m.upload_zone_tap_rate:.0%}, "
            f"Gen abandon: {m.generation_abandon_rate:.0%}, Export click: {m.export_cta_click_rate:.0%}, "
            f"Mobile complete: {m.mobile_completion_rate:.0%}. Priority: {priority}."
        )

        return DesignDecision(
            timestamp=datetime.utcnow().isoformat() + "Z",
            css_overrides=all_css,
            layout_changes=all_layout,
            component_mods=all_mods,
            reasoning=reasoning,
            metrics_snapshot=asdict(m),
            priority=priority,
        )

    # ─── CSS Generator ──────────────────────────────────────────────
    def _generate_css(self, overrides: Dict[str, str]) -> str:
        """Convert CSS override dict to a valid stylesheet string"""
        lines = [
            "/* ═══════════════════════════════════════════════════",
            "   Design Engineer — Autonomous CSS Overrides",
            f"   Generated: {datetime.utcnow().isoformat()}Z",
            "   These styles override index.html defaults based on UX data.",
            "   DO NOT EDIT — regenerated daily by design_engineer.py",
            "   ═══════════════════════════════════════════════════ */",
            "",
        ]

        media_queries = {}
        regular_rules = {}

        for selector, value in overrides.items():
            if selector.startswith("@keyframes"):
                # Keyframe animation
                anim_name = selector.replace("@keyframes ", "")
                lines.append(f"@keyframes {anim_name} {{ {value} }}")
                lines.append("")
            elif selector.startswith("@media"):
                # Collect media query rules
                media_key = selector
                if media_key not in media_queries:
                    media_queries[media_key] = []
                media_queries[media_key].append(value)
            else:
                regular_rules[selector] = value

        # Write regular rules
        for selector, value in regular_rules.items():
            lines.append(f"{selector} {{ {value} }}")
            lines.append("")

        # Write media queries
        for media, rules in media_queries.items():
            lines.append(f"{media} {{")
            for rule in rules:
                # Rule might contain multiple selectors
                for line in rule.strip().split("\n"):
                    lines.append(f"  {line.strip()}")
            lines.append("}")
            lines.append("")

        return "\n".join(lines)

    # ─── Writers ────────────────────────────────────────────────────
    def write_config(self, decision: DesignDecision) -> Path:
        """Write design config with CSS overrides"""
        config = self.current_config.copy()
        config["version"] = config.get("version", 0) + 1
        config["css_overrides"] = decision.css_overrides
        config["active_fixes"] = decision.layout_changes
        config["layout_changes"] = decision.layout_changes
        config["component_mods"] = decision.component_mods
        config["last_updated"] = decision.timestamp
        config["last_decision"] = decision.reasoning
        config["priority"] = decision.priority

        # Keep history (last 30 entries)
        history = config.get("history", [])
        history.append({
            "timestamp": decision.timestamp,
            "fixes": decision.layout_changes,
            "priority": decision.priority,
            "reasoning": decision.reasoning[:200],
        })
        config["history"] = history[-30:]

        CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n")
        self.current_config = config

        print(f"[DesignEngineer] Config written → {CONFIG_PATH}")
        return CONFIG_PATH

    def write_templates(self, decision: DesignDecision) -> List[Path]:
        """Write CSS override file that frontend injects"""
        written = []

        if decision.css_overrides:
            css_content = self._generate_css(decision.css_overrides)
            css_path = TEMPLATE_DIR / "design_overrides.css"
            css_path.write_text(css_content)
            written.append(css_path)
            print(f"[DesignEngineer] CSS overrides written → {css_path} ({len(decision.css_overrides)} rules)")

        return written

    def _log_decision(self, decision: DesignDecision):
        log_path = DATA_DIR / "design_decisions.jsonl"
        with open(log_path, "a") as f:
            f.write(json.dumps(asdict(decision)) + "\n")

    # ─── Main Entry ─────────────────────────────────────────────────
    def run(self) -> Dict:
        """Execute full design optimization cycle"""
        print("\n" + "=" * 65)
        print("  DESIGN ENGINEER — Autonomous Visual UX Cycle")
        print("=" * 65)

        # 1. Analyze
        metrics = self.analyze()
        print(f"\n[Analyze] Hero bounce: {metrics.hero_bounce_rate:.0%}, "
              f"Upload tap: {metrics.upload_zone_tap_rate:.0%}")
        print(f"[Analyze] Gen abandon: {metrics.generation_abandon_rate:.0%}, "
              f"Export click: {metrics.export_cta_click_rate:.0%}")
        print(f"[Analyze] Mobile: {metrics.mobile_completion_rate:.0%}, "
              f"Desktop: {metrics.desktop_completion_rate:.0%}")

        # 2. Decide
        decision = self.decide()
        print(f"\n[Decide] {decision.reasoning}")

        # 3. Write config
        self.write_config(decision)

        # 4. Write CSS overrides
        templates = self.write_templates(decision)

        # 5. Log
        self._log_decision(decision)

        result = {
            "status": "success",
            "priority": decision.priority,
            "css_rules": len(decision.css_overrides),
            "layout_changes": decision.layout_changes,
            "templates_written": [str(t) for t in templates],
            "config_path": str(CONFIG_PATH),
            "metrics": asdict(metrics),
            "reasoning": decision.reasoning,
        }

        print(f"\n{'─' * 65}")
        print(f"  RESULT: {len(decision.css_overrides)} CSS rules | "
              f"Priority: {decision.priority} | {len(templates)} files written")
        print(f"{'=' * 65}\n")

        return result


def main():
    engineer = DesignEngineer()
    result = engineer.run()
    summary_path = DATA_DIR / "design_summary.json"
    summary_path.write_text(json.dumps(result, indent=2) + "\n")
    print(f"\nSummary saved to {summary_path}")


if __name__ == "__main__":
    main()
