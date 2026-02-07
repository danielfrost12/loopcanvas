#!/usr/bin/env python3
"""
Revenue & Monetization Lead — Canvas Agent Army v2.0

Tracks P&L in real-time. Enforces $0 cost ceiling. Optimizes conversion funnel.
IRON RULE: No Spend Until Revenue.

"Every agent must check the $0 constraint before taking any action that incurs cost.
The Master Orchestrator maintains a real-time P&L. No agent can spend more than
the company earns." — Canvas Agent Army Spec

Pricing Tiers:
  Free: 3 canvases/month, watermarked
  Artist ($9.99/mo): Unlimited, unwatermarked, basic export
  Pro ($29.99/mo): 4K, music video editor, all platforms
  Enterprise: Custom pricing, API access, team collaboration

Phases:
  Phase 1: Track costs only, enforce $0
  Phase 2: Conversion funnel analysis
  Phase 3: Pricing optimization, A/B tests
  Phase 4: Enterprise sales pipeline, expansion revenue
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict

# ══════════════════════════════════════════════════════════════
# Paths
# ══════════════════════════════════════════════════════════════

ENGINE_DIR = Path(__file__).parent.parent
APP_DIR = ENGINE_DIR.parent
DATA_DIR = ENGINE_DIR / "checklist_data"
OPT_DIR = ENGINE_DIR / "optimization_data"
CONFIG_DIR = APP_DIR
CONFIG_PATH = APP_DIR / "revenue_config.json"

DATA_DIR.mkdir(exist_ok=True)
OPT_DIR.mkdir(exist_ok=True)

# ══════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════

PRICING_TIERS = {
    "free":       {"price": 0,       "canvases_per_month": 3,  "watermark": True,  "formats": ["spotify_canvas"]},
    "artist":     {"price": 9.99,    "canvases_per_month": -1, "watermark": False, "formats": ["spotify_canvas", "apple_music", "tiktok"]},
    "pro":        {"price": 29.99,   "canvases_per_month": -1, "watermark": False, "formats": "all"},
    "enterprise": {"price": "custom", "canvases_per_month": -1, "watermark": False, "formats": "all"},
}

COST_CENTERS = [
    "compute_gpu", "hosting_vercel", "database", "cdn",
    "email", "analytics", "ci_cd", "storage",
]

FREE_TIER_LIMITS = {
    "compute_gpu":     {"provider": "Google Colab / Kaggle", "limit": "30 hrs/week GPU"},
    "hosting_vercel":  {"provider": "Vercel Free", "limit": "100GB bandwidth/mo"},
    "database":        {"provider": "Supabase Free", "limit": "500MB / 1B reads"},
    "cdn":             {"provider": "Cloudflare Free", "limit": "Unlimited"},
    "email":           {"provider": "Resend Free", "limit": "3,000 emails/mo"},
    "analytics":       {"provider": "PostHog Free", "limit": "1M events/mo"},
    "ci_cd":           {"provider": "GitHub Actions", "limit": "2,000 min/mo"},
    "storage":         {"provider": "Cloudflare R2", "limit": "10GB free"},
}


# ══════════════════════════════════════════════════════════════
# Data Structures
# ══════════════════════════════════════════════════════════════

@dataclass
class RevenueMetrics:
    total_revenue: float = 0.0
    total_costs: float = 0.0
    monthly_revenue: float = 0.0
    monthly_costs: float = 0.0
    free_users: int = 0
    paid_users: int = 0
    free_to_paid_rate: float = 0.0
    churn_rate: float = 0.0
    mrr: float = 0.0
    mrr_growth_rate: float = 0.0
    cost_per_center: Dict[str, float] = field(default_factory=dict)
    conversion_funnel: Dict[str, float] = field(default_factory=dict)
    at_risk_users: int = 0


@dataclass
class RevenueDecision:
    timestamp: str = ""
    phase: int = 1
    cost_alerts: List[str] = field(default_factory=list)
    pricing_changes: Dict = field(default_factory=dict)
    conversion_actions: List[str] = field(default_factory=list)
    cost_enforcement: Dict = field(default_factory=dict)
    reasoning: str = ""
    metrics_snapshot: Dict = field(default_factory=dict)


# ══════════════════════════════════════════════════════════════
# Revenue Monitor
# ══════════════════════════════════════════════════════════════

class RevenueMonitor:
    """Autonomous P&L tracker and $0 cost enforcer."""

    def __init__(self):
        self.metrics = RevenueMetrics()
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        if CONFIG_PATH.exists():
            try:
                return json.loads(CONFIG_PATH.read_text())
            except (json.JSONDecodeError, IOError):
                pass
        return {
            "version": 1, "phase": 1,
            "cost_enforcement": {
                "hard_block": True, "allowed_paid_apis": [],
                "total_spend_this_month": 0.0, "alert_threshold": 0.01,
                "monthly_revenue": 0.0,
            },
            "pricing_tiers": PRICING_TIERS,
            "conversion_funnel": {},
            "startup_credits": {"aws_activate": "pending", "gcp_startups": "pending", "azure_startups": "pending"},
            "last_updated": "", "last_decision": "",
        }

    def _read_jsonl(self, filepath: Path) -> List[Dict]:
        entries = []
        if not filepath.exists():
            return entries
        try:
            for line in filepath.read_text().splitlines():
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except IOError:
            pass
        return entries

    # ─── Cost Compliance ────────────────────────────────────────
    def check_cost_compliance(self) -> List[str]:
        """Verify $0 spend across all cost centers."""
        alerts = []
        total_spend = 0.0

        for center in COST_CENTERS:
            # Check if any cost data exists
            cost_file = DATA_DIR / f"cost_{center}.jsonl"
            entries = self._read_jsonl(cost_file)
            center_spend = sum(e.get("cost", 0.0) for e in entries)
            total_spend += center_spend

            if center_spend > 0:
                alerts.append(f"COST ALERT: {center} = ${center_spend:.4f}. Must be $0.")

        # Check all agent configs for any paid API usage
        for cfg_name in ["model_config.json", "audio_config.json", "growth_config.json"]:
            cfg_path = CONFIG_DIR / cfg_name
            if cfg_path.exists():
                try:
                    cfg = json.loads(cfg_path.read_text())
                    if cfg.get("paid_api_calls", 0) > 0:
                        alerts.append(f"COST ALERT: {cfg_name} reports paid API calls!")
                except:
                    pass

        if total_spend > 0:
            alerts.insert(0, f"CRITICAL: Total spend this month = ${total_spend:.4f}. MUST BE $0.")
        else:
            alerts.append("✅ $0 spend confirmed across all cost centers.")

        return alerts

    # ─── Conversion Tracking ────────────────────────────────────
    def track_conversions(self) -> Dict[str, float]:
        """Track free → paid conversion funnel."""
        activity = self._read_jsonl(DATA_DIR / "user_activity.jsonl")

        unique_users = set()
        paid_users = set()
        churned = set()

        for e in activity:
            user_id = e.get("user_id", e.get("session_id", ""))
            if user_id:
                unique_users.add(user_id)
            if e.get("event") == "upgrade":
                paid_users.add(user_id)
            if e.get("event") == "churn":
                churned.add(user_id)

        total = max(len(unique_users), 1)
        funnel = {
            "total_users": len(unique_users),
            "free_users": len(unique_users) - len(paid_users),
            "paid_users": len(paid_users),
            "free_to_paid_rate": len(paid_users) / total,
            "churn_rate": len(churned) / max(len(paid_users), 1),
        }

        self.metrics.free_users = funnel["free_users"]
        self.metrics.paid_users = funnel["paid_users"]
        self.metrics.free_to_paid_rate = funnel["free_to_paid_rate"]
        self.metrics.churn_rate = funnel["churn_rate"]

        return funnel

    # ─── Analysis ───────────────────────────────────────────────
    def analyze(self) -> RevenueMetrics:
        """Full revenue analysis."""
        cost_alerts = self.check_cost_compliance()
        funnel = self.track_conversions()

        # MRR calculation
        self.metrics.mrr = self.metrics.paid_users * 9.99  # Assuming artist tier average
        self.metrics.monthly_revenue = self.metrics.mrr
        self.metrics.total_revenue = self.metrics.mrr  # Simplified for now

        # Cost per center
        total_cost = 0.0
        for center in COST_CENTERS:
            cost_file = DATA_DIR / f"cost_{center}.jsonl"
            entries = self._read_jsonl(cost_file)
            center_cost = sum(e.get("cost", 0.0) for e in entries)
            self.metrics.cost_per_center[center] = center_cost
            total_cost += center_cost

        self.metrics.monthly_costs = total_cost
        self.metrics.total_costs = total_cost
        self.metrics.conversion_funnel = funnel

        return self.metrics

    # ─── Decision Engine ────────────────────────────────────────
    def decide(self, metrics: RevenueMetrics) -> RevenueDecision:
        decision = RevenueDecision(timestamp=datetime.utcnow().isoformat() + "Z")
        reasoning_parts = []

        # Phase determination
        if metrics.monthly_revenue == 0:
            decision.phase = 1
            reasoning_parts.append("Phase 1: Pre-revenue. Enforcing $0 cost ceiling.")
        elif metrics.mrr < 100:
            decision.phase = 2
            reasoning_parts.append(f"Phase 2: Early revenue (MRR ${metrics.mrr:.0f}). Analyzing conversion funnel.")
        elif metrics.mrr < 1000:
            decision.phase = 3
            reasoning_parts.append(f"Phase 3: Growing (MRR ${metrics.mrr:.0f}). Optimizing pricing.")
        else:
            decision.phase = 4
            reasoning_parts.append(f"Phase 4: Scaling (MRR ${metrics.mrr:.0f}). Enterprise pipeline active.")

        # Cost enforcement
        decision.cost_alerts = self.check_cost_compliance()
        decision.cost_enforcement = {
            "hard_block": True,
            "total_spend": metrics.monthly_costs,
            "total_revenue": metrics.monthly_revenue,
            "profit": metrics.monthly_revenue - metrics.monthly_costs,
            "status": "compliant" if metrics.monthly_costs <= 0 else "VIOLATION",
        }

        if metrics.monthly_costs > 0 and metrics.monthly_revenue <= 0:
            reasoning_parts.append(f"COST VIOLATION: ${metrics.monthly_costs:.4f} spend with $0 revenue!")
            decision.cost_enforcement["action"] = "HALT_ALL_PAID_APIS"

        # Conversion actions
        if metrics.free_to_paid_rate < 0.02 and metrics.free_users > 0:
            decision.conversion_actions.append("Add value prop messaging to free tier export screen")
            decision.conversion_actions.append("Show 'Upgrade for unwatermarked export' CTA")

        if metrics.churn_rate > 0.1:
            decision.conversion_actions.append("Implement retention email sequence for at-risk users")

        decision.reasoning = " ".join(reasoning_parts)
        decision.metrics_snapshot = asdict(metrics)
        return decision

    # ─── Writers ────────────────────────────────────────────────
    def write_config(self, decision: RevenueDecision) -> Path:
        config = self.config.copy()
        config["version"] = config.get("version", 0) + 1
        config["phase"] = decision.phase
        config["last_updated"] = decision.timestamp
        config["last_decision"] = decision.reasoning

        config["cost_enforcement"] = decision.cost_enforcement
        config["conversion_funnel"] = {
            "free_to_artist": self.metrics.free_to_paid_rate,
            "churn_rate": self.metrics.churn_rate,
            "mrr": self.metrics.mrr,
            "mrr_growth_rate": self.metrics.mrr_growth_rate,
        }

        CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n")
        print(f"[RevenueMonitor] Config written → {CONFIG_PATH}")
        return CONFIG_PATH

    def write_report(self, decision: RevenueDecision) -> Path:
        report = {
            "timestamp": decision.timestamp,
            "phase": decision.phase,
            "mrr": self.metrics.mrr,
            "total_costs": self.metrics.monthly_costs,
            "profit": self.metrics.mrr - self.metrics.monthly_costs,
            "cost_status": "compliant" if self.metrics.monthly_costs <= 0 else "VIOLATION",
            "cost_alerts": decision.cost_alerts,
            "conversion_funnel": self.metrics.conversion_funnel,
            "actions": decision.conversion_actions,
        }
        report_path = DATA_DIR / "revenue_report.json"
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        print(f"[RevenueMonitor] Report written → {report_path}")
        return report_path

    def _log_decision(self, decision: RevenueDecision):
        log_path = DATA_DIR / "revenue_decisions.jsonl"
        entry = {
            "timestamp": decision.timestamp,
            "phase": decision.phase,
            "mrr": self.metrics.mrr,
            "costs": self.metrics.monthly_costs,
            "alerts": len(decision.cost_alerts),
        }
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    # ─── Main Entry ─────────────────────────────────────────────
    def run(self) -> Dict:
        print("\n" + "=" * 65)
        print("  REVENUE MONITOR — P&L Tracking & $0 Enforcement Cycle")
        print("=" * 65)

        metrics = self.analyze()
        print(f"\n[Analyze] MRR: ${metrics.mrr:.2f}, Costs: ${metrics.monthly_costs:.4f}")
        print(f"[Analyze] Users: {metrics.free_users} free, {metrics.paid_users} paid")
        print(f"[Analyze] Conversion: {metrics.free_to_paid_rate:.1%}, Churn: {metrics.churn_rate:.1%}")

        decision = self.decide(metrics)
        print(f"\n[Decide] {decision.reasoning}")

        if decision.cost_alerts:
            for alert in decision.cost_alerts:
                print(f"  💰 {alert}")

        self.write_config(decision)
        self.write_report(decision)
        self._log_decision(decision)

        result = {
            "status": "success",
            "phase": decision.phase,
            "mrr": metrics.mrr,
            "cost_compliant": metrics.monthly_costs <= 0,
            "reasoning": decision.reasoning,
        }

        summary_path = DATA_DIR / "revenue_summary.json"
        summary_path.write_text(json.dumps(result, indent=2) + "\n")

        print(f"\n{'─' * 65}")
        print(f"  RESULT: Phase {decision.phase} | MRR: ${metrics.mrr:.2f} | $0 {'✅' if metrics.monthly_costs <= 0 else '❌'}")
        print(f"{'=' * 65}\n")

        return result


def main():
    monitor = RevenueMonitor()
    monitor.run()


if __name__ == "__main__":
    main()
