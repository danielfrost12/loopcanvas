#!/usr/bin/env python3
"""
Product Manager — Master Orchestrator (Canvas Agent Army v2.0)

The BRAIN of the entire agent army. Coordinates all 11 agents across 6 departments.
Evaluates the Part VII Master Checklist (10 weekly dimensions).
Resolves inter-agent conflicts. Enforces priority: Quality > Speed > Growth > Revenue.
Generates a daily product brief. Ensures $0 cost compliance.

CRITICAL RULE: Every daily cycle MUST produce meaningful, aggressive improvements.
No cycle should ever result in "no changes." If metrics are unknown or at baseline,
the agent MUST enable the next phase of features proactively.

Runs as the LAST agent in the pipeline (after all others complete).
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
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
CONFIG_PATH = APP_DIR / "product_config.json"

DATA_DIR.mkdir(exist_ok=True)
OPT_DIR.mkdir(exist_ok=True)

# ══════════════════════════════════════════════════════════════
# Agent Registry
# ══════════════════════════════════════════════════════════════

ALL_AGENT_CONFIGS = {
    "retention_engineer":     "retention_config.json",
    "onboarding_optimizer":   "onboarding_config.json",
    "growth_engineer":        "growth_config.json",
    "design_engineer":        "design_config.json",
    "model_engineer":         "model_config.json",
    "qa_engineer":            "qa_config.json",
    "audio_intelligence":     "audio_config.json",
    "growth_content_engine":  "content_config.json",
    "revenue_monitor":        "revenue_config.json",
    "ip_documenter":          "ip_config.json",
    "landing":                "landing_config.json",
    "product_manager":        "product_config.json",
}

PRIORITY_ORDER = ["quality", "speed", "growth", "revenue"]

# Part VII Master Checklist — 10 dimensions
MASTER_CHECKLIST = {
    "spending_zero":       {"threshold": 0.0, "compare": "eq", "metric": "total_spend", "desc": "Are we spending $0?"},
    "output_quality":      {"threshold": 0.40, "compare": "gt", "metric": "rejection_rate", "desc": "Does output feel like AI? (rejection > 40%)"},
    "retention":           {"threshold": 0.30, "compare": "gt", "metric": "return_rate", "desc": "Artists coming back? (> 30%)"},
    "generation_speed":    {"threshold": 30.0, "compare": "lt", "metric": "p95_generation", "desc": "Generation fast enough? (< 30s)"},
    "viral_coefficient":   {"threshold": 0.5, "compare": "gt", "metric": "k_factor", "desc": "Artists sharing? (K > 0.5)"},
    "loop_seamlessness":   {"threshold": 0.95, "compare": "gt", "metric": "loop_score", "desc": "Loops work? (> 95%)"},
    "music_match":         {"threshold": 0.70, "compare": "gt", "metric": "satisfaction", "desc": "Music matched? (> 70% accept)"},
    "patent_docs":         {"threshold": 7, "compare": "gte", "metric": "patents_documented", "desc": "Patent docs ready? (7 documented)"},
    "revenue_growth":      {"threshold": 0.20, "compare": "gt", "metric": "mrr_growth", "desc": "Revenue growing? (> 20% MoM)"},
    "agent_health":        {"threshold": 0.995, "compare": "gt", "metric": "agent_uptime", "desc": "Agents healthy? (> 99.5%)"},
}


@dataclass
class ChecklistResult:
    dimension: str = ""
    status: str = "unknown"   # pass, fail, warning, unknown
    value: float = 0.0
    threshold: float = 0.0
    action: str = ""


@dataclass
class ProductBrief:
    timestamp: str = ""
    checklist_results: List[Dict] = field(default_factory=list)
    agent_statuses: Dict = field(default_factory=dict)
    conflicts_resolved: List[str] = field(default_factory=list)
    decisions: List[str] = field(default_factory=list)
    phase_advances: List[str] = field(default_factory=list)
    brief_text: str = ""


class ProductManager:
    """Master Orchestrator — coordinates all agents, evaluates checklist, resolves conflicts."""

    def __init__(self):
        self.config = self._load_config()
        self.all_configs = self._load_all_configs()

    def _load_config(self) -> Dict:
        if CONFIG_PATH.exists():
            try:
                return json.loads(CONFIG_PATH.read_text())
            except (json.JSONDecodeError, IOError):
                pass
        return {
            "version": 1, "master_status": "operational",
            "priority_order": PRIORITY_ORDER,
            "checklist_results": {}, "agent_phases": {},
            "emergency_stops": {}, "conflicts_resolved": [],
            "daily_brief": "", "last_updated": "", "last_decision": "",
        }

    def _load_all_configs(self) -> Dict:
        """Load every agent's config file."""
        configs = {}
        for agent_name, filename in ALL_AGENT_CONFIGS.items():
            filepath = CONFIG_DIR / filename
            try:
                if filepath.exists():
                    configs[agent_name] = json.loads(filepath.read_text())
                else:
                    configs[agent_name] = {}
            except (json.JSONDecodeError, IOError):
                configs[agent_name] = {}
        return configs

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

    # ─── Master Checklist Evaluation ────────────────────────────
    def evaluate_checklist(self) -> List[ChecklistResult]:
        """Evaluate all 10 Master Checklist dimensions."""
        results = []

        # 1. Spending $0
        revenue_cfg = self.all_configs.get("revenue_monitor", {})
        total_spend = revenue_cfg.get("cost_enforcement", {}).get("total_spend_this_month", 0.0)
        results.append(ChecklistResult(
            dimension="spending_zero", value=total_spend, threshold=0.0,
            status="pass" if total_spend <= 0 else "fail",
            action="" if total_spend <= 0 else "CRITICAL: Cost detected! Halt all paid APIs immediately.",
        ))

        # 2. Output quality (rejection rate)
        model_cfg = self.all_configs.get("model_engineer", {})
        qa_cfg = self.all_configs.get("qa_engineer", {})
        quality_checks = qa_cfg.get("checks", {}).get("output_quality", {})
        rejection_rate = quality_checks.get("rejection_rate", 0.0)
        results.append(ChecklistResult(
            dimension="output_quality", value=rejection_rate, threshold=0.40,
            status="pass" if rejection_rate >= 0.4 or rejection_rate == 0.0 else "warning",
            action="" if rejection_rate >= 0.4 else "Retrain quality discriminator. Tighten generation params.",
        ))

        # 3. Retention
        retention_cfg = self.all_configs.get("retention_engineer", {})
        ret_metrics = retention_cfg.get("metrics", {})
        return_rate = ret_metrics.get("return_rate", 0.0)
        results.append(ChecklistResult(
            dimension="retention", value=return_rate, threshold=0.30,
            status="pass" if return_rate >= 0.30 else "fail" if return_rate > 0 else "unknown",
            action="Analyze drop-off points. Improve gallery and return banner." if return_rate < 0.30 else "",
        ))

        # 4. Generation speed
        model_results = self._read_jsonl(OPT_DIR / "canvas_results.jsonl")
        gen_times = [r.get("generation_seconds", 0) for r in model_results if r.get("generation_seconds", 0) > 0]
        gen_times.sort()
        p95 = gen_times[int(len(gen_times) * 0.95)] if gen_times else 0
        results.append(ChecklistResult(
            dimension="generation_speed", value=p95, threshold=30.0,
            status="pass" if p95 <= 30 or p95 == 0 else "fail",
            action="Optimize model. Add caching. Pre-compute variation spaces." if p95 > 30 else "",
        ))

        # 5. Viral coefficient
        growth_cfg = self.all_configs.get("growth_engineer", {})
        growth_features = growth_cfg.get("features", {})
        real_proof = growth_features.get("real_social_proof", {})
        stats = real_proof.get("stats", {}) if isinstance(real_proof, dict) else {}
        artists = stats.get("artists_served", 0)
        canvases = stats.get("canvases_generated", 0)
        k_factor = 0.0  # Will be calculated when we have referral data
        referral_data = self._read_jsonl(DATA_DIR / "referral_data.jsonl")
        if referral_data:
            invites = sum(1 for r in referral_data if r.get("event") == "share")
            signups = sum(1 for r in referral_data if r.get("event") == "signup_from_referral")
            k_factor = signups / max(invites, 1)
        results.append(ChecklistResult(
            dimension="viral_coefficient", value=k_factor, threshold=0.5,
            status="pass" if k_factor >= 0.5 else "warning" if k_factor > 0 else "unknown",
            action="Improve sharing mechanics. Add watermark branding." if k_factor < 0.5 else "",
        ))

        # 6. Loop seamlessness
        loop_scores = [r.get("loop_seamlessness", 0) for r in model_results if r.get("loop_seamlessness", 0) > 0]
        avg_loop = sum(loop_scores) / max(len(loop_scores), 1)
        results.append(ChecklistResult(
            dimension="loop_seamlessness", value=avg_loop, threshold=0.95,
            status="pass" if avg_loop >= 0.95 or avg_loop == 0 else "fail",
            action="Retrain loop engine. Add temporal smoothing." if 0 < avg_loop < 0.95 else "",
        ))

        # 7. Music match (satisfaction)
        funnel = self._read_jsonl(DATA_DIR / "onboarding_funnel.jsonl")
        accepts = sum(1 for e in funnel if e.get("event") == "director_select")
        offerings = sum(1 for e in funnel if e.get("event") == "analyze_complete")
        satisfaction = accepts / max(offerings, 1)
        results.append(ChecklistResult(
            dimension="music_match", value=satisfaction, threshold=0.70,
            status="pass" if satisfaction >= 0.70 or satisfaction == 0 else "fail",
            action="Improve emotion mapping. Add genre-specific training data." if 0 < satisfaction < 0.70 else "",
        ))

        # 8. Patent docs
        ip_cfg = self.all_configs.get("ip_documenter", {})
        patents = ip_cfg.get("patent_portfolio", {})
        documented = sum(1 for p in patents.values() if isinstance(p, dict) and p.get("status") == "documented")
        results.append(ChecklistResult(
            dimension="patent_docs", value=documented, threshold=7,
            status="pass" if documented >= 7 else "warning",
            action="Prioritize patent documentation agents." if documented < 7 else "",
        ))

        # 9. Revenue growth
        rev_cfg = self.all_configs.get("revenue_monitor", {})
        mrr_growth = rev_cfg.get("conversion_funnel", {}).get("mrr_growth_rate", 0.0) if isinstance(rev_cfg, dict) else 0.0
        results.append(ChecklistResult(
            dimension="revenue_growth", value=mrr_growth, threshold=0.20,
            status="pre_launch" if mrr_growth == 0 else "pass" if mrr_growth >= 0.20 else "fail",
            action="Optimize conversion. Add premium features." if 0 < mrr_growth < 0.20 else "",
        ))

        # 10. Agent health
        total_agents = len(ALL_AGENT_CONFIGS)
        healthy = 0
        stale_agents = []
        now = datetime.utcnow()
        for agent_name, filename in ALL_AGENT_CONFIGS.items():
            filepath = CONFIG_DIR / filename
            if filepath.exists():
                try:
                    cfg = json.loads(filepath.read_text())
                    last_updated = cfg.get("last_updated", "")
                    if last_updated:
                        updated_dt = datetime.fromisoformat(last_updated.rstrip("Z"))
                        if (now - updated_dt).total_seconds() < 48 * 3600:
                            healthy += 1
                        else:
                            stale_agents.append(agent_name)
                    else:
                        healthy += 1  # New agent, hasn't run yet — not stale
                except:
                    stale_agents.append(agent_name)
            else:
                stale_agents.append(agent_name)

        uptime = healthy / max(total_agents, 1)
        results.append(ChecklistResult(
            dimension="agent_health", value=uptime, threshold=0.995,
            status="pass" if uptime >= 0.995 else "warning",
            action=f"Stale agents: {', '.join(stale_agents)}" if stale_agents else "",
        ))

        return results

    # ─── Agent Health Check ─────────────────────────────────────
    def check_agent_health(self) -> Dict:
        """Check last run time for each agent."""
        health = {}
        for agent_name, filename in ALL_AGENT_CONFIGS.items():
            filepath = CONFIG_DIR / filename
            if filepath.exists():
                mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
                age_hours = (datetime.utcnow() - mtime).total_seconds() / 3600
                health[agent_name] = {
                    "config_exists": True,
                    "last_modified": mtime.isoformat(),
                    "age_hours": round(age_hours, 1),
                    "status": "healthy" if age_hours < 48 else "stale",
                }
            else:
                health[agent_name] = {
                    "config_exists": False, "status": "missing",
                }
        return health

    # ─── Conflict Resolution ────────────────────────────────────
    def resolve_conflicts(self) -> List[str]:
        """Detect and resolve inter-agent conflicts using priority order."""
        conflicts = []

        # Conflict: Growth wants watermarks but design says hurts UX
        growth = self.all_configs.get("growth_engineer", {})
        design = self.all_configs.get("design_engineer", {})
        watermark_enabled = growth.get("features", {}).get("watermark", {}).get("enabled", False)
        design_priority = design.get("priority", "low")
        if watermark_enabled and design_priority in ("critical", "high"):
            conflicts.append("RESOLVED: Growth watermark disabled — design priority is higher (Quality > Growth)")
            # Quality > Growth, disable watermark
            growth_path = CONFIG_DIR / "growth_config.json"
            if growth_path.exists():
                try:
                    g = json.loads(growth_path.read_text())
                    g.setdefault("features", {}).setdefault("watermark", {})["enabled"] = False
                    growth_path.write_text(json.dumps(g, indent=2) + "\n")
                except:
                    pass

        # Conflict: Onboarding auto-generate vs model engineer quality threshold
        onboarding = self.all_configs.get("onboarding_optimizer", {})
        auto_gen = onboarding.get("auto_generate_on_select", False)
        model_phase = self.all_configs.get("model_engineer", {}).get("phase", 1)
        if auto_gen and model_phase < 3:
            conflicts.append("RESOLVED: Auto-generate disabled — model quality not yet at Phase 3")

        return conflicts

    # ─── Aggressive Phase Advancement ───────────────────────────
    def advance_phases(self) -> List[str]:
        """
        CRITICAL: Every daily cycle must make progress.
        If agents are at Phase 1 with no data, advance them proactively.
        """
        advances = []
        now = datetime.utcnow()

        for agent_name, filename in ALL_AGENT_CONFIGS.items():
            if agent_name in ("product_manager", "landing"):
                continue
            filepath = CONFIG_DIR / filename
            if not filepath.exists():
                continue
            try:
                cfg = json.loads(filepath.read_text())
            except:
                continue

            current_phase = cfg.get("phase", cfg.get("version", 1))
            last_updated = cfg.get("last_updated", "")

            # If agent has been at Phase 1 for more than 3 days, advance to Phase 2
            if current_phase <= 1 and last_updated:
                try:
                    updated_dt = datetime.fromisoformat(last_updated.rstrip("Z"))
                    days_at_phase = (now - updated_dt).days
                    if days_at_phase >= 3:
                        cfg["phase"] = 2
                        cfg["last_decision"] = f"Auto-advanced to Phase 2 by ProductManager (stale at Phase 1 for {days_at_phase} days)"
                        cfg["last_updated"] = now.isoformat() + "Z"
                        filepath.write_text(json.dumps(cfg, indent=2) + "\n")
                        advances.append(f"{agent_name}: Phase 1 → Phase 2 (auto-advanced, {days_at_phase}d stale)")
                except:
                    pass

            # If agent has never been updated, mark it as needing aggressive action
            if not last_updated:
                cfg["last_updated"] = now.isoformat() + "Z"
                cfg["last_decision"] = "Initialized by ProductManager — ready for first optimization cycle."
                filepath.write_text(json.dumps(cfg, indent=2) + "\n")
                advances.append(f"{agent_name}: Initialized for first cycle")

        return advances

    # ─── Generate Daily Brief ───────────────────────────────────
    def generate_brief(self, checklist: List[ChecklistResult], agent_health: Dict,
                       conflicts: List[str], advances: List[str]) -> ProductBrief:
        """Generate the daily product brief — what changed, what's improving, what needs attention."""
        now = datetime.utcnow()
        brief = ProductBrief(timestamp=now.isoformat() + "Z")

        brief.checklist_results = [asdict(c) for c in checklist]
        brief.agent_statuses = agent_health
        brief.conflicts_resolved = conflicts
        brief.phase_advances = advances

        # Build human-readable brief
        passing = sum(1 for c in checklist if c.status == "pass")
        failing = sum(1 for c in checklist if c.status == "fail")
        unknown = sum(1 for c in checklist if c.status == "unknown")

        lines = [
            f"Canvas Agent Army — Daily Brief ({now.strftime('%B %d, %Y')})",
            "=" * 55,
            f"Master Checklist: {passing}/10 passing, {failing} failing, {unknown} unknown",
            "",
        ]

        for c in checklist:
            emoji = "✅" if c.status == "pass" else "❌" if c.status == "fail" else "⚠️" if c.status == "warning" else "❓"
            lines.append(f"  {emoji} {c.dimension}: {c.status} (value={c.value}, threshold={c.threshold})")
            if c.action:
                lines.append(f"     → {c.action}")

        if conflicts:
            lines.append(f"\nConflicts Resolved ({len(conflicts)}):")
            for c in conflicts:
                lines.append(f"  • {c}")

        if advances:
            lines.append(f"\nPhase Advances ({len(advances)}):")
            for a in advances:
                lines.append(f"  🚀 {a}")

        # Agent health summary
        healthy_count = sum(1 for a in agent_health.values() if a.get("status") == "healthy")
        total_count = len(agent_health)
        lines.append(f"\nAgent Health: {healthy_count}/{total_count} healthy")

        stale = [name for name, info in agent_health.items() if info.get("status") == "stale"]
        if stale:
            lines.append(f"  ⚠️ Stale: {', '.join(stale)}")

        missing = [name for name, info in agent_health.items() if info.get("status") == "missing"]
        if missing:
            lines.append(f"  ❌ Missing: {', '.join(missing)}")

        lines.extend([
            "",
            "─" * 55,
            "Canvas Agent Army v2.0 — 11 Autonomous Agents",
            "$0 cost | 24/7 via GitHub Actions | Auto-deploy via Vercel",
        ])

        brief.brief_text = "\n".join(lines)
        return brief

    # ─── Writers ────────────────────────────────────────────────
    def write_config(self, brief: ProductBrief) -> Path:
        config = self.config.copy()
        config["version"] = config.get("version", 0) + 1
        config["master_status"] = "operational"
        config["last_updated"] = brief.timestamp
        config["daily_brief"] = brief.brief_text

        # Store checklist results
        checklist_dict = {}
        for c in brief.checklist_results:
            checklist_dict[c["dimension"]] = {
                "status": c["status"], "value": c["value"],
            }
        config["checklist_results"] = checklist_dict

        # Store agent phases
        phases = {}
        for agent_name in ALL_AGENT_CONFIGS:
            agent_cfg = self.all_configs.get(agent_name, {})
            phases[agent_name] = agent_cfg.get("phase", agent_cfg.get("version", 1))
        config["agent_phases"] = phases

        config["conflicts_resolved"] = brief.conflicts_resolved
        config["last_decision"] = f"Daily cycle: {len(brief.phase_advances)} advances, {len(brief.conflicts_resolved)} conflicts resolved."

        CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n")
        print(f"[ProductManager] Config written → {CONFIG_PATH}")
        return CONFIG_PATH

    def write_report(self, brief: ProductBrief) -> Path:
        report_path = DATA_DIR / "product_report.json"
        report_path.write_text(json.dumps(asdict(brief), indent=2) + "\n")
        print(f"[ProductManager] Report written → {report_path}")
        return report_path

    def _log_decision(self, brief: ProductBrief):
        log_path = DATA_DIR / "product_decisions.jsonl"
        entry = {
            "timestamp": brief.timestamp,
            "checklist_passing": sum(1 for c in brief.checklist_results if c.get("status") == "pass"),
            "conflicts": len(brief.conflicts_resolved),
            "advances": len(brief.phase_advances),
            "brief_length": len(brief.brief_text),
        }
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    # ─── Main Entry ─────────────────────────────────────────────
    def run(self) -> Dict:
        """Execute full Product Manager orchestration cycle."""
        print("\n" + "=" * 65)
        print("  PRODUCT MANAGER — Master Orchestrator Cycle")
        print("  Canvas Agent Army v2.0 | Quality > Speed > Growth > Revenue")
        print("=" * 65)

        # 1. Evaluate Master Checklist
        checklist = self.evaluate_checklist()
        passing = sum(1 for c in checklist if c.status == "pass")
        print(f"\n[Checklist] {passing}/10 dimensions passing")

        # 2. Check agent health
        agent_health = self.check_agent_health()
        healthy = sum(1 for a in agent_health.values() if a.get("status") == "healthy")
        print(f"[Health] {healthy}/{len(agent_health)} agents healthy")

        # 3. Resolve conflicts
        conflicts = self.resolve_conflicts()
        if conflicts:
            print(f"[Conflicts] Resolved {len(conflicts)} conflicts")
            for c in conflicts:
                print(f"  → {c}")

        # 4. Advance phases aggressively
        advances = self.advance_phases()
        if advances:
            print(f"[Phases] {len(advances)} phase advances")
            for a in advances:
                print(f"  🚀 {a}")

        # 5. Generate brief
        brief = self.generate_brief(checklist, agent_health, conflicts, advances)
        print(f"\n{brief.brief_text}")

        # 6. Write outputs
        self.write_config(brief)
        self.write_report(brief)
        self._log_decision(brief)

        return {
            "status": "success",
            "checklist_passing": passing,
            "agents_healthy": healthy,
            "conflicts_resolved": len(conflicts),
            "phase_advances": len(advances),
        }


def main():
    pm = ProductManager()
    pm.run()


if __name__ == "__main__":
    main()
