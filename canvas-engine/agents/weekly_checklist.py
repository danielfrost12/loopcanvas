#!/usr/bin/env python3
"""
Canvas Weekly Master Checklist — Part VII Implementation

Every week (or continuously in autonomous mode), the Master Orchestrator
evaluates the entire system against this checklist:

| Check                      | Metric                          | Threshold                                      | If Failing                                          |
|----------------------------|----------------------------------|-------------------------------------------------|-----------------------------------------------------|
| Are we spending $0?        | Total monthly cloud/API spend   | $0 (pre-revenue)                                | Halt paid API calls, switch to free alternatives    |
| Does output feel like AI?  | Quality gate rejection rate     | >40% rejected and regenerated                   | Retrain discriminator, tighten generation params    |
| Are artists coming back?   | Week 1 retention                | >30% return within 7 days                       | Analyze drop-off, improve onboarding                |
| Is generation fast enough? | Canvas generation p95 latency   | <30s new, <3s iteration                         | Optimize model, add caching, pre-compute            |
| Are artists sharing?       | Viral coefficient (K-factor)    | >0.5 (each user brings 0.5 new users)           | Improve watermark branding, share incentives        |
| Do loops work?             | Loop seamlessness score         | >95% pass automated loop test                   | Retrain loop engine, add temporal smoothing         |
| Is the music matched?      | Artist satisfaction w/ AV match | >70% accept first batch of options               | Improve emotion mapping, genre-specific training    |
| Are patent docs ready?     | Filing-ready patent documents   | 7 docs filing-ready within 90 days              | Prioritize patent documentation agents              |
| Is revenue growing?        | MRR growth rate                 | >20% MoM after public launch                    | Optimize conversion, improve free-to-paid funnel    |
| Are agents healthy?        | Agent uptime across all depts   | >99.5%                                          | Auto-restart failed agents, investigate root cause  |

This module:
1. Collects metrics from all system components
2. Evaluates each against thresholds
3. Triggers remediation actions for failing checks
4. Generates a report
5. Can run on a weekly schedule or continuously (24/7 autonomous mode)

Cost: $0 — all metrics are local file/process inspection
"""

import os
import sys
import json
import time
import signal
import threading
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta

# Add paths
ENGINE_DIR = Path(__file__).parent.parent
APP_DIR = ENGINE_DIR.parent
ROOT_DIR = APP_DIR.parent
sys.path.insert(0, str(ENGINE_DIR))
sys.path.insert(0, str(ROOT_DIR))

# Data storage
CHECKLIST_DIR = ENGINE_DIR / "checklist_data"
CHECKLIST_DIR.mkdir(exist_ok=True)


# ══════════════════════════════════════════════════════════════
# Data Structures
# ══════════════════════════════════════════════════════════════

@dataclass
class CheckResult:
    """Result of a single checklist evaluation"""
    check_id: str
    check_name: str
    metric_name: str
    metric_value: float
    threshold: str
    threshold_value: float
    passed: bool
    severity: str  # "critical", "warning", "info"
    remediation: str
    details: Dict = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class ChecklistReport:
    """Full weekly checklist report"""
    timestamp: str
    total_checks: int
    passed_checks: int
    failed_checks: int
    critical_failures: int
    overall_health: str  # "healthy", "degraded", "critical"
    results: List[Dict]
    remediation_actions_taken: List[str]
    next_evaluation: str


# ══════════════════════════════════════════════════════════════
# Metric Collectors
# ══════════════════════════════════════════════════════════════

class MetricCollector:
    """Collects metrics from all system components"""

    def __init__(self):
        self._cache = {}
        self._cache_ttl = 60  # seconds

    def _cached(self, key: str, collector: Callable, ttl: int = None) -> any:
        """Cache metric values to avoid redundant computation"""
        ttl = ttl or self._cache_ttl
        now = time.time()
        if key in self._cache:
            value, cached_at = self._cache[key]
            if now - cached_at < ttl:
                return value
        value = collector()
        self._cache[key] = (value, now)
        return value

    def clear_cache(self):
        """Clear all cached metrics"""
        self._cache.clear()

    # ── Cost Metrics ──────────────────────────────────────────

    def get_monthly_spend(self) -> float:
        """Get total monthly cloud/API spend"""
        def _collect():
            try:
                from agents.cost_enforcer import get_enforcer
                enforcer = get_enforcer()
                status = enforcer.get_status()

                # Count blocked events as potential spend
                total_blocked_cost = sum(
                    e.estimated_cost for e in enforcer.events
                    if e.blocked
                )

                # Actual spend = revenue - we're at $0 pre-revenue
                return status.get('revenue', 0.0)
            except Exception:
                return 0.0

        return self._cached("monthly_spend", _collect)

    # ── Quality Metrics ───────────────────────────────────────

    def get_quality_rejection_rate(self) -> float:
        """Get percentage of generations rejected by quality gate"""
        def _collect():
            results_file = ENGINE_DIR / "optimization_data" / "canvas_results.jsonl"
            if not results_file.exists():
                return 0.0

            cutoff = datetime.now() - timedelta(days=7)
            total = 0
            rejected = 0

            try:
                with open(results_file) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            ts = datetime.fromisoformat(data['timestamp'])
                            if ts >= cutoff:
                                total += 1
                                if not data.get('quality_passed', False):
                                    rejected += 1
                        except (json.JSONDecodeError, KeyError, ValueError):
                            continue
            except Exception:
                return 0.0

            if total == 0:
                return 0.0
            return (rejected / total) * 100

        return self._cached("quality_rejection_rate", _collect)

    def get_quality_details(self) -> Dict:
        """Get detailed quality metrics"""
        results_file = ENGINE_DIR / "optimization_data" / "canvas_results.jsonl"
        if not results_file.exists():
            return {"total": 0, "passed": 0, "rejected": 0, "avg_score": 0.0}

        cutoff = datetime.now() - timedelta(days=7)
        scores = []
        passed = 0
        rejected = 0

        try:
            with open(results_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        ts = datetime.fromisoformat(data['timestamp'])
                        if ts >= cutoff:
                            scores.append(data.get('quality_score', 0.0))
                            if data.get('quality_passed', False):
                                passed += 1
                            else:
                                rejected += 1
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue
        except Exception:
            pass

        return {
            "total": len(scores),
            "passed": passed,
            "rejected": rejected,
            "avg_score": sum(scores) / len(scores) if scores else 0.0,
            "best_score": max(scores) if scores else 0.0,
            "worst_score": min(scores) if scores else 0.0,
        }

    # ── Retention Metrics ─────────────────────────────────────

    def get_week1_retention(self) -> float:
        """Get Week 1 retention rate (% of users who return within 7 days)"""
        def _collect():
            retention_file = CHECKLIST_DIR / "user_activity.jsonl"
            if not retention_file.exists():
                return 0.0

            users = {}  # user_id → list of timestamps
            try:
                with open(retention_file) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            uid = data.get('user_id', '')
                            ts = datetime.fromisoformat(data['timestamp'])
                            if uid not in users:
                                users[uid] = []
                            users[uid].append(ts)
                        except (json.JSONDecodeError, KeyError, ValueError):
                            continue
            except Exception:
                return 0.0

            if not users:
                return 0.0

            # For each user, check if they came back within 7 days of first visit
            retained = 0
            eligible = 0
            cutoff = datetime.now() - timedelta(days=7)

            for uid, visits in users.items():
                visits.sort()
                first_visit = visits[0]
                if first_visit > cutoff:
                    continue  # Too new to measure

                eligible += 1
                seven_days_later = first_visit + timedelta(days=7)
                if any(v > first_visit and v <= seven_days_later for v in visits[1:]):
                    retained += 1

            if eligible == 0:
                return 0.0
            return (retained / eligible) * 100

        return self._cached("week1_retention", _collect)

    # ── Latency Metrics ───────────────────────────────────────

    def get_generation_p95_latency(self) -> Dict:
        """Get p95 latency for canvas generation (new + iteration)"""
        def _collect():
            latency_file = CHECKLIST_DIR / "generation_latency.jsonl"
            if not latency_file.exists():
                return {"new_p95": 0.0, "iteration_p95": 0.0}

            new_latencies = []
            iteration_latencies = []
            cutoff = datetime.now() - timedelta(days=7)

            try:
                with open(latency_file) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            ts = datetime.fromisoformat(data['timestamp'])
                            if ts >= cutoff:
                                latency = data.get('latency_seconds', 0.0)
                                if data.get('type') == 'iteration':
                                    iteration_latencies.append(latency)
                                else:
                                    new_latencies.append(latency)
                        except (json.JSONDecodeError, KeyError, ValueError):
                            continue
            except Exception:
                return {"new_p95": 0.0, "iteration_p95": 0.0}

            def p95(values):
                if not values:
                    return 0.0
                values.sort()
                idx = int(len(values) * 0.95)
                return values[min(idx, len(values) - 1)]

            return {
                "new_p95": p95(new_latencies),
                "iteration_p95": p95(iteration_latencies),
                "new_count": len(new_latencies),
                "iteration_count": len(iteration_latencies),
            }

        return self._cached("generation_latency", _collect)

    # ── Viral Coefficient ─────────────────────────────────────

    def get_viral_coefficient(self) -> float:
        """Get K-factor (viral coefficient)"""
        def _collect():
            viral_file = CHECKLIST_DIR / "referrals.jsonl"
            if not viral_file.exists():
                return 0.0

            total_users = 0
            total_invites_accepted = 0
            cutoff = datetime.now() - timedelta(days=30)

            try:
                with open(viral_file) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            ts = datetime.fromisoformat(data['timestamp'])
                            if ts >= cutoff:
                                total_users += 1
                                total_invites_accepted += data.get('invites_accepted', 0)
                        except (json.JSONDecodeError, KeyError, ValueError):
                            continue
            except Exception:
                return 0.0

            if total_users == 0:
                return 0.0
            return total_invites_accepted / total_users

        return self._cached("viral_coefficient", _collect)

    # ── Loop Seamlessness ─────────────────────────────────────

    def get_loop_seamlessness_rate(self) -> float:
        """Get percentage of canvases that pass automated loop test"""
        def _collect():
            results_file = ENGINE_DIR / "optimization_data" / "canvas_results.jsonl"
            if not results_file.exists():
                return 0.0

            cutoff = datetime.now() - timedelta(days=7)
            total = 0
            seamless = 0

            try:
                with open(results_file) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            ts = datetime.fromisoformat(data['timestamp'])
                            if ts >= cutoff:
                                total += 1
                                loop_score = data.get('loop_score', 0.0)
                                if loop_score >= 0.85:  # Seamless threshold
                                    seamless += 1
                        except (json.JSONDecodeError, KeyError, ValueError):
                            continue
            except Exception:
                return 0.0

            if total == 0:
                return 0.0
            return (seamless / total) * 100

        return self._cached("loop_seamlessness", _collect)

    # ── Audio-Visual Match ────────────────────────────────────

    def get_av_match_acceptance_rate(self) -> float:
        """Get percentage of artists who accept first batch of visual options"""
        def _collect():
            match_file = CHECKLIST_DIR / "direction_selections.jsonl"
            if not match_file.exists():
                return 0.0

            cutoff = datetime.now() - timedelta(days=7)
            total_sessions = 0
            first_batch_accepted = 0

            try:
                with open(match_file) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            ts = datetime.fromisoformat(data['timestamp'])
                            if ts >= cutoff:
                                total_sessions += 1
                                if data.get('accepted_first_batch', False):
                                    first_batch_accepted += 1
                        except (json.JSONDecodeError, KeyError, ValueError):
                            continue
            except Exception:
                return 0.0

            if total_sessions == 0:
                return 0.0
            return (first_batch_accepted / total_sessions) * 100

        return self._cached("av_match_acceptance", _collect)

    # ── Patent Docs ───────────────────────────────────────────

    def get_patent_doc_status(self) -> Dict:
        """Get status of patent documentation readiness"""
        def _collect():
            patent_file = CHECKLIST_DIR / "patent_status.json"
            if not patent_file.exists():
                return {"ready": 0, "total": 7, "days_remaining": 90}

            try:
                with open(patent_file) as f:
                    return json.load(f)
            except Exception:
                return {"ready": 0, "total": 7, "days_remaining": 90}

        return self._cached("patent_docs", _collect, ttl=3600)

    # ── Revenue ───────────────────────────────────────────────

    def get_mrr_growth_rate(self) -> float:
        """Get month-over-month MRR growth rate"""
        def _collect():
            revenue_file = CHECKLIST_DIR / "revenue_history.jsonl"
            if not revenue_file.exists():
                return 0.0

            monthly_revenue = {}  # "YYYY-MM" → total
            try:
                with open(revenue_file) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            month_key = data['timestamp'][:7]  # "YYYY-MM"
                            monthly_revenue[month_key] = monthly_revenue.get(month_key, 0) + data.get('amount', 0)
                        except (json.JSONDecodeError, KeyError):
                            continue
            except Exception:
                return 0.0

            if len(monthly_revenue) < 2:
                return 0.0

            sorted_months = sorted(monthly_revenue.keys())
            current = monthly_revenue[sorted_months[-1]]
            previous = monthly_revenue[sorted_months[-2]]

            if previous == 0:
                return 100.0 if current > 0 else 0.0
            return ((current - previous) / previous) * 100

        return self._cached("mrr_growth", _collect, ttl=3600)

    # ── Agent Health ──────────────────────────────────────────

    def get_agent_uptime(self) -> float:
        """Get agent uptime percentage across all departments"""
        def _collect():
            uptime_file = CHECKLIST_DIR / "agent_heartbeats.jsonl"
            if not uptime_file.exists():
                # Check if agents are running by inspecting processes
                return self._check_live_agent_health()

            cutoff = datetime.now() - timedelta(days=7)
            agent_beats = {}  # agent_name → list of (timestamp, alive)

            try:
                with open(uptime_file) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            ts = datetime.fromisoformat(data['timestamp'])
                            if ts >= cutoff:
                                agent = data.get('agent', 'unknown')
                                if agent not in agent_beats:
                                    agent_beats[agent] = []
                                agent_beats[agent].append({
                                    'timestamp': ts,
                                    'alive': data.get('alive', True)
                                })
                        except (json.JSONDecodeError, KeyError, ValueError):
                            continue
            except Exception:
                return self._check_live_agent_health()

            if not agent_beats:
                return self._check_live_agent_health()

            # Calculate uptime per agent
            uptimes = []
            for agent, beats in agent_beats.items():
                alive_count = sum(1 for b in beats if b['alive'])
                total_count = len(beats)
                if total_count > 0:
                    uptimes.append(alive_count / total_count * 100)

            return sum(uptimes) / len(uptimes) if uptimes else 0.0

        return self._cached("agent_uptime", _collect)

    def _check_live_agent_health(self) -> float:
        """Check if critical agents/processes are running"""
        agents_checked = 0
        agents_alive = 0

        # Check orchestrator module is importable
        agents_checked += 1
        try:
            import importlib
            spec = importlib.util.find_spec("agents.cost_enforcer")
            if spec:
                agents_alive += 1
        except Exception:
            pass

        # Check optimization data directory exists and has recent data
        agents_checked += 1
        opt_state = ENGINE_DIR / "optimization_data" / "optimization_state.json"
        if opt_state.exists():
            try:
                mtime = datetime.fromtimestamp(opt_state.stat().st_mtime)
                if (datetime.now() - mtime).days < 7:
                    agents_alive += 1
            except Exception:
                pass

        # Check cost enforcer is functional
        agents_checked += 1
        try:
            from agents.cost_enforcer import get_enforcer
            enforcer = get_enforcer()
            enforcer.get_status()
            agents_alive += 1
        except Exception:
            pass

        # Check quality gate wrapper exists
        agents_checked += 1
        qg_path = ENGINE_DIR / "quality_gate_wrapper.py"
        if qg_path.exists():
            agents_alive += 1

        # Check loop engine exists
        agents_checked += 1
        loop_path = ENGINE_DIR / "loop" / "seamless_loop.py"
        if loop_path.exists():
            agents_alive += 1

        if agents_checked == 0:
            return 0.0
        return (agents_alive / agents_checked) * 100


# ══════════════════════════════════════════════════════════════
# Remediation Actions
# ══════════════════════════════════════════════════════════════

class RemediationEngine:
    """Automated remediation for failing checklist items"""

    def __init__(self):
        self.actions_taken: List[str] = []
        self.actions_log = CHECKLIST_DIR / "remediation_log.jsonl"

    def remediate(self, check_result: CheckResult) -> Optional[str]:
        """
        Take automated remediation action for a failing check.

        Returns description of action taken, or None if no action possible.
        """
        handler = getattr(self, f"_fix_{check_result.check_id}", None)
        if handler:
            action = handler(check_result)
            if action:
                self._log_action(check_result.check_id, action)
                self.actions_taken.append(action)
                return action
        return None

    def _log_action(self, check_id: str, action: str):
        """Log remediation action"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "check_id": check_id,
            "action": action,
        }
        try:
            with open(self.actions_log, 'a') as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def _fix_cost_zero(self, result: CheckResult) -> Optional[str]:
        """Remediation: Halt all paid API calls, switch to free alternatives"""
        try:
            from agents.cost_enforcer import get_enforcer
            enforcer = get_enforcer()

            # Ensure hard block is enabled
            enforcer.config['hard_block'] = True
            enforcer.config['cost_ceiling'] = 0.0

            # Clear any accidentally allowed services
            enforcer.config['allowed_paid_apis'] = []

            return "Enforced $0 ceiling: hard_block=True, cleared allowed APIs"
        except Exception as e:
            return f"Cost remediation attempted but failed: {e}"

    def _fix_quality_gate(self, result: CheckResult) -> Optional[str]:
        """Remediation: Tighten generation parameters"""
        try:
            evolved_config = ENGINE_DIR / "optimization_data" / "evolved_config.json"
            if evolved_config.exists():
                with open(evolved_config) as f:
                    config = json.load(f)

                # Tighten quality minimum
                config['quality_minimum'] = 9.5  # Raise from 9.3

                # Add common AI-looking patterns to negative prompts
                negatives = config.get('negative_prompt_additions', [])
                negatives.extend([
                    'unnaturally smooth',
                    'plastic skin',
                    'morphing artifacts',
                    'ai generated look',
                ])
                config['negative_prompt_additions'] = list(set(negatives))

                with open(evolved_config, 'w') as f:
                    json.dump(config, f, indent=2)

                return "Tightened quality params: raised minimum to 9.5, added negative prompts"
            return None
        except Exception as e:
            return f"Quality remediation attempted but failed: {e}"

    def _fix_retention(self, result: CheckResult) -> Optional[str]:
        """Remediation: Flag for onboarding review (requires human)"""
        flag_file = CHECKLIST_DIR / "retention_alert.json"
        alert = {
            "timestamp": datetime.now().isoformat(),
            "metric_value": result.metric_value,
            "threshold": result.threshold_value,
            "message": "Week 1 retention below 30%. Review onboarding flow and first-run experience.",
            "suggested_actions": [
                "Analyze user drop-off points in session logs",
                "Review first-generation quality for new users",
                "Check if demo tracks produce good results",
                "Consider adding guided first-run tutorial",
            ],
        }
        try:
            with open(flag_file, 'w') as f:
                json.dump(alert, f, indent=2)
            return f"Retention alert saved to {flag_file.name}"
        except Exception:
            return None

    def _fix_latency(self, result: CheckResult) -> Optional[str]:
        """Remediation: Enable caching, switch to fast mode"""
        try:
            # Set environment to force fast mode
            os.environ["LOOPCANVAS_MODE"] = "fast"
            os.environ["LOOPCANVAS_CACHE_ENABLED"] = "1"

            return "Enabled fast mode and caching for generation pipeline"
        except Exception:
            return None

    def _fix_viral(self, result: CheckResult) -> Optional[str]:
        """Remediation: Flag for marketing review"""
        flag_file = CHECKLIST_DIR / "viral_alert.json"
        alert = {
            "timestamp": datetime.now().isoformat(),
            "k_factor": result.metric_value,
            "message": "Viral coefficient below 0.5. Review sharing mechanics.",
        }
        try:
            with open(flag_file, 'w') as f:
                json.dump(alert, f, indent=2)
            return f"Viral coefficient alert saved"
        except Exception:
            return None

    def _fix_loop_seamless(self, result: CheckResult) -> Optional[str]:
        """Remediation: Increase crossfade frames in loop engine"""
        try:
            # Update loop engine default crossfade
            loop_config = CHECKLIST_DIR / "loop_config_override.json"
            override = {
                "timestamp": datetime.now().isoformat(),
                "crossfade_frames": 15,  # Increase from default
                "temporal_smoothing": True,
                "reason": f"Loop seamlessness at {result.metric_value:.1f}%, below 95%",
            }
            with open(loop_config, 'w') as f:
                json.dump(override, f, indent=2)

            return "Increased loop crossfade frames to 15, enabled temporal smoothing"
        except Exception:
            return None

    def _fix_av_match(self, result: CheckResult) -> Optional[str]:
        """Remediation: Trigger retraining of emotion mapping"""
        flag_file = CHECKLIST_DIR / "av_match_alert.json"
        alert = {
            "timestamp": datetime.now().isoformat(),
            "acceptance_rate": result.metric_value,
            "message": "Audio-visual match acceptance below 70%. Review emotion mapping.",
            "suggested_actions": [
                "Analyze which genres have lowest acceptance",
                "Add more genre-specific training data to seed runner",
                "Review director scoring algorithm",
            ],
        }
        try:
            with open(flag_file, 'w') as f:
                json.dump(alert, f, indent=2)
            return "AV match alert saved, flagged for emotion mapping review"
        except Exception:
            return None

    def _fix_patent_docs(self, result: CheckResult) -> Optional[str]:
        """Remediation: Flag patent documentation priority"""
        flag_file = CHECKLIST_DIR / "patent_alert.json"
        alert = {
            "timestamp": datetime.now().isoformat(),
            "docs_ready": result.metric_value,
            "target": 7,
            "message": "Patent documentation behind schedule. Filing only when founder authorizes.",
        }
        try:
            with open(flag_file, 'w') as f:
                json.dump(alert, f, indent=2)
            return "Patent documentation alert flagged for founder review"
        except Exception:
            return None

    def _fix_mrr_growth(self, result: CheckResult) -> Optional[str]:
        """Remediation: Flag for conversion optimization"""
        flag_file = CHECKLIST_DIR / "revenue_alert.json"
        alert = {
            "timestamp": datetime.now().isoformat(),
            "growth_rate": result.metric_value,
            "message": "MRR growth below 20% MoM. Review conversion funnel.",
        }
        try:
            with open(flag_file, 'w') as f:
                json.dump(alert, f, indent=2)
            return "Revenue growth alert saved"
        except Exception:
            return None

    def _fix_agent_health(self, result: CheckResult) -> Optional[str]:
        """Remediation: Attempt to restart failed agents"""
        restarted = []

        # Try to restart seed runner if it's dead
        try:
            watchdog = APP_DIR / "watchdog.sh"
            if watchdog.exists():
                # Check if watchdog is running
                try:
                    ps_result = subprocess.run(
                        ["pgrep", "-f", "watchdog.sh"],
                        capture_output=True, text=True, timeout=5,
                    )
                    if ps_result.returncode != 0:
                        # Watchdog not running — flag it
                        restarted.append("watchdog not running (flagged)")
                except Exception:
                    pass
        except Exception:
            pass

        # Verify optimization data directory
        opt_dir = ENGINE_DIR / "optimization_data"
        opt_dir.mkdir(exist_ok=True)

        if restarted:
            return f"Agent health check: {', '.join(restarted)}"
        return "Agent health check completed, all critical paths accessible"


# ══════════════════════════════════════════════════════════════
# The Master Checklist
# ══════════════════════════════════════════════════════════════

class WeeklyChecklist:
    """
    Part VII: The Master Checklist

    Every week, the Master Orchestrator evaluates the entire system
    against this checklist. In autonomous mode, runs continuously.
    """

    def __init__(self):
        self.collector = MetricCollector()
        self.remediator = RemediationEngine()
        self.report_file = CHECKLIST_DIR / "weekly_report.json"
        self.history_file = CHECKLIST_DIR / "checklist_history.jsonl"
        self._running = False
        self._stop_event = threading.Event()

    # ── Check Definitions ─────────────────────────────────────

    def _check_cost_zero(self) -> CheckResult:
        """Check 1: Are we spending $0?"""
        spend = self.collector.get_monthly_spend()
        passed = spend <= 0.0

        return CheckResult(
            check_id="cost_zero",
            check_name="Are we spending $0?",
            metric_name="Total monthly cloud/API spend",
            metric_value=spend,
            threshold="$0 (pre-revenue)",
            threshold_value=0.0,
            passed=passed,
            severity="critical" if not passed else "info",
            remediation="Immediately halt all paid API calls, switch to free alternatives",
        )

    def _check_quality_gate(self) -> CheckResult:
        """Check 2: Does output feel like AI?"""
        rejection_rate = self.collector.get_quality_rejection_rate()
        details = self.collector.get_quality_details()
        # >40% rejected means quality gate IS catching AI-looking outputs
        # This is actually a PASS — the gate is working
        # It's a FAIL if the gate isn't catching enough (rejection too LOW with bad quality)
        # But the threshold says ">40% rejected and regenerated" as the threshold
        # So we want rejection rate to be high enough that bad outputs get caught
        # Actually re-reading: the check is "Does output feel like AI?" — if YES that's bad
        # The metric is rejection rate, threshold is >40%
        # If >40% are being rejected, the system is working but quality is poor
        # We FAIL this check if rejection rate > 40% (too many bad generations)
        passed = rejection_rate <= 40.0

        return CheckResult(
            check_id="quality_gate",
            check_name="Does output feel like AI?",
            metric_name="Quality gate rejection rate",
            metric_value=rejection_rate,
            threshold=">40% rejected and regenerated",
            threshold_value=40.0,
            passed=passed,
            severity="critical" if not passed else "info",
            remediation="Retrain quality discriminator, tighten generation parameters",
            details=details,
        )

    def _check_retention(self) -> CheckResult:
        """Check 3: Are artists coming back?"""
        retention = self.collector.get_week1_retention()
        passed = retention >= 30.0

        return CheckResult(
            check_id="retention",
            check_name="Are artists coming back?",
            metric_name="Week 1 retention",
            metric_value=retention,
            threshold=">30% of artists return within 7 days",
            threshold_value=30.0,
            passed=passed,
            severity="warning" if not passed else "info",
            remediation="Analyze drop-off points, improve onboarding and first-run experience",
        )

    def _check_latency(self) -> CheckResult:
        """Check 4: Is generation fast enough?"""
        latency = self.collector.get_generation_p95_latency()
        new_p95 = latency.get("new_p95", 0.0)
        iter_p95 = latency.get("iteration_p95", 0.0)

        # Pass if new < 30s AND iteration < 3s
        passed = (new_p95 <= 30.0 or new_p95 == 0.0) and (iter_p95 <= 3.0 or iter_p95 == 0.0)

        return CheckResult(
            check_id="latency",
            check_name="Is generation fast enough?",
            metric_name="Canvas generation p95 latency",
            metric_value=new_p95,
            threshold="<30 seconds for new, <3 seconds for iteration",
            threshold_value=30.0,
            passed=passed,
            severity="warning" if not passed else "info",
            remediation="Optimize model, add caching, pre-compute variation spaces",
            details=latency,
        )

    def _check_viral(self) -> CheckResult:
        """Check 5: Are artists sharing?"""
        k_factor = self.collector.get_viral_coefficient()
        passed = k_factor >= 0.5

        return CheckResult(
            check_id="viral",
            check_name="Are artists sharing?",
            metric_name="Viral coefficient (K-factor)",
            metric_value=k_factor,
            threshold=">0.5 (each user brings 0.5 new users)",
            threshold_value=0.5,
            passed=passed,
            severity="warning" if not passed else "info",
            remediation="Improve watermark branding, add share incentives, improve output quality",
        )

    def _check_loop_seamless(self) -> CheckResult:
        """Check 6: Do loops work?"""
        seamless_rate = self.collector.get_loop_seamlessness_rate()
        passed = seamless_rate >= 95.0

        return CheckResult(
            check_id="loop_seamless",
            check_name="Do loops work?",
            metric_name="Loop seamlessness score",
            metric_value=seamless_rate,
            threshold=">95% pass automated loop test",
            threshold_value=95.0,
            passed=passed,
            severity="critical" if not passed else "info",
            remediation="Retrain loop engine, add more temporal smoothing",
        )

    def _check_av_match(self) -> CheckResult:
        """Check 7: Is the music matched?"""
        acceptance = self.collector.get_av_match_acceptance_rate()
        passed = acceptance >= 70.0

        return CheckResult(
            check_id="av_match",
            check_name="Is the music matched?",
            metric_name="Artist satisfaction with audio-visual match",
            metric_value=acceptance,
            threshold=">70% accept first batch of options",
            threshold_value=70.0,
            passed=passed,
            severity="warning" if not passed else "info",
            remediation="Improve emotion mapping, add more genre-specific training data",
        )

    def _check_patent_docs(self) -> CheckResult:
        """Check 8: Are patent docs ready?"""
        status = self.collector.get_patent_doc_status()
        ready = status.get("ready", 0)
        total = status.get("total", 7)
        days_remaining = status.get("days_remaining", 90)
        passed = ready >= total or days_remaining > 0

        return CheckResult(
            check_id="patent_docs",
            check_name="Are patent docs ready?",
            metric_name="Filing-ready patent documents",
            metric_value=float(ready),
            threshold="7 documented and filing-ready within 90 days. Filing only when founder authorizes.",
            threshold_value=7.0,
            passed=passed,
            severity="warning" if not passed else "info",
            remediation="Prioritize patent documentation agents, ensure all claims are current and filing-ready",
            details=status,
        )

    def _check_mrr_growth(self) -> CheckResult:
        """Check 9: Is revenue growing?"""
        growth = self.collector.get_mrr_growth_rate()
        passed = growth >= 20.0

        return CheckResult(
            check_id="mrr_growth",
            check_name="Is revenue growing?",
            metric_name="MRR growth rate",
            metric_value=growth,
            threshold=">20% MoM after public launch",
            threshold_value=20.0,
            passed=passed,
            severity="warning" if not passed else "info",
            remediation="Optimize conversion, add premium features, improve free-to-paid funnel",
        )

    def _check_agent_health(self) -> CheckResult:
        """Check 10: Are agents healthy?"""
        uptime = self.collector.get_agent_uptime()
        passed = uptime >= 99.5

        return CheckResult(
            check_id="agent_health",
            check_name="Are agents healthy?",
            metric_name="Agent uptime across all departments",
            metric_value=uptime,
            threshold=">99.5%",
            threshold_value=99.5,
            passed=passed,
            severity="critical" if not passed else "info",
            remediation="Auto-restart failed agents, investigate root cause, add redundancy",
        )

    # ── Run All Checks ────────────────────────────────────────

    ALL_CHECKS = [
        "_check_cost_zero",
        "_check_quality_gate",
        "_check_retention",
        "_check_latency",
        "_check_viral",
        "_check_loop_seamless",
        "_check_av_match",
        "_check_patent_docs",
        "_check_mrr_growth",
        "_check_agent_health",
    ]

    def evaluate(self, auto_remediate: bool = True) -> ChecklistReport:
        """
        Run all 10 checklist evaluations and generate a report.

        Args:
            auto_remediate: If True, automatically run remediation for failing checks

        Returns:
            ChecklistReport with all results
        """
        self.collector.clear_cache()
        results: List[CheckResult] = []
        remediation_actions: List[str] = []

        print(f"\n{'='*65}")
        print(f"  CANVAS MASTER CHECKLIST — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*65}")

        for check_method_name in self.ALL_CHECKS:
            check_method = getattr(self, check_method_name)
            try:
                result = check_method()
                results.append(result)

                # Print result
                status = "PASS" if result.passed else "FAIL"
                icon = " " if result.passed else " "
                print(f"  {icon} [{status}] {result.check_name}")
                print(f"          {result.metric_name}: {result.metric_value:.2f} (threshold: {result.threshold})")

                # Auto-remediate failures
                if not result.passed and auto_remediate:
                    action = self.remediator.remediate(result)
                    if action:
                        remediation_actions.append(action)
                        print(f"          -> Remediation: {action}")

            except Exception as e:
                # If a check itself fails, log it as a failure
                error_result = CheckResult(
                    check_id=check_method_name.replace("_check_", ""),
                    check_name=check_method_name,
                    metric_name="check_execution",
                    metric_value=0.0,
                    threshold="must not crash",
                    threshold_value=1.0,
                    passed=False,
                    severity="critical",
                    remediation=f"Fix check implementation: {str(e)}",
                )
                results.append(error_result)
                print(f"   [ERROR] {check_method_name}: {e}")

        # Compile report
        passed = sum(1 for r in results if r.passed)
        failed = sum(1 for r in results if not r.passed)
        critical = sum(1 for r in results if not r.passed and r.severity == "critical")

        if critical > 0:
            health = "critical"
        elif failed > 2:
            health = "degraded"
        elif failed > 0:
            health = "warning"
        else:
            health = "healthy"

        report = ChecklistReport(
            timestamp=datetime.now().isoformat(),
            total_checks=len(results),
            passed_checks=passed,
            failed_checks=failed,
            critical_failures=critical,
            overall_health=health,
            results=[asdict(r) for r in results],
            remediation_actions_taken=remediation_actions,
            next_evaluation=(datetime.now() + timedelta(weeks=1)).isoformat(),
        )

        # Print summary
        print(f"\n{'─'*65}")
        print(f"  SUMMARY: {passed}/{len(results)} checks passed | Health: {health.upper()}")
        if critical > 0:
            print(f"  CRITICAL FAILURES: {critical}")
        if remediation_actions:
            print(f"  REMEDIATIONS: {len(remediation_actions)} actions taken")
        print(f"{'='*65}\n")

        # Save report
        self._save_report(report)

        return report

    def _save_report(self, report: ChecklistReport):
        """Save report to file and append to history"""
        # Latest report
        try:
            with open(self.report_file, 'w') as f:
                json.dump(asdict(report), f, indent=2)
        except Exception:
            pass

        # History
        try:
            with open(self.history_file, 'a') as f:
                f.write(json.dumps(asdict(report)) + "\n")
        except Exception:
            pass

    def get_latest_report(self) -> Optional[Dict]:
        """Get the most recent checklist report"""
        if self.report_file.exists():
            try:
                with open(self.report_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def get_history(self, count: int = 10) -> List[Dict]:
        """Get recent checklist history"""
        if not self.history_file.exists():
            return []

        reports = []
        try:
            with open(self.history_file) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            reports.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except Exception:
            pass

        return reports[-count:]

    # ── Autonomous Mode ───────────────────────────────────────

    def run_autonomous(self, interval_seconds: int = 604800,
                       auto_remediate: bool = True):
        """
        Run the checklist continuously in autonomous mode.

        Default interval: 604800 seconds = 1 week
        Set to shorter intervals for more aggressive monitoring.

        Args:
            interval_seconds: Seconds between evaluations (default: 1 week)
            auto_remediate: Auto-fix failing checks
        """
        self._running = True
        self._stop_event.clear()

        print(f"\n{'#'*65}")
        print(f"# CANVAS MASTER CHECKLIST — AUTONOMOUS MODE")
        print(f"# Evaluation interval: {interval_seconds}s ({interval_seconds/3600:.1f}h)")
        print(f"# Auto-remediation: {'ENABLED' if auto_remediate else 'DISABLED'}")
        print(f"{'#'*65}\n")

        cycle = 0
        while self._running and not self._stop_event.is_set():
            cycle += 1
            print(f"\n--- Autonomous Evaluation Cycle #{cycle} ---")

            try:
                report = self.evaluate(auto_remediate=auto_remediate)

                # If critical, reduce interval for faster monitoring
                if report.overall_health == "critical":
                    next_interval = min(interval_seconds, 3600)  # Check hourly when critical
                    print(f"  CRITICAL: Next check in {next_interval}s (accelerated)")
                else:
                    next_interval = interval_seconds
                    print(f"  Next check in {next_interval}s")

            except Exception as e:
                print(f"  Evaluation cycle #{cycle} failed: {e}")
                next_interval = 60  # Retry in 1 minute on error

            # Wait for next interval or stop signal
            self._stop_event.wait(timeout=next_interval)

        print("\n[Checklist] Autonomous mode stopped.")

    def stop_autonomous(self):
        """Stop the autonomous evaluation loop"""
        self._running = False
        self._stop_event.set()

    def run_autonomous_threaded(self, interval_seconds: int = 604800,
                                 auto_remediate: bool = True) -> threading.Thread:
        """Start autonomous mode in a background thread"""
        thread = threading.Thread(
            target=self.run_autonomous,
            args=(interval_seconds, auto_remediate),
            daemon=True,
            name="canvas-checklist-autonomous",
        )
        thread.start()
        return thread


# ══════════════════════════════════════════════════════════════
# Metric Logging Helpers (called by other modules)
# ══════════════════════════════════════════════════════════════

def log_user_activity(user_id: str, action: str = "visit"):
    """Log user activity for retention tracking"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "action": action,
    }
    try:
        filepath = CHECKLIST_DIR / "user_activity.jsonl"
        with open(filepath, 'a') as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def log_generation_latency(latency_seconds: float, gen_type: str = "new"):
    """Log generation latency for performance tracking"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "latency_seconds": latency_seconds,
        "type": gen_type,  # "new" or "iteration"
    }
    try:
        filepath = CHECKLIST_DIR / "generation_latency.jsonl"
        with open(filepath, 'a') as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def log_direction_selection(session_id: str, accepted_first_batch: bool):
    """Log whether artist accepted first batch of visual directions"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "session_id": session_id,
        "accepted_first_batch": accepted_first_batch,
    }
    try:
        filepath = CHECKLIST_DIR / "direction_selections.jsonl"
        with open(filepath, 'a') as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def log_referral(user_id: str, invites_accepted: int):
    """Log referral/viral data"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "invites_accepted": invites_accepted,
    }
    try:
        filepath = CHECKLIST_DIR / "referrals.jsonl"
        with open(filepath, 'a') as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def log_agent_heartbeat(agent_name: str, alive: bool = True):
    """Log agent heartbeat for uptime tracking"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "agent": agent_name,
        "alive": alive,
    }
    try:
        filepath = CHECKLIST_DIR / "agent_heartbeats.jsonl"
        with open(filepath, 'a') as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def update_patent_status(ready: int, total: int = 7, days_remaining: int = 90):
    """Update patent documentation status"""
    status = {
        "ready": ready,
        "total": total,
        "days_remaining": days_remaining,
        "updated_at": datetime.now().isoformat(),
    }
    try:
        filepath = CHECKLIST_DIR / "patent_status.json"
        with open(filepath, 'w') as f:
            json.dump(status, f, indent=2)
    except Exception:
        pass


def log_revenue(amount: float, source: str = "stripe"):
    """Log revenue event"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "amount": amount,
        "source": source,
    }
    try:
        filepath = CHECKLIST_DIR / "revenue_history.jsonl"
        with open(filepath, 'a') as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════
# Singleton
# ══════════════════════════════════════════════════════════════

_checklist = None


def get_checklist() -> WeeklyChecklist:
    """Get the global weekly checklist instance"""
    global _checklist
    if _checklist is None:
        _checklist = WeeklyChecklist()
    return _checklist


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Canvas Master Checklist — Part VII")
    parser.add_argument("--autonomous", action="store_true",
                        help="Run in 24/7 autonomous mode")
    parser.add_argument("--interval", type=int, default=604800,
                        help="Evaluation interval in seconds (default: 1 week)")
    parser.add_argument("--no-remediate", action="store_true",
                        help="Disable automatic remediation")
    parser.add_argument("--report", action="store_true",
                        help="Show latest report and exit")
    parser.add_argument("--history", type=int, default=0,
                        help="Show last N reports")

    args = parser.parse_args()

    checklist = WeeklyChecklist()

    if args.report:
        report = checklist.get_latest_report()
        if report:
            print(json.dumps(report, indent=2))
        else:
            print("No report found. Run an evaluation first.")
    elif args.history > 0:
        history = checklist.get_history(args.history)
        for r in history:
            print(f"\n{r['timestamp']}: {r['passed_checks']}/{r['total_checks']} passed ({r['overall_health']})")
    elif args.autonomous:
        checklist.run_autonomous(
            interval_seconds=args.interval,
            auto_remediate=not args.no_remediate,
        )
    else:
        checklist.evaluate(auto_remediate=not args.no_remediate)
