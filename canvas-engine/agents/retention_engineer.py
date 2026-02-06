#!/usr/bin/env python3
"""
Retention Engineer — Autonomous Agent for User Retention

Ships real product changes daily to improve user retention from 0% to 30%.
Runs in GitHub Actions on a cron schedule. $0 cost — no APIs, no databases.

What it does:
1. ANALYZE: Reads user activity, onboarding funnel, and canvas results from JSONL
2. DECIDE: Based on current metrics, decides which retention features to enable
3. CONFIGURE: Writes retention_config.json that the frontend reads at runtime
4. TEMPLATE: Generates/updates HTML template fragments (gallery, banner, share modal)
5. REPORT: Prints a CI-visible report of metrics and decisions

Retention phases (progressive feature rollout):
  - Phase 1 (return_rate <  5%): Gallery + welcome back banner (basics)
  - Phase 2 (return_rate  5-15%): + share links + batch mode teaser
  - Phase 3 (return_rate 15-25%): + director comparison + A/B tests
  - Phase 4 (return_rate > 25%): Fine-tune gallery layout, optimize share copy

Data: canvas-engine/checklist_data/*.jsonl
Config: retention_config.json (repo root, read by frontend)
Templates: templates/*.html (repo root, included by frontend)
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field


# ======================================================================
# Paths — follow the same pattern as optimization_loop.py
# ======================================================================

ENGINE_DIR = Path(__file__).parent.parent
APP_DIR = ENGINE_DIR.parent
DATA_DIR = ENGINE_DIR / "checklist_data"
OPT_DATA_DIR = ENGINE_DIR / "optimization_data"
CONFIG_DIR = APP_DIR
TEMPLATE_DIR = APP_DIR / "templates"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
OPT_DATA_DIR.mkdir(exist_ok=True)
TEMPLATE_DIR.mkdir(exist_ok=True)


# ======================================================================
# Data Structures
# ======================================================================

@dataclass
class RetentionMetrics:
    """Computed retention metrics"""
    return_rate: float = 0.0        # % of sessions that are return visits
    gallery_usage: float = 0.0      # % of return visitors who view gallery
    share_rate: float = 0.0         # % of completed canvases that get shared
    export_rate: float = 0.0        # % of completed canvases exported
    total_sessions: int = 0
    return_sessions: int = 0
    onboarding_completion: float = 0.0  # % who complete onboarding
    drop_off_stage: str = ""            # stage where most users drop off


@dataclass
class RetentionDecision:
    """Decisions made by the agent for this run"""
    phase: int = 1
    gallery_enabled: bool = False
    gallery_max_items: int = 20
    gallery_position: str = "bottom"
    share_enabled: bool = False
    share_platforms: List[str] = field(default_factory=lambda: ["copy_link"])
    return_banner_enabled: bool = False
    return_banner_message: str = "Welcome back! You have {count} canvases."
    batch_mode_teaser: bool = False
    director_comparison: bool = False
    ab_test_active: str = ""
    ab_test_variants: Dict = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)


# ======================================================================
# Core Agent
# ======================================================================

class RetentionEngineer:
    """
    Autonomous retention optimization agent.

    Call run() daily via GitHub Actions. It reads data, computes metrics,
    decides which features to ship, writes config + templates.
    """

    def __init__(self):
        self.metrics = RetentionMetrics()
        self.decision = RetentionDecision()
        self.config_file = CONFIG_DIR / "retention_config.json"
        self._raw_activity: List[Dict] = []
        self._raw_onboarding: List[Dict] = []
        self._raw_canvas: List[Dict] = []

    # ==================================================================
    # Step 1: ANALYZE — Read JSONL data, compute metrics
    # ==================================================================

    def analyze(self) -> RetentionMetrics:
        """Read all JSONL data sources and compute retention metrics."""
        print("\n" + "=" * 60)
        print("RETENTION ENGINEER — ANALYZE")
        print("=" * 60)

        self._load_data()
        self._compute_return_rate()
        self._compute_gallery_usage()
        self._compute_share_rate()
        self._compute_export_rate()
        self._compute_onboarding_funnel()

        return self.metrics

    def _load_data(self):
        """Load all JSONL data sources with error handling."""
        self._raw_activity = self._read_jsonl(DATA_DIR / "user_activity.jsonl")
        self._raw_onboarding = self._read_jsonl(DATA_DIR / "onboarding_funnel.jsonl")
        self._raw_canvas = self._read_jsonl(OPT_DATA_DIR / "canvas_results.jsonl")

        print("  Loaded: {} activity events, {} onboarding events, {} canvas results".format(
            len(self._raw_activity), len(self._raw_onboarding), len(self._raw_canvas)))

    def _read_jsonl(self, path: Path) -> List[Dict]:
        """Read a JSONL file, skipping corrupt lines."""
        if not path.exists():
            print("  [skip] {} not found".format(path.name))
            return []

        records = []
        corrupt = 0
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        corrupt += 1
                        continue
        except Exception as e:
            print("  [error] Reading {}: {}".format(path.name, e))
            return []

        if corrupt > 0:
            print("  [warn] {}: {} corrupt lines skipped".format(path.name, corrupt))

        return records

    def _compute_return_rate(self):
        """Compute % of sessions that are return visits."""
        if not self._raw_activity:
            self.metrics.return_rate = 0.0
            self.metrics.total_sessions = 0
            self.metrics.return_sessions = 0
            print("  return_rate: 0.0% (no activity data)")
            return

        # Group events by session_id
        sessions: Dict[str, List[Dict]] = {}
        for event in self._raw_activity:
            sid = event.get("session_id", event.get("user_id", ""))
            if not sid:
                continue
            if sid not in sessions:
                sessions[sid] = []
            sessions[sid].append(event)

        total = len(sessions)
        returning = 0

        for sid, events in sessions.items():
            # A session is "returning" if explicitly flagged or if multiple
            # distinct day visits exist
            if any(e.get("returning", False) for e in events):
                returning += 1
                continue

            # Fallback: check if this session has activity on more than one day
            days = set()
            for e in events:
                ts = e.get("timestamp", "")
                if ts:
                    try:
                        days.add(ts[:10])  # YYYY-MM-DD
                    except (IndexError, TypeError):
                        pass
            if len(days) > 1:
                returning += 1

        self.metrics.total_sessions = total
        self.metrics.return_sessions = returning
        self.metrics.return_rate = (returning / total * 100) if total > 0 else 0.0

        print("  return_rate: {:.1f}% ({}/{} sessions)".format(
            self.metrics.return_rate, returning, total))

    def _compute_gallery_usage(self):
        """Compute % of return visitors who view the gallery."""
        if not self._raw_activity:
            self.metrics.gallery_usage = 0.0
            print("  gallery_usage: 0.0% (no data)")
            return

        return_sessions = set()
        gallery_views = set()

        for event in self._raw_activity:
            sid = event.get("session_id", event.get("user_id", ""))
            if event.get("returning", False):
                return_sessions.add(sid)
            if event.get("event", "") == "gallery_view":
                gallery_views.add(sid)

        if not return_sessions:
            self.metrics.gallery_usage = 0.0
            print("  gallery_usage: 0.0% (no return visitors)")
            return

        viewers = return_sessions & gallery_views
        self.metrics.gallery_usage = (len(viewers) / len(return_sessions) * 100)

        print("  gallery_usage: {:.1f}% ({}/{} returners)".format(
            self.metrics.gallery_usage, len(viewers), len(return_sessions)))

    def _compute_share_rate(self):
        """Compute % of completed canvases that get shared."""
        if not self._raw_canvas:
            self.metrics.share_rate = 0.0
            print("  share_rate: 0.0% (no canvas data)")
            return

        completed = 0
        shared = 0

        for result in self._raw_canvas:
            if result.get("quality_passed", False) or result.get("exported", False):
                completed += 1
                platforms = result.get("export_platforms", [])
                share_platforms = {"twitter", "instagram", "discord", "tiktok", "share_link"}
                if any(p.lower() in share_platforms for p in platforms):
                    shared += 1

        # Also check activity log for share events
        for event in self._raw_activity:
            if event.get("event", "") in ("share", "share_canvas", "copy_link"):
                shared += 1

        self.metrics.share_rate = (shared / completed * 100) if completed > 0 else 0.0

        print("  share_rate: {:.1f}% ({}/{} completed canvases)".format(
            self.metrics.share_rate, shared, completed))

    def _compute_export_rate(self):
        """Compute % of completed canvases exported."""
        if not self._raw_canvas:
            self.metrics.export_rate = 0.0
            print("  export_rate: 0.0% (no canvas data)")
            return

        total = len(self._raw_canvas)
        exported = sum(1 for r in self._raw_canvas if r.get("exported", False))

        self.metrics.export_rate = (exported / total * 100) if total > 0 else 0.0

        print("  export_rate: {:.1f}% ({}/{} canvases)".format(
            self.metrics.export_rate, exported, total))

    def _compute_onboarding_funnel(self):
        """Analyze onboarding funnel to find drop-off points."""
        if not self._raw_onboarding:
            self.metrics.onboarding_completion = 0.0
            self.metrics.drop_off_stage = "unknown"
            print("  onboarding: no funnel data")
            return

        stage_counts: Dict[str, int] = {}
        session_stages: Dict[str, List[str]] = {}

        for event in self._raw_onboarding:
            sid = event.get("session_id", "")
            stage = event.get("stage", "")
            if not sid or not stage:
                continue

            stage_counts[stage] = stage_counts.get(stage, 0) + 1
            if sid not in session_stages:
                session_stages[sid] = []
            session_stages[sid].append(stage)

        if stage_counts:
            max_stage = max(stage_counts, key=stage_counts.get)
            self.metrics.drop_off_stage = max_stage

        total_sessions = len(session_stages)
        completed = sum(
            1 for stages in session_stages.values()
            if "export" in stages or "complete" in stages
        )
        self.metrics.onboarding_completion = (
            (completed / total_sessions * 100) if total_sessions > 0 else 0.0
        )

        print("  onboarding: {:.1f}% complete, biggest drop-off at: {}".format(
            self.metrics.onboarding_completion, self.metrics.drop_off_stage))

    # ==================================================================
    # Step 2: DECIDE — Based on metrics, choose features
    # ==================================================================

    def decide(self) -> RetentionDecision:
        """Based on current metrics, decide which features to enable/disable."""
        print("\n" + "=" * 60)
        print("RETENTION ENGINEER — DECIDE")
        print("=" * 60)

        rate = self.metrics.return_rate

        if rate < 5.0:
            self._decide_phase1()
        elif rate < 15.0:
            self._decide_phase2()
        elif rate < 25.0:
            self._decide_phase3()
        else:
            self._decide_phase4()

        self._add_targeted_recommendations()

        print("  Phase: {}".format(self.decision.phase))
        print("  Gallery: {} (max={}, pos={})".format(
            "ON" if self.decision.gallery_enabled else "OFF",
            self.decision.gallery_max_items, self.decision.gallery_position))
        print("  Share: {} ({})".format(
            "ON" if self.decision.share_enabled else "OFF",
            ", ".join(self.decision.share_platforms)))
        print("  Return banner: {}".format(
            "ON" if self.decision.return_banner_enabled else "OFF"))
        print("  Batch teaser: {}".format(
            "ON" if self.decision.batch_mode_teaser else "OFF"))
        print("  Director comparison: {}".format(
            "ON" if self.decision.director_comparison else "OFF"))
        if self.decision.ab_test_active:
            print("  A/B test: {}".format(self.decision.ab_test_active))
        print("  Recommendations: {}".format(len(self.decision.recommendations)))

        return self.decision

    def _decide_phase1(self):
        """Phase 1: return_rate < 5% — Enable basics."""
        self.decision.phase = 1
        self.decision.gallery_enabled = True
        self.decision.gallery_max_items = 20
        self.decision.gallery_position = "bottom"
        self.decision.share_enabled = False
        self.decision.share_platforms = ["copy_link"]
        self.decision.return_banner_enabled = True
        self.decision.return_banner_message = (
            "Welcome back! You have {count} canvases waiting.")
        self.decision.batch_mode_teaser = False
        self.decision.director_comparison = False
        self.decision.ab_test_active = ""
        self.decision.ab_test_variants = {}
        self.decision.recommendations.append(
            "Phase 1: Gallery and return banner enabled. Focus on giving users "
            "a reason to come back -- their saved work.")

    def _decide_phase2(self):
        """Phase 2: return_rate 5-15% — Add social sharing + batch teaser."""
        self.decision.phase = 2
        self.decision.gallery_enabled = True
        self.decision.gallery_max_items = 30
        self.decision.gallery_position = "bottom"
        self.decision.share_enabled = True
        self.decision.share_platforms = [
            "twitter", "instagram", "discord", "copy_link"]
        self.decision.return_banner_enabled = True
        self.decision.return_banner_message = (
            "Welcome back! You have {count} canvases. "
            "Share your best work and unlock 3 more exports.")
        self.decision.batch_mode_teaser = True
        self.decision.director_comparison = False
        self.decision.ab_test_active = ""
        self.decision.ab_test_variants = {}
        self.decision.recommendations.append(
            "Phase 2: Sharing enabled. Viral loop active -- referral incentive "
            "offers 3 free exports per share.")

    def _decide_phase3(self):
        """Phase 3: return_rate 15-25% — Enable advanced features + A/B tests."""
        self.decision.phase = 3
        self.decision.gallery_enabled = True
        self.decision.gallery_max_items = 50
        self.decision.gallery_position = "top"
        self.decision.share_enabled = True
        self.decision.share_platforms = [
            "twitter", "instagram", "discord", "copy_link"]
        self.decision.return_banner_enabled = True
        self.decision.return_banner_message = (
            "Welcome back! {count} canvases in your collection. "
            "Try the new director comparison mode.")
        self.decision.batch_mode_teaser = True
        self.decision.director_comparison = True
        self.decision.ab_test_active = "gallery_prominence"
        self.decision.ab_test_variants = {
            "A": {"gallery_position": "top"},
            "B": {"gallery_position": "bottom"},
        }
        self.decision.recommendations.append(
            "Phase 3: Director comparison enabled. A/B testing gallery "
            "position (top vs bottom) to optimize engagement.")

    def _decide_phase4(self):
        """Phase 4: return_rate > 25% — Fine-tune and optimize."""
        self.decision.phase = 4
        self.decision.gallery_enabled = True
        self.decision.gallery_max_items = 100
        self.decision.share_enabled = True
        self.decision.share_platforms = [
            "twitter", "instagram", "discord", "copy_link"]
        self.decision.return_banner_enabled = True
        self.decision.batch_mode_teaser = True
        self.decision.director_comparison = True

        if self.metrics.gallery_usage < 50.0:
            self.decision.gallery_position = "top"
            self.decision.return_banner_message = (
                "Welcome back! Check out your {count} canvases below.")
            self.decision.ab_test_active = "gallery_cta_copy"
            self.decision.ab_test_variants = {
                "A": {"cta_text": "View your canvases"},
                "B": {"cta_text": "Your collection is growing"},
            }
            self.decision.recommendations.append(
                "Phase 4: Gallery usage below 50%. Testing CTA copy to drive "
                "more users to their gallery.")
        elif self.metrics.share_rate < 10.0:
            self.decision.gallery_position = "top"
            self.decision.return_banner_message = (
                "Welcome back! Share your best canvas and unlock premium features.")
            self.decision.ab_test_active = "share_incentive"
            self.decision.ab_test_variants = {
                "A": {"incentive": "3 extra exports"},
                "B": {"incentive": "unlock director comparison"},
            }
            self.decision.recommendations.append(
                "Phase 4: Share rate below 10%. Testing share incentive copy.")
        else:
            self.decision.gallery_position = "top"
            self.decision.return_banner_message = (
                "Welcome back! You have {count} canvases in your collection.")
            self.decision.ab_test_active = ""
            self.decision.ab_test_variants = {}
            self.decision.recommendations.append(
                "Phase 4: Metrics healthy. Maintaining current configuration.")

    def _add_targeted_recommendations(self):
        """Add specific recommendations based on metric gaps."""
        if self.metrics.export_rate < 70.0 and self.metrics.export_rate > 0.0:
            self.decision.recommendations.append(
                "Export rate is {:.1f}% (target: 70%). ".format(
                    self.metrics.export_rate) +
                "Consider: simplify export flow, add one-click export, "
                "show format preview.")

        if (self.metrics.onboarding_completion < 50.0
                and self.metrics.drop_off_stage):
            self.decision.recommendations.append(
                "Onboarding completion is {:.1f}%. ".format(
                    self.metrics.onboarding_completion) +
                "Biggest drop-off at '{}' stage. ".format(
                    self.metrics.drop_off_stage) +
                "Consider: add progress indicator, reduce steps, "
                "show example outputs.")

        if (self.decision.gallery_enabled
                and self.metrics.gallery_usage < 50.0
                and self.metrics.return_sessions > 0):
            self.decision.recommendations.append(
                "Gallery usage is {:.1f}% among returners ".format(
                    self.metrics.gallery_usage) +
                "(target: 50%). Consider: move gallery higher, "
                "add thumbnail previews.")

        if (self.decision.share_enabled
                and self.metrics.share_rate < 10.0
                and self.metrics.return_rate >= 5.0):
            self.decision.recommendations.append(
                "Share rate is {:.1f}% (target: 10%). ".format(
                    self.metrics.share_rate) +
                "Consider: add share prompt after export, "
                "improve share preview card.")

    # ==================================================================
    # Step 3: WRITE CONFIG — retention_config.json
    # ==================================================================

    def write_config(self):
        """Write retention_config.json to the repo root."""
        print("\n" + "=" * 60)
        print("RETENTION ENGINEER — WRITE CONFIG")
        print("=" * 60)

        version = 1
        if self.config_file.exists():
            try:
                with open(self.config_file) as f:
                    existing = json.load(f)
                version = existing.get("version", 0) + 1
            except (json.JSONDecodeError, Exception):
                pass

        config = {
            "version": version,
            "updated_at": datetime.now().isoformat(),
            "features": {
                "gallery_enabled": self.decision.gallery_enabled,
                "gallery_max_items": self.decision.gallery_max_items,
                "share_enabled": self.decision.share_enabled,
                "share_platforms": self.decision.share_platforms,
                "return_banner_enabled": self.decision.return_banner_enabled,
                "return_banner_message": self.decision.return_banner_message,
                "batch_mode_teaser": self.decision.batch_mode_teaser,
                "director_comparison": self.decision.director_comparison,
            },
            "ab_tests": {
                "active_test": self.decision.ab_test_active,
                "variants": self.decision.ab_test_variants,
                "traffic_split": 0.5,
            },
            "metrics": {
                "return_rate": round(self.metrics.return_rate, 2),
                "gallery_usage": round(self.metrics.gallery_usage, 2),
                "share_rate": round(self.metrics.share_rate, 2),
                "export_rate": round(self.metrics.export_rate, 2),
            },
            "recommendations": self.decision.recommendations,
        }

        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            print("  Written: {}".format(self.config_file))
            print("  Version: {}".format(version))
        except Exception as e:
            print("  [error] Failed to write config: {}".format(e))

    # ==================================================================
    # Step 4: WRITE TEMPLATES — HTML fragments
    # ==================================================================

    def write_templates(self):
        """Write/update HTML template files."""
        print("\n" + "=" * 60)
        print("RETENTION ENGINEER — WRITE TEMPLATES")
        print("=" * 60)

        self._write_gallery_template()
        self._write_return_banner_template()
        self._write_share_modal_template()

    def _write_gallery_template(self):
        """Write templates/gallery_component.html — dark themed card grid."""
        path = TEMPLATE_DIR / "gallery_component.html"
        max_items = self.decision.gallery_max_items
        position = self.decision.gallery_position
        ds = datetime.now().strftime('%Y%m%d')

        html = """<!-- Gallery Component — Auto-generated by Retention Engineer v""" + ds + """ -->
<!-- Position: """ + position + """ | Max items: """ + str(max_items) + """ -->
<section class="canvas-gallery" id="canvas-gallery" data-max-items=\"""" + str(max_items) + """\" data-position=\"""" + position + """\">
  <div class="gallery-header">
    <h2 class="gallery-title">Your Canvases</h2>
    <span class="gallery-count" id="gallery-count">0 canvases</span>
  </div>
  <div class="gallery-grid" id="gallery-grid"></div>
  <template id="gallery-card-template">
    <article class="gallery-card glass">
      <div class="card-thumbnail">
        <img src="" alt="Canvas preview" loading="lazy" class="card-img" />
        <div class="card-overlay"><span class="card-score"></span></div>
      </div>
      <div class="card-info">
        <h3 class="card-director"></h3>
        <time class="card-date"></time>
      </div>
      <div class="card-actions">
        <button class="btn-card btn-view" aria-label="View canvas">View</button>
        <button class="btn-card btn-share" aria-label="Share canvas">Share</button>
      </div>
    </article>
  </template>
  <style>
    .canvas-gallery { width: 100%; max-width: 1200px; margin: 0 auto; padding: 2rem 1rem; }
    .gallery-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem; padding: 0 0.5rem; }
    .gallery-title { font-family: 'Inter', -apple-system, sans-serif; font-size: 1.25rem; font-weight: 600; color: rgba(255,255,255,0.92); letter-spacing: -0.01em; }
    .gallery-count { font-family: 'Inter', -apple-system, sans-serif; font-size: 0.8rem; font-weight: 400; color: rgba(255,255,255,0.35); }
    .gallery-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 1rem; }
    .gallery-card { background: rgba(255,255,255,0.03); backdrop-filter: blur(40px) saturate(180%); -webkit-backdrop-filter: blur(40px) saturate(180%); border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; overflow: hidden; transition: transform 0.2s cubic-bezier(0.16,1,0.3,1), border-color 0.2s ease, box-shadow 0.2s ease; box-shadow: inset 0 1px 0 rgba(255,255,255,0.1), 0 2px 8px rgba(0,0,0,0.3); }
    .gallery-card:hover { transform: translateY(-2px); border-color: rgba(255,255,255,0.15); box-shadow: inset 0 1px 0 rgba(255,255,255,0.1), 0 8px 32px rgba(0,0,0,0.4); }
    .card-thumbnail { position: relative; aspect-ratio: 9/16; max-height: 200px; overflow: hidden; background: #111; }
    .card-img { width: 100%; height: 100%; object-fit: cover; }
    .card-overlay { position: absolute; bottom: 0; left: 0; right: 0; padding: 0.5rem; background: linear-gradient(transparent, rgba(0,0,0,0.7)); display: flex; justify-content: flex-end; }
    .card-score { font-family: 'Inter', -apple-system, sans-serif; font-size: 0.7rem; font-weight: 600; color: #1db954; background: rgba(0,0,0,0.5); padding: 0.15rem 0.4rem; border-radius: 6px; }
    .card-info { padding: 0.75rem 1rem 0.5rem; }
    .card-director { font-family: 'Inter', -apple-system, sans-serif; font-size: 0.85rem; font-weight: 500; color: rgba(255,255,255,0.92); margin-bottom: 0.2rem; }
    .card-date { font-family: 'Inter', -apple-system, sans-serif; font-size: 0.7rem; color: rgba(255,255,255,0.35); }
    .card-actions { display: flex; gap: 0.5rem; padding: 0 1rem 0.75rem; }
    .btn-card { flex: 1; padding: 0.45rem 0; border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; background: rgba(255,255,255,0.03); color: rgba(255,255,255,0.6); font-family: 'Inter', -apple-system, sans-serif; font-size: 0.75rem; font-weight: 500; cursor: pointer; transition: all 0.15s ease; }
    .btn-card:hover { background: rgba(255,255,255,0.06); border-color: rgba(255,255,255,0.15); color: rgba(255,255,255,0.92); }
    .btn-share { color: #1db954; }
    .btn-share:hover { background: rgba(29,185,84,0.1); border-color: rgba(29,185,84,0.3); }
    @media (max-width: 640px) { .gallery-grid { grid-template-columns: repeat(2, 1fr); gap: 0.75rem; } .card-info { padding: 0.5rem 0.75rem 0.25rem; } .card-actions { padding: 0 0.75rem 0.5rem; } }
  </style>
</section>
"""
        try:
            with open(path, 'w') as f:
                f.write(html)
            print("  Written: {}".format(path))
        except Exception as e:
            print("  [error] gallery_component.html: {}".format(e))

    def _write_return_banner_template(self):
        """Write templates/return_banner.html — dismissable welcome back banner."""
        path = TEMPLATE_DIR / "return_banner.html"
        message = self.decision.return_banner_message
        ds = datetime.now().strftime('%Y%m%d')

        html = """<!-- Return Banner — Auto-generated by Retention Engineer v""" + ds + """ -->
<div class="return-banner glass" id="return-banner" role="alert" style="display: none;">
  <div class="banner-content">
    <div class="banner-icon">
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="10" cy="10" r="9" stroke="rgba(29,185,84,0.6)" stroke-width="1.5"/>
        <path d="M7 10L9 12L13 8" stroke="#1db954" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </div>
    <p class="banner-message" id="banner-message">""" + message + """</p>
    <button class="banner-cta" id="banner-cta" type="button">View your canvases</button>
  </div>
  <button class="banner-dismiss" id="banner-dismiss" type="button" aria-label="Dismiss banner">
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M3 3L11 11M11 3L3 11" stroke="rgba(255,255,255,0.35)" stroke-width="1.5" stroke-linecap="round"/></svg>
  </button>
  <style>
    .return-banner { position: fixed; top: 0; left: 0; right: 0; z-index: 1000; background: rgba(255,255,255,0.03); backdrop-filter: blur(40px) saturate(180%); -webkit-backdrop-filter: blur(40px) saturate(180%); border-bottom: 1px solid rgba(255,255,255,0.08); padding: 0.75rem 1rem; animation: bannerSlideIn 0.4s cubic-bezier(0.16,1,0.3,1); box-shadow: inset 0 -1px 0 rgba(255,255,255,0.05), 0 2px 8px rgba(0,0,0,0.3); }
    @keyframes bannerSlideIn { from { transform: translateY(-100%); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
    .banner-content { display: flex; align-items: center; gap: 0.75rem; max-width: 1200px; margin: 0 auto; }
    .banner-icon { flex-shrink: 0; }
    .banner-message { flex: 1; font-family: 'Inter', -apple-system, sans-serif; font-size: 0.85rem; font-weight: 400; color: rgba(255,255,255,0.6); line-height: 1.4; }
    .banner-cta { flex-shrink: 0; padding: 0.4rem 1rem; background: #1db954; border: none; border-radius: 10px; color: #000; font-family: 'Inter', -apple-system, sans-serif; font-size: 0.8rem; font-weight: 600; cursor: pointer; transition: background 0.15s ease, transform 0.15s ease; }
    .banner-cta:hover { background: #1ed760; transform: scale(1.02); }
    .banner-dismiss { position: absolute; top: 50%; right: 0.75rem; transform: translateY(-50%); background: none; border: none; cursor: pointer; padding: 0.4rem; border-radius: 8px; transition: background 0.15s ease; }
    .banner-dismiss:hover { background: rgba(255,255,255,0.06); }
    @media (max-width: 640px) { .banner-content { flex-wrap: wrap; gap: 0.5rem; } .banner-cta { width: 100%; text-align: center; padding: 0.5rem; } }
  </style>
  <script>
    (function() {
      var dismiss = document.getElementById('banner-dismiss');
      if (dismiss) {
        dismiss.addEventListener('click', function() {
          var banner = document.getElementById('return-banner');
          if (banner) {
            banner.style.transform = 'translateY(-100%)';
            banner.style.opacity = '0';
            banner.style.transition = 'transform 0.3s ease, opacity 0.3s ease';
            setTimeout(function() { banner.style.display = 'none'; }, 300);
            try { sessionStorage.setItem('banner_dismissed', '1'); } catch(e) {}
          }
        });
      }
      var cta = document.getElementById('banner-cta');
      if (cta) {
        cta.addEventListener('click', function() {
          var gallery = document.getElementById('canvas-gallery');
          if (gallery) { gallery.scrollIntoView({ behavior: 'smooth' }); }
        });
      }
    })();
  </script>
</div>
"""
        try:
            with open(path, 'w') as f:
                f.write(html)
            print("  Written: {}".format(path))
        except Exception as e:
            print("  [error] return_banner.html: {}".format(e))

    def _write_share_modal_template(self):
        """Write templates/share_modal.html — share dialog with social icons."""
        path = TEMPLATE_DIR / "share_modal.html"
        platforms = self.decision.share_platforms
        ds = datetime.now().strftime('%Y%m%d')

        platform_icons = {
            "twitter": ("Twitter", '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>'),
            "instagram": ("Instagram", '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2c2.717 0 3.056.01 4.122.06 1.065.05 1.79.217 2.428.465.66.254 1.216.598 1.772 1.153a4.908 4.908 0 0 1 1.153 1.772c.247.637.415 1.363.465 2.428.047 1.066.06 1.405.06 4.122 0 2.717-.01 3.056-.06 4.122-.05 1.065-.218 1.79-.465 2.428a4.883 4.883 0 0 1-1.153 1.772 4.915 4.915 0 0 1-1.772 1.153c-.637.247-1.363.415-2.428.465-1.066.047-1.405.06-4.122.06-2.717 0-3.056-.01-4.122-.06-1.065-.05-1.79-.218-2.428-.465a4.89 4.89 0 0 1-1.772-1.153 4.904 4.904 0 0 1-1.153-1.772c-.248-.637-.415-1.363-.465-2.428C2.013 15.056 2 14.717 2 12c0-2.717.01-3.056.06-4.122.05-1.066.217-1.79.465-2.428a4.88 4.88 0 0 1 1.153-1.772A4.897 4.897 0 0 1 5.45 2.525c.638-.248 1.362-.415 2.428-.465C8.944 2.013 9.283 2 12 2zm0 5a5 5 0 1 0 0 10 5 5 0 0 0 0-10zm0 8.25a3.25 3.25 0 1 1 0-6.5 3.25 3.25 0 0 1 0 6.5z"/></svg>'),
            "discord": ("Discord", '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128c.12-.098.246-.198.373-.292a.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.094.246.194.373.292a.077.077 0 0 1-.006.127 12.3 12.3 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.84 19.84 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.06.06 0 0 0-.031-.03z"/></svg>'),
            "copy_link": ("Copy Link", '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>'),
        }

        platform_btns = ""
        for plat in platforms:
            name, icon = platform_icons.get(plat, (plat.title(), ""))
            platform_btns += '\n        <button class="share-platform-btn" data-platform="' + plat + '" type="button" role="button" tabindex="0">\n          ' + icon + '\n          <span>' + name + '</span>\n        </button>'

        html = """<!-- Share Modal — Auto-generated by Retention Engineer v""" + ds + """ -->
<div class="share-modal-overlay" id="share-modal-overlay" style="display: none;" role="dialog" aria-modal="true" aria-label="Share canvas">
  <div class="share-modal glass">
    <div class="share-modal-header">
      <h3 class="share-modal-title">Share Canvas</h3>
      <button class="share-modal-close" id="share-modal-close" type="button" aria-label="Close">
        <svg width="16" height="16" viewBox="0 0 14 14" fill="none"><path d="M3 3L11 11M11 3L3 11" stroke="rgba(255,255,255,0.35)" stroke-width="1.5" stroke-linecap="round"/></svg>
      </button>
    </div>
    <div class="share-preview">
      <div class="share-preview-img" id="share-preview-img"></div>
      <div class="share-preview-meta">
        <span class="share-preview-director" id="share-preview-director"></span>
        <span class="share-preview-score" id="share-preview-score"></span>
      </div>
    </div>
    <div class="share-platforms">""" + platform_btns + """
    </div>
    <div class="share-incentive">
      <svg width="14" height="14" viewBox="0 0 20 20" fill="none"><path d="M10 2L12.09 7.26L18 8.27L14 12.14L14.18 18.02L10 15.77L5.82 18.02L6 12.14L2 8.27L7.91 7.26L10 2Z" fill="rgba(29,185,84,0.5)"/></svg>
      <span>Share to unlock 3 more exports this month</span>
    </div>
    <div class="share-link-row">
      <input class="share-link-input" id="share-link-input" type="text" readonly value="" aria-label="Share link" />
      <button class="share-link-copy" id="share-link-copy" type="button">Copy</button>
    </div>
  </div>
  <style>
    .share-modal-overlay { position: fixed; inset: 0; z-index: 2000; display: flex; align-items: center; justify-content: center; background: rgba(0,0,0,0.6); backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px); animation: fadeIn 0.2s ease; }
    @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
    .share-modal { width: 90%; max-width: 400px; background: rgba(20,20,20,0.95); backdrop-filter: blur(40px) saturate(180%); -webkit-backdrop-filter: blur(40px) saturate(180%); border: 1px solid rgba(255,255,255,0.08); border-radius: 20px; padding: 1.5rem; box-shadow: inset 0 1px 0 rgba(255,255,255,0.1), 0 24px 64px rgba(0,0,0,0.5); animation: modalSlideUp 0.35s cubic-bezier(0.16,1,0.3,1); }
    @keyframes modalSlideUp { from { transform: translateY(20px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
    .share-modal-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.25rem; }
    .share-modal-title { font-family: 'Inter', -apple-system, sans-serif; font-size: 1.1rem; font-weight: 600; color: rgba(255,255,255,0.92); }
    .share-modal-close { background: none; border: none; cursor: pointer; padding: 0.35rem; border-radius: 8px; transition: background 0.15s ease; }
    .share-modal-close:hover { background: rgba(255,255,255,0.06); }
    .share-preview { background: #111; border-radius: 14px; overflow: hidden; margin-bottom: 1.25rem; border: 1px solid rgba(255,255,255,0.03); }
    .share-preview-img { aspect-ratio: 9/16; max-height: 180px; background: #0a0a0a; display: flex; align-items: center; justify-content: center; color: rgba(255,255,255,0.2); font-size: 0.8rem; }
    .share-preview-meta { display: flex; align-items: center; justify-content: space-between; padding: 0.6rem 0.85rem; }
    .share-preview-director { font-family: 'Inter', -apple-system, sans-serif; font-size: 0.8rem; font-weight: 500; color: rgba(255,255,255,0.6); }
    .share-preview-score { font-family: 'Inter', -apple-system, sans-serif; font-size: 0.75rem; font-weight: 600; color: #1db954; }
    .share-platforms { display: grid; grid-template-columns: repeat(auto-fit, minmax(80px, 1fr)); gap: 0.6rem; margin-bottom: 1rem; }
    .share-platform-btn { display: flex; flex-direction: column; align-items: center; gap: 0.35rem; padding: 0.75rem 0.5rem; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 14px; color: rgba(255,255,255,0.6); font-family: 'Inter', -apple-system, sans-serif; font-size: 0.65rem; font-weight: 500; cursor: pointer; transition: all 0.15s ease; }
    .share-platform-btn:hover { background: rgba(255,255,255,0.06); border-color: rgba(255,255,255,0.15); color: rgba(255,255,255,0.92); }
    .share-incentive { display: flex; align-items: center; gap: 0.5rem; padding: 0.6rem 0.75rem; background: rgba(29,185,84,0.06); border: 1px solid rgba(29,185,84,0.15); border-radius: 10px; margin-bottom: 1rem; }
    .share-incentive span { font-family: 'Inter', -apple-system, sans-serif; font-size: 0.75rem; font-weight: 500; color: rgba(29,185,84,0.8); }
    .share-link-row { display: flex; gap: 0.5rem; }
    .share-link-input { flex: 1; padding: 0.5rem 0.75rem; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; color: rgba(255,255,255,0.6); font-family: 'Inter', -apple-system, sans-serif; font-size: 0.8rem; outline: none; }
    .share-link-input:focus { border-color: rgba(255,255,255,0.15); }
    .share-link-copy { padding: 0.5rem 1rem; background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; color: rgba(255,255,255,0.92); font-family: 'Inter', -apple-system, sans-serif; font-size: 0.8rem; font-weight: 500; cursor: pointer; transition: all 0.15s ease; }
    .share-link-copy:hover { background: rgba(255,255,255,0.1); }
  </style>
  <script>
    (function() {
      var overlay = document.getElementById('share-modal-overlay');
      var closeBtn = document.getElementById('share-modal-close');
      var copyBtn = document.getElementById('share-link-copy');
      var linkInput = document.getElementById('share-link-input');
      if (closeBtn) { closeBtn.addEventListener('click', function() { if (overlay) overlay.style.display = 'none'; }); }
      if (overlay) { overlay.addEventListener('click', function(e) { if (e.target === overlay) overlay.style.display = 'none'; }); }
      if (copyBtn && linkInput) {
        copyBtn.addEventListener('click', function() {
          if (navigator.clipboard) {
            navigator.clipboard.writeText(linkInput.value).then(function() {
              copyBtn.textContent = 'Copied!';
              setTimeout(function() { copyBtn.textContent = 'Copy'; }, 2000);
            });
          } else {
            linkInput.select();
            document.execCommand('copy');
            copyBtn.textContent = 'Copied!';
            setTimeout(function() { copyBtn.textContent = 'Copy'; }, 2000);
          }
        });
      }
    })();
  </script>
</div>
"""
        try:
            with open(path, 'w') as f:
                f.write(html)
            print("  Written: {}".format(path))
        except Exception as e:
            print("  [error] share_modal.html: {}".format(e))

    # ==================================================================
    # Step 5: RUN — Full pipeline
    # ==================================================================

    def run(self):
        """Full retention engineering pipeline. Called by GitHub Actions daily."""
        start = datetime.now()

        print("\n" + "#" * 60)
        print("# RETENTION ENGINEER — " + start.strftime('%Y-%m-%d %H:%M:%S'))
        print("# Target: 0% -> 30% return rate")
        print("# Cost: $0")
        print("#" * 60)

        self.analyze()
        self.decide()
        self.write_config()
        self.write_templates()

        elapsed = (datetime.now() - start).total_seconds()
        self._print_report(elapsed)

    def _print_report(self, elapsed=0.0):
        """Print CI-visible metrics report."""
        print("\n" + "=" * 60)
        print("RETENTION ENGINEER — REPORT")
        print("=" * 60)

        metrics_table = [
            ("return_rate", self.metrics.return_rate, 30.0, "%"),
            ("gallery_usage", self.metrics.gallery_usage, 50.0, "%"),
            ("share_rate", self.metrics.share_rate, 10.0, "%"),
            ("export_rate", self.metrics.export_rate, 70.0, "%"),
        ]

        for name, value, target, unit in metrics_table:
            status = "PASS" if value >= target else "BELOW"
            bar_len = int(min(value / target, 1.0) * 20)
            bar = "#" * bar_len + "-" * (20 - bar_len)
            print("  {:20s} {:6.1f}{} / {:.0f}{}  [{}]  {}".format(
                name, value, unit, target, unit, bar, status))

        print("\n  Phase:               {}".format(self.decision.phase))
        print("  Total sessions:      {}".format(self.metrics.total_sessions))
        print("  Return sessions:     {}".format(self.metrics.return_sessions))
        print("  Onboarding:          {:.1f}%".format(
            self.metrics.onboarding_completion))
        print("  Drop-off stage:      {}".format(
            self.metrics.drop_off_stage or "N/A"))

        if self.decision.recommendations:
            print("\n  Recommendations:")
            for i, rec in enumerate(self.decision.recommendations, 1):
                print("    {}. {}".format(i, rec))

        print("\n  Config:    {}".format(self.config_file))
        print("  Templates: {}/".format(TEMPLATE_DIR))

        if elapsed > 0:
            print("  Runtime:   {:.1f}s".format(elapsed))

        print("=" * 60 + "\n")

    def print_report(self):
        """Load existing config and print metrics report without re-running."""
        if not self.config_file.exists():
            print("No retention_config.json found. Run the agent first.")
            return

        try:
            with open(self.config_file) as f:
                config = json.load(f)
        except (json.JSONDecodeError, Exception) as e:
            print("Error reading config: {}".format(e))
            return

        print("\n" + "=" * 60)
        print("RETENTION ENGINEER — LATEST REPORT")
        print("=" * 60)
        print("  Version:    {}".format(config.get("version", "?")))
        print("  Updated:    {}".format(config.get("updated_at", "?")))

        metrics = config.get("metrics", {})
        targets = {
            "return_rate": 30, "gallery_usage": 50,
            "share_rate": 10, "export_rate": 70}

        for name, target in targets.items():
            value = metrics.get(name, 0.0)
            status = "PASS" if value >= target else "BELOW"
            bar_len = int(min(value / target, 1.0) * 20)
            bar = "#" * bar_len + "-" * (20 - bar_len)
            print("  {:20s} {:6.1f}% / {}%  [{}]  {}".format(
                name, value, target, bar, status))

        features = config.get("features", {})
        print("\n  Features:")
        for k, v in features.items():
            print("    {}: {}".format(k, v))

        ab = config.get("ab_tests", {})
        if ab.get("active_test"):
            print("\n  A/B Test: {}".format(ab["active_test"]))
            print("    Variants: {}".format(
                json.dumps(ab.get("variants", {}))))
            print("    Split: {}".format(ab.get("traffic_split", 0.5)))

        recs = config.get("recommendations", [])
        if recs:
            print("\n  Recommendations:")
            for i, rec in enumerate(recs, 1):
                print("    {}. {}".format(i, rec))

        print("=" * 60 + "\n")


# ======================================================================
# Singleton
# ======================================================================

_agent: Optional[RetentionEngineer] = None


def get_retention_engineer() -> RetentionEngineer:
    """Get the global retention engineer instance."""
    global _agent
    if _agent is None:
        _agent = RetentionEngineer()
    return _agent


# ======================================================================
# CLI
# ======================================================================

if __name__ == "__main__":
    agent = RetentionEngineer()

    if len(sys.argv) > 1 and sys.argv[1] == "report":
        agent.print_report()
    else:
        agent.run()
