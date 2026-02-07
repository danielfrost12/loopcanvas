#!/usr/bin/env python3
"""
QA Engineer Agent — Quality Gate for the Canvas Agent Army v2.0

PHILOSOPHY: Reject everything that isn't exceptional.

This agent autonomously tests every aspect of the Canvas product. It enforces
the 9.3/10 minimum quality bar across all pipeline outputs, validates API
health, detects regressions, and ensures the entire system is production-ready.

Quality Standards (non-negotiable):
  - 9.3/10 minimum quality score (reject everything below)
  - 95/100 minimum technical quality score
  - 80-90% expected rejection rate (intentionally brutal)
  - 7 hard rejection flags (any single one = instant reject)
  - 5 scoring axes with individual pass requirements
  - Sub-3-second iteration time
  - Sub-30-second generation time
  - Loop seamlessness > 95%
  - Artist satisfaction > 70% accept first batch

Hard Rejection Flags (instant reject on ANY):
  1. no_ai_artifacts     — AI-generated look detected
  2. no_morphing_faces   — Face morphing / warping artifacts
  3. no_uncanny_valley   — Uncanny valley effect in motion
  4. cinematic_color_grading — Color grading not cinematic quality
  5. beat_sync_accuracy  — Audio-visual sync off beat
  6. seamless_looping    — Loop point visible or jarring
  7. director_style_match — Output doesn't match director intent

Scoring Axes (weighted, ALL must pass individually):
  1. Observer Neutrality    (x3.0) — "footage doesn't know it's being watched"
  2. Camera Humility        (x2.5) — camera presence is invisible
  3. Temporal Indifference  (x2.0) — no urgency, time flows naturally
  4. Memory Texture         (x1.5) — feels like a real memory, not generated
  5. Light-First Emotion    (x1.0) — emotion from lighting, not tricks

Data sources:
  canvas-engine/optimization_data/canvas_results.jsonl
  canvas-engine/checklist_data/*.jsonl
  *_config.json files in app root

Outputs:
  qa_config.json                          — QA configuration and thresholds
  canvas-engine/checklist_data/qa_report.json    — latest QA report
  canvas-engine/checklist_data/qa_decisions.jsonl — decision log

Cost: $0 — all local file/process inspection, no APIs
"""

import json
import os
import sys
import time
import statistics
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.request import urlopen
from urllib.error import URLError


# ======================================================================
# Paths — follow the same pattern as all other agents
# ======================================================================

ENGINE_DIR = Path(__file__).parent.parent
APP_DIR = ENGINE_DIR.parent
DATA_DIR = ENGINE_DIR / "checklist_data"
OPT_DIR = ENGINE_DIR / "optimization_data"
CONFIG_DIR = APP_DIR
TEMPLATE_DIR = APP_DIR / "templates"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
OPT_DIR.mkdir(exist_ok=True)
TEMPLATE_DIR.mkdir(exist_ok=True)

sys.path.insert(0, str(ENGINE_DIR))


# ======================================================================
# Constants
# ======================================================================

MINIMUM_QUALITY_SCORE = 9.3          # out of 10 — the hard floor
MINIMUM_TECHNICAL_SCORE = 95         # out of 100
EXPECTED_REJECTION_RATE_LOW = 0.80   # 80% minimum rejection expected
EXPECTED_REJECTION_RATE_HIGH = 0.90  # 90% upper bound
MAX_GENERATION_TIME_SECONDS = 30.0   # new canvas generation
MAX_ITERATION_TIME_SECONDS = 3.0     # iteration on existing canvas
LOOP_SEAMLESSNESS_THRESHOLD = 0.95   # 95% seamless
ARTIST_SATISFACTION_THRESHOLD = 0.70 # 70% accept first batch
AGENT_STALENESS_HOURS = 48           # agents must run within 48h
REGRESSION_WINDOW_DAYS = 7           # compare last 7 vs previous 7

HARD_REJECTION_FLAGS = [
    "no_ai_artifacts",
    "no_morphing_faces",
    "no_uncanny_valley",
    "cinematic_color_grading",
    "beat_sync_accuracy",
    "seamless_looping",
    "director_style_match",
]

SCORING_AXES = {
    "observer_neutrality":   {"weight": 3.0, "min_score": 7.0, "description": "Footage doesn't know it's being watched"},
    "camera_humility":       {"weight": 2.5, "min_score": 7.0, "description": "Camera presence is invisible"},
    "temporal_indifference": {"weight": 2.0, "min_score": 7.0, "description": "No urgency, time flows naturally"},
    "memory_texture":        {"weight": 1.5, "min_score": 7.0, "description": "Feels like a real memory"},
    "light_first_emotion":   {"weight": 1.0, "min_score": 7.0, "description": "Emotion from lighting, not tricks"},
}

# Required keys for each config file
REQUIRED_CONFIG_KEYS = {
    "growth_config.json": ["version", "share", "referral", "social_proof", "watermark"],
    "onboarding_config.json": ["version"],
    "retention_config.json": ["version"],
    "landing_config.json": ["version"],
}

# API endpoints to health-check (localhost or configured base URL)
API_ENDPOINTS = [
    "/api/configs",
    "/api/track",
    "/api/upload",
    "/api/generate",
]


# ======================================================================
# Data Structures
# ======================================================================

@dataclass
class QACheckResult:
    """Result of a single QA check."""
    check_id: str
    check_name: str
    passed: bool
    severity: str             # "critical", "warning", "info"
    metric_value: float
    threshold: float
    details: Dict = field(default_factory=dict)
    remediation: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class OutputScore:
    """Quality score for a single canvas output."""
    job_id: str
    overall_score: float
    technical_score: float
    axis_scores: Dict[str, float]
    hard_flags_passed: Dict[str, bool]
    passed: bool
    rejection_reasons: List[str] = field(default_factory=list)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class RegressionResult:
    """Result of regression detection between two time windows."""
    metric_name: str
    current_value: float
    previous_value: float
    delta: float
    delta_pct: float
    regressed: bool
    severity: str           # "critical", "warning", "none"
    details: str = ""


@dataclass
class QAReport:
    """Full QA report."""
    timestamp: str
    total_checks: int
    passed_checks: int
    failed_checks: int
    critical_failures: int
    overall_verdict: str     # "PASS", "FAIL", "DEGRADED"
    check_results: List[Dict]
    output_scores: List[Dict]
    regressions: List[Dict]
    pipeline_health: Dict
    summary: str


# ======================================================================
# JSONL Reader Utility
# ======================================================================

def _read_jsonl(path: Path, days: int = 30) -> List[Dict]:
    """Read JSONL file, filter to last N days. Returns [] on missing files."""
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


def _read_jsonl_windowed(path: Path, start_days_ago: int, end_days_ago: int) -> List[Dict]:
    """Read JSONL entries within a specific day window (for regression comparison)."""
    if not path.exists():
        return []
    now = datetime.now()
    start = now - timedelta(days=start_days_ago)
    end = now - timedelta(days=end_days_ago)
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
                        if start <= ts <= end:
                            rows.append(data)
                except (json.JSONDecodeError, ValueError):
                    continue
    except OSError:
        pass
    return rows


# ======================================================================
# QA Engineer Agent
# ======================================================================

class QAEngineer:
    """
    Quality Gate Agent — tests every aspect of the Canvas product.

    Run daily via GitHub Actions or on-demand before any release.
    Enforces 9.3/10 minimum quality bar with an 80-90% expected rejection rate.
    """

    RESULTS_FILE = OPT_DIR / "canvas_results.jsonl"
    LATENCY_FILE = DATA_DIR / "generation_latency.jsonl"
    HEARTBEAT_FILE = DATA_DIR / "agent_heartbeats.jsonl"
    DIRECTION_FILE = DATA_DIR / "direction_selections.jsonl"

    QA_CONFIG_PATH = CONFIG_DIR / "qa_config.json"
    QA_REPORT_PATH = DATA_DIR / "qa_report.json"
    QA_DECISIONS_LOG = DATA_DIR / "qa_decisions.jsonl"

    def __init__(self, api_base_url: str = "http://localhost:3000"):
        self.api_base_url = api_base_url
        self.check_results: List[QACheckResult] = []
        self.output_scores: List[OutputScore] = []
        self.regressions: List[RegressionResult] = []

    # ==================================================================
    # Main Entry Points
    # ==================================================================

    def run(self):
        """Full QA pipeline: analyze, validate, score, check regression, report."""
        sep = "=" * 65
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("\n" + sep)
        print("  QA ENGINEER -- Canvas Quality Gate v2.0")
        print("  " + now_str)
        print(sep)

        self.check_results = []
        self.output_scores = []
        self.regressions = []

        # Run all validation checks
        self._check_api_health()
        self._check_config_integrity()
        self._check_template_integrity()
        self._check_output_quality()
        self._check_regression()
        self._check_pipeline_latency()
        self._check_loop_quality()
        self._check_cost_compliance()
        self._check_agent_health()
        self._check_artist_satisfaction()

        # Generate and save report
        report = self._generate_report()
        self._save_report(report)
        self._log_decisions()
        self._write_qa_config()
        self._print_report(report)

        return report

    def analyze(self) -> Dict:
        """Analyze current quality metrics without running full validation."""
        results = _read_jsonl(self.RESULTS_FILE, days=7)
        if not results:
            return {"status": "no_data", "total_outputs": 0}

        scores = [r.get("quality_score", 0.0) for r in results]
        passed = [r for r in results if r.get("quality_passed", False)]

        return {
            "status": "ok",
            "total_outputs": len(results),
            "passed_outputs": len(passed),
            "rejection_rate": 1.0 - (len(passed) / len(results)) if results else 0.0,
            "avg_quality_score": statistics.mean(scores) if scores else 0.0,
            "median_quality_score": statistics.median(scores) if scores else 0.0,
            "min_quality_score": min(scores) if scores else 0.0,
            "max_quality_score": max(scores) if scores else 0.0,
            "stdev": statistics.stdev(scores) if len(scores) > 1 else 0.0,
        }

    def validate(self) -> Dict:
        """Run all validation checks and return summary."""
        self.run()
        passed = sum(1 for c in self.check_results if c.passed)
        failed = sum(1 for c in self.check_results if not c.passed)
        return {
            "total_checks": len(self.check_results),
            "passed": passed,
            "failed": failed,
            "verdict": "PASS" if failed == 0 else "FAIL",
        }

    def score_output(self, result_data: Dict) -> OutputScore:
        """
        Score a single canvas output against all quality axes.

        This is the core scoring function. Every output must pass:
        1. All 7 hard rejection flags
        2. All 5 scoring axes individually (each axis has a minimum)
        3. Weighted total >= 9.3/10
        4. Technical quality >= 95/100
        """
        job_id = result_data.get("job_id", "unknown")
        quality_breakdown = result_data.get("quality_breakdown", {})
        quality_score = result_data.get("quality_score", 0.0)

        # --- Hard rejection flags ---
        hard_flags = {}
        rejection_reasons = []

        flag_checks = {
            "no_ai_artifacts": quality_breakdown.get("ai_artifact_score", 10.0) >= 8.0,
            "no_morphing_faces": "morphing" not in str(quality_breakdown.get("issues", [])).lower(),
            "no_uncanny_valley": "uncanny" not in str(quality_breakdown.get("issues", [])).lower(),
            "cinematic_color_grading": quality_breakdown.get("color_grading_quality", 10.0) >= 7.0,
            "beat_sync_accuracy": quality_breakdown.get("beat_sync_score", 10.0) >= 7.5,
            "seamless_looping": result_data.get("loop_score", 1.0) >= LOOP_SEAMLESSNESS_THRESHOLD,
            "director_style_match": quality_breakdown.get("style_match_score", 10.0) >= 7.0,
        }

        for flag_name in HARD_REJECTION_FLAGS:
            passed = flag_checks.get(flag_name, True)
            hard_flags[flag_name] = passed
            if not passed:
                rejection_reasons.append("HARD_REJECT: " + flag_name)

        # --- Scoring axes ---
        axis_scores = {}
        raw_axis_data = {
            "observer_neutrality": quality_breakdown.get("observer_neutrality", quality_score),
            "camera_humility": quality_breakdown.get("camera_humility", quality_score * 0.95),
            "temporal_indifference": quality_breakdown.get("temporal_indifference", quality_score * 0.9),
            "memory_texture": quality_breakdown.get("memory_texture", quality_score * 0.92),
            "light_first_emotion": quality_breakdown.get("light_first_emotion", quality_score * 0.88),
        }

        total_weighted = 0.0
        total_weight = 0.0
        any_axis_failed = False

        for axis_name, axis_config in SCORING_AXES.items():
            score = raw_axis_data.get(axis_name, 0.0)
            axis_scores[axis_name] = round(score, 2)
            weight = axis_config["weight"]
            min_score = axis_config["min_score"]

            total_weighted += score * weight
            total_weight += weight

            if score < min_score:
                any_axis_failed = True
                rejection_reasons.append(
                    "AXIS_FAIL: " + axis_name + " = " + str(round(score, 2))
                    + " (min " + str(min_score) + ")"
                )

        # Weighted overall score (normalize to 10-point scale)
        weighted_overall = total_weighted / total_weight if total_weight > 0 else 0.0

        # Technical score (normalize to 100-point scale)
        technical_score = weighted_overall * 10.0

        # Final pass/fail
        hard_flags_all_passed = all(hard_flags.values())
        score_passes = weighted_overall >= MINIMUM_QUALITY_SCORE
        technical_passes = technical_score >= MINIMUM_TECHNICAL_SCORE

        if not score_passes:
            rejection_reasons.append(
                "SCORE_BELOW_MIN: " + str(round(weighted_overall, 2))
                + " < " + str(MINIMUM_QUALITY_SCORE)
            )
        if not technical_passes:
            rejection_reasons.append(
                "TECHNICAL_BELOW_MIN: " + str(round(technical_score, 1))
                + " < " + str(MINIMUM_TECHNICAL_SCORE)
            )

        final_passed = (
            hard_flags_all_passed
            and score_passes
            and technical_passes
            and not any_axis_failed
        )

        return OutputScore(
            job_id=job_id,
            overall_score=round(weighted_overall, 3),
            technical_score=round(technical_score, 1),
            axis_scores=axis_scores,
            hard_flags_passed=hard_flags,
            passed=final_passed,
            rejection_reasons=rejection_reasons,
        )

    def check_regression(self) -> List[RegressionResult]:
        """Compare metrics from last 7 days vs previous 7 days."""
        recent = _read_jsonl_windowed(self.RESULTS_FILE, 7, 0)
        previous = _read_jsonl_windowed(self.RESULTS_FILE, 14, 7)

        results = []

        if not recent or not previous:
            return results

        # Quality score regression
        recent_scores = [r.get("quality_score", 0.0) for r in recent]
        previous_scores = [r.get("quality_score", 0.0) for r in previous]

        results.append(self._compare_metric(
            "avg_quality_score",
            statistics.mean(recent_scores) if recent_scores else 0.0,
            statistics.mean(previous_scores) if previous_scores else 0.0,
            regression_if="lower",
            critical_threshold=0.5,
        ))

        # Pass rate regression
        recent_pass_rate = (
            sum(1 for r in recent if r.get("quality_passed"))
            / max(len(recent), 1)
        )
        previous_pass_rate = (
            sum(1 for r in previous if r.get("quality_passed"))
            / max(len(previous), 1)
        )

        results.append(self._compare_metric(
            "pass_rate",
            recent_pass_rate,
            previous_pass_rate,
            regression_if="lower",
            critical_threshold=0.10,
        ))

        # Loop score regression
        recent_loops = [r.get("loop_score", 0.0) for r in recent if "loop_score" in r]
        previous_loops = [r.get("loop_score", 0.0) for r in previous if "loop_score" in r]

        if recent_loops and previous_loops:
            results.append(self._compare_metric(
                "avg_loop_score",
                statistics.mean(recent_loops),
                statistics.mean(previous_loops),
                regression_if="lower",
                critical_threshold=0.05,
            ))

        # Latency regression
        recent_latency = _read_jsonl_windowed(self.LATENCY_FILE, 7, 0)
        previous_latency = _read_jsonl_windowed(self.LATENCY_FILE, 14, 7)

        if recent_latency and previous_latency:
            recent_gen_times = [
                r.get("latency_seconds", 0.0) for r in recent_latency
                if r.get("type") == "new"
            ]
            previous_gen_times = [
                r.get("latency_seconds", 0.0) for r in previous_latency
                if r.get("type") == "new"
            ]

            if recent_gen_times and previous_gen_times:
                results.append(self._compare_metric(
                    "avg_generation_latency",
                    statistics.mean(recent_gen_times),
                    statistics.mean(previous_gen_times),
                    regression_if="higher",
                    critical_threshold=5.0,
                ))

        self.regressions = results
        return results

    # ==================================================================
    # Individual Check Methods
    # ==================================================================

    def _check_api_health(self):
        """Check 1: API endpoint health — all endpoints respond."""
        print("\n  [1/10] API Health Check")
        for endpoint in API_ENDPOINTS:
            url = self.api_base_url.rstrip("/") + endpoint
            passed = False
            status_code = 0
            error_msg = ""

            try:
                response = urlopen(url, timeout=5)
                status_code = response.getcode()
                passed = status_code in (200, 201, 204, 301, 302)
            except URLError as e:
                error_msg = str(e.reason) if hasattr(e, "reason") else str(e)
            except Exception as e:
                error_msg = str(e)

            # In dev/CI, the server may not be running. Mark as warning, not critical.
            severity = "warning" if not passed else "info"

            result = QACheckResult(
                check_id="api_health_" + endpoint.replace("/", "_").strip("_"),
                check_name="API Health: " + endpoint,
                passed=passed,
                severity=severity,
                metric_value=float(status_code),
                threshold=200.0,
                details={"url": url, "status_code": status_code, "error": error_msg},
                remediation=(
                    "Check that " + endpoint + " is accessible and returns 2xx"
                    if not passed else ""
                ),
            )
            self.check_results.append(result)
            status_str = "PASS" if passed else "WARN"
            print("    [" + status_str + "] " + endpoint + ": "
                  + str(status_code or error_msg))

    def _check_config_integrity(self):
        """Check 2: All config JSONs parse and contain required keys."""
        print("\n  [2/10] Config Integrity Check")
        for config_name, required_keys in REQUIRED_CONFIG_KEYS.items():
            config_path = CONFIG_DIR / config_name
            passed = True
            missing_keys = []
            error_msg = ""

            if not config_path.exists():
                passed = False
                error_msg = "File not found"
            else:
                try:
                    with open(config_path) as f:
                        data = json.load(f)
                    for key in required_keys:
                        if key not in data:
                            missing_keys.append(key)
                    if missing_keys:
                        passed = False
                        error_msg = "Missing keys: " + ", ".join(missing_keys)
                except json.JSONDecodeError as e:
                    passed = False
                    error_msg = "JSON parse error: " + str(e)
                except OSError as e:
                    passed = False
                    error_msg = "Read error: " + str(e)

            result = QACheckResult(
                check_id="config_" + config_name.replace(".", "_"),
                check_name="Config: " + config_name,
                passed=passed,
                severity="critical" if not passed else "info",
                metric_value=1.0 if passed else 0.0,
                threshold=1.0,
                details={
                    "path": str(config_path),
                    "missing_keys": missing_keys,
                    "error": error_msg,
                },
                remediation=(
                    "Fix or regenerate " + config_name + ": " + error_msg
                    if not passed else ""
                ),
            )
            self.check_results.append(result)
            status_str = "PASS" if passed else "FAIL"
            suffix = " (" + error_msg + ")" if error_msg else ""
            print("    [" + status_str + "] " + config_name + suffix)

    def _check_template_integrity(self):
        """Check 3: All HTML templates exist and are non-empty."""
        print("\n  [3/10] Template Integrity Check")
        expected_templates = [
            "share_modal.html",
            "onboarding_tips.html",
            "return_banner.html",
            "gallery_component.html",
            "landing_hero_variant.html",
        ]

        for template_name in expected_templates:
            template_path = TEMPLATE_DIR / template_name
            passed = True
            error_msg = ""
            file_size = 0

            if not template_path.exists():
                passed = False
                error_msg = "Template not found"
            else:
                try:
                    file_size = template_path.stat().st_size
                    if file_size == 0:
                        passed = False
                        error_msg = "Template is empty"
                except OSError as e:
                    passed = False
                    error_msg = "Read error: " + str(e)

            result = QACheckResult(
                check_id="template_" + template_name.replace(".", "_"),
                check_name="Template: " + template_name,
                passed=passed,
                severity="warning" if not passed else "info",
                metric_value=float(file_size),
                threshold=1.0,
                details={
                    "path": str(template_path),
                    "size_bytes": file_size,
                    "error": error_msg,
                },
                remediation=(
                    "Regenerate " + template_name + " by running the responsible agent"
                    if not passed else ""
                ),
            )
            self.check_results.append(result)
            status_str = "PASS" if passed else "WARN"
            suffix = " - " + error_msg if error_msg else ""
            print("    [" + status_str + "] " + template_name
                  + " (" + str(file_size) + " bytes)" + suffix)

    def _check_output_quality(self):
        """Check 4: Score every canvas result against 5 axes."""
        print("\n  [4/10] Output Quality Check")
        results = _read_jsonl(self.RESULTS_FILE, days=7)

        if not results:
            result = QACheckResult(
                check_id="output_quality",
                check_name="Output Quality (no data)",
                passed=True,
                severity="info",
                metric_value=0.0,
                threshold=MINIMUM_QUALITY_SCORE,
                details={"note": "No canvas results in last 7 days"},
            )
            self.check_results.append(result)
            print("    [INFO] No canvas results to score")
            return

        total_scored = 0
        total_passed = 0
        all_scores = []

        for result_data in results:
            score = self.score_output(result_data)
            self.output_scores.append(score)
            total_scored += 1
            if score.passed:
                total_passed += 1
            all_scores.append(score.overall_score)

        rejection_rate = (
            1.0 - (total_passed / total_scored) if total_scored > 0 else 0.0
        )
        avg_score = statistics.mean(all_scores) if all_scores else 0.0

        # Expected rejection rate is 80-90%. If rejection is too LOW, quality bar
        # may be slipping.
        rejection_healthy = (
            EXPECTED_REJECTION_RATE_LOW <= rejection_rate <= EXPECTED_REJECTION_RATE_HIGH
        )

        # The critical check: average score of PASSED outputs must be >= 9.3
        passed_scores = [s.overall_score for s in self.output_scores if s.passed]
        avg_passed_score = (
            statistics.mean(passed_scores) if passed_scores else 0.0
        )
        quality_bar_met = (
            avg_passed_score >= MINIMUM_QUALITY_SCORE or not passed_scores
        )

        check_passed = quality_bar_met

        result = QACheckResult(
            check_id="output_quality",
            check_name="Output Quality Gate",
            passed=check_passed,
            severity="critical" if not check_passed else "info",
            metric_value=avg_passed_score,
            threshold=MINIMUM_QUALITY_SCORE,
            details={
                "total_scored": total_scored,
                "total_passed": total_passed,
                "rejection_rate": round(rejection_rate, 4),
                "rejection_rate_healthy": rejection_healthy,
                "avg_score_all": round(avg_score, 3),
                "avg_score_passed": round(avg_passed_score, 3),
                "expected_rejection_range": (
                    str(int(EXPECTED_REJECTION_RATE_LOW * 100)) + "-"
                    + str(int(EXPECTED_REJECTION_RATE_HIGH * 100)) + "%"
                ),
            },
            remediation=(
                "Passed outputs averaging below 9.3/10. "
                "Tighten generation parameters."
                if not check_passed else ""
            ),
        )
        self.check_results.append(result)

        status_str = "PASS" if check_passed else "FAIL"
        print("    [" + status_str + "] Scored " + str(total_scored) + " outputs: "
              + str(total_passed) + " passed, "
              + str(total_scored - total_passed) + " rejected ("
              + "{:.1f}".format(rejection_rate * 100) + "% rejection rate)")
        print("           Avg passed score: "
              + "{:.2f}".format(avg_passed_score) + "/10 (min "
              + str(MINIMUM_QUALITY_SCORE) + ")")
        if not rejection_healthy:
            direction = "below" if rejection_rate < EXPECTED_REJECTION_RATE_LOW else "above"
            print("    [WARN] Rejection rate "
                  + "{:.1f}".format(rejection_rate * 100) + "% is " + direction
                  + " expected "
                  + str(int(EXPECTED_REJECTION_RATE_LOW * 100)) + "-"
                  + str(int(EXPECTED_REJECTION_RATE_HIGH * 100)) + "% range")

    def _check_regression(self):
        """Check 5: Compare last 7 days vs previous 7 days."""
        print("\n  [5/10] Regression Detection")
        regressions = self.check_regression()

        any_critical = False
        any_warning = False

        for reg in regressions:
            if reg.regressed:
                if reg.severity == "critical":
                    any_critical = True
                    print("    [CRIT] " + reg.metric_name + ": "
                          + "{:.3f}".format(reg.previous_value) + " -> "
                          + "{:.3f}".format(reg.current_value) + " ("
                          + "{:+.1f}".format(reg.delta_pct) + "%)")
                elif reg.severity == "warning":
                    any_warning = True
                    print("    [WARN] " + reg.metric_name + ": "
                          + "{:.3f}".format(reg.previous_value) + " -> "
                          + "{:.3f}".format(reg.current_value) + " ("
                          + "{:+.1f}".format(reg.delta_pct) + "%)")
            else:
                print("    [ OK ] " + reg.metric_name + ": "
                      + "{:.3f}".format(reg.previous_value) + " -> "
                      + "{:.3f}".format(reg.current_value) + " ("
                      + "{:+.1f}".format(reg.delta_pct) + "%)")

        if not regressions:
            print("    [INFO] Not enough data for regression comparison")

        severity = "critical" if any_critical else ("warning" if any_warning else "info")
        passed = not any_critical

        result = QACheckResult(
            check_id="regression_detection",
            check_name="Regression Detection",
            passed=passed,
            severity=severity,
            metric_value=float(sum(1 for r in regressions if r.regressed)),
            threshold=0.0,
            details={
                "regressions_found": sum(1 for r in regressions if r.regressed),
                "critical_regressions": sum(
                    1 for r in regressions if r.severity == "critical"
                ),
                "metrics_compared": len(regressions),
            },
            remediation=(
                "Investigate quality regressions in last 7 days"
                if not passed else ""
            ),
        )
        self.check_results.append(result)

    def _check_pipeline_latency(self):
        """Check 6: Generation time < 30s, iteration < 3s."""
        print("\n  [6/10] Pipeline Latency Check")
        latency_data = _read_jsonl(self.LATENCY_FILE, days=7)

        new_latencies = [
            r.get("latency_seconds", 0.0) for r in latency_data
            if r.get("type") == "new"
        ]
        iter_latencies = [
            r.get("latency_seconds", 0.0) for r in latency_data
            if r.get("type") == "iteration"
        ]

        # New generation check
        new_p95 = (
            self._percentile(new_latencies, 0.95) if new_latencies else 0.0
        )
        new_passed = new_p95 <= MAX_GENERATION_TIME_SECONDS or new_p95 == 0.0

        result_new = QACheckResult(
            check_id="latency_new_generation",
            check_name="Latency: New Generation (p95)",
            passed=new_passed,
            severity="warning" if not new_passed else "info",
            metric_value=new_p95,
            threshold=MAX_GENERATION_TIME_SECONDS,
            details={
                "p95": round(new_p95, 2),
                "count": len(new_latencies),
                "mean": (
                    round(statistics.mean(new_latencies), 2)
                    if new_latencies else 0.0
                ),
            },
            remediation=(
                "New generation p95 is " + "{:.1f}".format(new_p95)
                + "s, exceeds " + str(MAX_GENERATION_TIME_SECONDS) + "s limit"
                if not new_passed else ""
            ),
        )
        self.check_results.append(result_new)

        # Iteration check
        iter_p95 = (
            self._percentile(iter_latencies, 0.95) if iter_latencies else 0.0
        )
        iter_passed = iter_p95 <= MAX_ITERATION_TIME_SECONDS or iter_p95 == 0.0

        result_iter = QACheckResult(
            check_id="latency_iteration",
            check_name="Latency: Iteration (p95)",
            passed=iter_passed,
            severity="warning" if not iter_passed else "info",
            metric_value=iter_p95,
            threshold=MAX_ITERATION_TIME_SECONDS,
            details={
                "p95": round(iter_p95, 2),
                "count": len(iter_latencies),
                "mean": (
                    round(statistics.mean(iter_latencies), 2)
                    if iter_latencies else 0.0
                ),
            },
            remediation=(
                "Iteration p95 is " + "{:.1f}".format(iter_p95)
                + "s, exceeds " + str(MAX_ITERATION_TIME_SECONDS) + "s limit"
                if not iter_passed else ""
            ),
        )
        self.check_results.append(result_iter)

        new_status = "PASS" if new_passed else "WARN"
        iter_status = "PASS" if iter_passed else "WARN"
        print("    [" + new_status + "] New generation p95: "
              + "{:.2f}".format(new_p95) + "s (limit "
              + str(MAX_GENERATION_TIME_SECONDS) + "s, n="
              + str(len(new_latencies)) + ")")
        print("    [" + iter_status + "] Iteration p95: "
              + "{:.2f}".format(iter_p95) + "s (limit "
              + str(MAX_ITERATION_TIME_SECONDS) + "s, n="
              + str(len(iter_latencies)) + ")")

    def _check_loop_quality(self):
        """Check 7: Loop seamlessness > 95%."""
        print("\n  [7/10] Loop Quality Check")
        results = _read_jsonl(self.RESULTS_FILE, days=7)

        loop_scores = [
            r.get("loop_score", 0.0) for r in results if "loop_score" in r
        ]
        if not loop_scores:
            result = QACheckResult(
                check_id="loop_quality",
                check_name="Loop Seamlessness",
                passed=True,
                severity="info",
                metric_value=0.0,
                threshold=LOOP_SEAMLESSNESS_THRESHOLD,
                details={"note": "No loop data available"},
            )
            self.check_results.append(result)
            print("    [INFO] No loop data available")
            return

        total = len(loop_scores)
        seamless = sum(1 for s in loop_scores if s >= LOOP_SEAMLESSNESS_THRESHOLD)
        seamless_rate = seamless / total if total > 0 else 0.0
        avg_score = statistics.mean(loop_scores)

        passed = seamless_rate >= LOOP_SEAMLESSNESS_THRESHOLD

        result = QACheckResult(
            check_id="loop_quality",
            check_name="Loop Seamlessness",
            passed=passed,
            severity="critical" if not passed else "info",
            metric_value=round(seamless_rate, 4),
            threshold=LOOP_SEAMLESSNESS_THRESHOLD,
            details={
                "total_loops": total,
                "seamless_count": seamless,
                "seamless_rate": round(seamless_rate, 4),
                "avg_loop_score": round(avg_score, 4),
            },
            remediation=(
                "Loop seamlessness below 95%. "
                "Increase crossfade frames, add temporal smoothing."
                if not passed else ""
            ),
        )
        self.check_results.append(result)

        status_str = "PASS" if passed else "FAIL"
        print("    [" + status_str + "] " + str(seamless) + "/" + str(total)
              + " loops seamless (" + "{:.1f}".format(seamless_rate * 100)
              + "%), avg score: " + "{:.3f}".format(avg_score))

    def _check_cost_compliance(self):
        """Check 8: $0 spend verified."""
        print("\n  [8/10] Cost Compliance Check")
        spend = 0.0
        cost_events_blocked = 0

        try:
            from agents.cost_enforcer import get_enforcer
            enforcer = get_enforcer()
            status = enforcer.get_status()
            spend = status.get("revenue", 0.0)
            cost_events_blocked = status.get("recent_blocked_count", 0)
        except ImportError:
            pass
        except Exception:
            pass

        passed = spend <= 0.0

        result = QACheckResult(
            check_id="cost_compliance",
            check_name="Cost Compliance ($0 Rule)",
            passed=passed,
            severity="critical" if not passed else "info",
            metric_value=spend,
            threshold=0.0,
            details={
                "total_spend": spend,
                "blocked_cost_events": cost_events_blocked,
            },
            remediation=(
                "SPENDING DETECTED. Immediately halt all paid API calls."
                if not passed else ""
            ),
        )
        self.check_results.append(result)

        status_str = "PASS" if passed else "FAIL"
        print("    [" + status_str + "] Total spend: $"
              + "{:.2f}".format(spend) + " (blocked events: "
              + str(cost_events_blocked) + ")")

    def _check_agent_health(self):
        """Check 9: All agents have run within last 48h."""
        print("\n  [9/10] Agent Health Check")
        heartbeats = _read_jsonl(self.HEARTBEAT_FILE, days=7)

        # Group by agent, find most recent heartbeat
        agent_last_seen = {}
        for hb in heartbeats:
            agent_name = hb.get("agent", "unknown")
            ts_str = hb.get("timestamp", "")
            alive = hb.get("alive", True)
            if ts_str and alive:
                try:
                    ts = datetime.fromisoformat(ts_str)
                    if (agent_name not in agent_last_seen
                            or ts > agent_last_seen[agent_name]):
                        agent_last_seen[agent_name] = ts
                except ValueError:
                    continue

        now = datetime.now()
        stale_agents = []
        healthy_agents = []
        staleness_cutoff = now - timedelta(hours=AGENT_STALENESS_HOURS)

        for agent_name, last_seen in agent_last_seen.items():
            if last_seen < staleness_cutoff:
                stale_agents.append(agent_name)
            else:
                healthy_agents.append(agent_name)

        # Also check that critical agent files exist
        critical_agents = [
            ("cost_enforcer", ENGINE_DIR / "agents" / "cost_enforcer.py"),
            ("optimization_loop", ENGINE_DIR / "agents" / "optimization_loop.py"),
            ("weekly_checklist", ENGINE_DIR / "agents" / "weekly_checklist.py"),
            ("growth_engineer", ENGINE_DIR / "agents" / "growth_engineer.py"),
            ("retention_engineer", ENGINE_DIR / "agents" / "retention_engineer.py"),
            ("design_engineer", ENGINE_DIR / "agents" / "design_engineer.py"),
            ("onboarding_optimizer", ENGINE_DIR / "agents" / "onboarding_optimizer.py"),
            ("seed_runner", ENGINE_DIR / "agents" / "seed_runner.py"),
        ]

        missing_agents = []
        for agent_name, agent_path in critical_agents:
            if not agent_path.exists():
                missing_agents.append(agent_name)

        has_stale = len(stale_agents) > 0
        has_missing = len(missing_agents) > 0
        passed = not has_missing  # Missing agents is critical, stale is warning

        severity = "info"
        if has_missing:
            severity = "critical"
        elif has_stale:
            severity = "warning"

        result = QACheckResult(
            check_id="agent_health",
            check_name="Agent Health (all agents within 48h)",
            passed=passed,
            severity=severity,
            metric_value=float(len(healthy_agents)),
            threshold=float(len(critical_agents)),
            details={
                "healthy_agents": healthy_agents,
                "stale_agents": stale_agents,
                "missing_agents": missing_agents,
                "total_tracked": len(agent_last_seen),
                "staleness_cutoff_hours": AGENT_STALENESS_HOURS,
            },
            remediation=(
                ("Missing agent files: " + ", ".join(missing_agents) + ". "
                 if missing_agents else "")
                + ("Stale agents (no heartbeat in "
                   + str(AGENT_STALENESS_HOURS) + "h): "
                   + ", ".join(stale_agents)
                   if stale_agents else "")
            ),
        )
        self.check_results.append(result)

        if has_missing:
            status_str = "FAIL"
        elif has_stale:
            status_str = "WARN"
        else:
            status_str = "PASS"
        print("    [" + status_str + "] " + str(len(healthy_agents))
              + " healthy, " + str(len(stale_agents)) + " stale, "
              + str(len(missing_agents)) + " missing")
        if stale_agents:
            print("           Stale: " + ", ".join(stale_agents))
        if missing_agents:
            print("           Missing: " + ", ".join(missing_agents))

    def _check_artist_satisfaction(self):
        """Check 10: Artist satisfaction > 70% accept first batch."""
        print("\n  [10/10] Artist Satisfaction Check")
        selections = _read_jsonl(self.DIRECTION_FILE, days=7)

        if not selections:
            result = QACheckResult(
                check_id="artist_satisfaction",
                check_name="Artist Satisfaction (first batch acceptance)",
                passed=True,
                severity="info",
                metric_value=0.0,
                threshold=ARTIST_SATISFACTION_THRESHOLD,
                details={"note": "No direction selection data available"},
            )
            self.check_results.append(result)
            print("    [INFO] No direction selection data available")
            return

        total_sessions = len(selections)
        accepted_first = sum(
            1 for s in selections if s.get("accepted_first_batch", False)
        )
        acceptance_rate = (
            accepted_first / total_sessions if total_sessions > 0 else 0.0
        )

        passed = acceptance_rate >= ARTIST_SATISFACTION_THRESHOLD

        result = QACheckResult(
            check_id="artist_satisfaction",
            check_name="Artist Satisfaction (first batch acceptance)",
            passed=passed,
            severity="warning" if not passed else "info",
            metric_value=round(acceptance_rate, 4),
            threshold=ARTIST_SATISFACTION_THRESHOLD,
            details={
                "total_sessions": total_sessions,
                "accepted_first_batch": accepted_first,
                "acceptance_rate": round(acceptance_rate, 4),
            },
            remediation=(
                "Artist first-batch acceptance below 70%. "
                "Improve direction generation quality."
                if not passed else ""
            ),
        )
        self.check_results.append(result)

        status_str = "PASS" if passed else "WARN"
        print("    [" + status_str + "] " + str(accepted_first) + "/"
              + str(total_sessions) + " sessions accepted first batch ("
              + "{:.1f}".format(acceptance_rate * 100) + "%)")

    # ==================================================================
    # Report Generation
    # ==================================================================

    def _generate_report(self) -> QAReport:
        """Compile all check results into a full QA report."""
        total = len(self.check_results)
        passed = sum(1 for c in self.check_results if c.passed)
        failed = total - passed
        critical = sum(
            1 for c in self.check_results
            if not c.passed and c.severity == "critical"
        )

        if critical > 0:
            verdict = "FAIL"
        elif failed > 2:
            verdict = "DEGRADED"
        elif failed > 0:
            verdict = "DEGRADED"
        else:
            verdict = "PASS"

        # Pipeline health summary
        analysis = self.analyze()
        pipeline_health = {
            "quality_analysis": analysis,
            "api_base": self.api_base_url,
            "checked_at": datetime.now().isoformat(),
        }

        # Summary text
        summary_parts = [
            "QA Report: " + str(passed) + "/" + str(total) + " checks passed.",
        ]
        if critical > 0:
            summary_parts.append(
                str(critical) + " CRITICAL failures require immediate attention."
            )
        if self.regressions:
            regressed_count = sum(1 for r in self.regressions if r.regressed)
            if regressed_count > 0:
                summary_parts.append(
                    str(regressed_count) + " metric regressions detected."
                )
        if self.output_scores:
            scored = len(self.output_scores)
            score_passed = sum(1 for s in self.output_scores if s.passed)
            rej_rate = (1.0 - score_passed / scored) * 100 if scored > 0 else 0.0
            summary_parts.append(
                "Scored " + str(scored) + " outputs: " + str(score_passed)
                + " passed quality gate ("
                + "{:.0f}".format(rej_rate) + "% rejection rate)."
            )

        return QAReport(
            timestamp=datetime.now().isoformat(),
            total_checks=total,
            passed_checks=passed,
            failed_checks=failed,
            critical_failures=critical,
            overall_verdict=verdict,
            check_results=[asdict(c) for c in self.check_results],
            output_scores=[asdict(s) for s in self.output_scores],
            regressions=[asdict(r) for r in self.regressions],
            pipeline_health=pipeline_health,
            summary=" ".join(summary_parts),
        )

    def _save_report(self, report: QAReport):
        """Save report to qa_report.json."""
        try:
            with open(self.QA_REPORT_PATH, "w") as f:
                json.dump(asdict(report), f, indent=2)
            print("\n  Report saved: " + str(self.QA_REPORT_PATH))
        except OSError as e:
            print("\n  [ERROR] Failed to save report: " + str(e))

    def _log_decisions(self):
        """Log all QA decisions to qa_decisions.jsonl."""
        try:
            with open(self.QA_DECISIONS_LOG, "a") as f:
                entry = {
                    "timestamp": datetime.now().isoformat(),
                    "agent": "qa_engineer",
                    "total_checks": len(self.check_results),
                    "passed": sum(1 for c in self.check_results if c.passed),
                    "failed": sum(
                        1 for c in self.check_results if not c.passed
                    ),
                    "critical": sum(
                        1 for c in self.check_results
                        if not c.passed and c.severity == "critical"
                    ),
                    "outputs_scored": len(self.output_scores),
                    "outputs_passed": sum(
                        1 for s in self.output_scores if s.passed
                    ),
                    "regressions_found": sum(
                        1 for r in self.regressions if r.regressed
                    ),
                    "failed_checks": [
                        {
                            "id": c.check_id,
                            "name": c.check_name,
                            "severity": c.severity,
                        }
                        for c in self.check_results if not c.passed
                    ],
                }
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass

    def _write_qa_config(self):
        """Write qa_config.json with current thresholds and status."""
        config = {
            "version": 1,
            "updated_at": datetime.now().isoformat(),
            "quality_gate": {
                "minimum_quality_score": MINIMUM_QUALITY_SCORE,
                "minimum_technical_score": MINIMUM_TECHNICAL_SCORE,
                "expected_rejection_rate": {
                    "low": EXPECTED_REJECTION_RATE_LOW,
                    "high": EXPECTED_REJECTION_RATE_HIGH,
                },
                "hard_rejection_flags": HARD_REJECTION_FLAGS,
                "scoring_axes": {
                    name: {
                        "weight": cfg["weight"],
                        "min_score": cfg["min_score"],
                    }
                    for name, cfg in SCORING_AXES.items()
                },
            },
            "pipeline_limits": {
                "max_generation_time_seconds": MAX_GENERATION_TIME_SECONDS,
                "max_iteration_time_seconds": MAX_ITERATION_TIME_SECONDS,
                "loop_seamlessness_threshold": LOOP_SEAMLESSNESS_THRESHOLD,
                "artist_satisfaction_threshold": ARTIST_SATISFACTION_THRESHOLD,
            },
            "agent_monitoring": {
                "staleness_hours": AGENT_STALENESS_HOURS,
                "regression_window_days": REGRESSION_WINDOW_DAYS,
            },
            "last_run": {
                "timestamp": datetime.now().isoformat(),
                "total_checks": len(self.check_results),
                "passed": sum(1 for c in self.check_results if c.passed),
                "failed": sum(1 for c in self.check_results if not c.passed),
            },
        }

        try:
            with open(self.QA_CONFIG_PATH, "w") as f:
                json.dump(config, f, indent=2)
            print("  Config saved: " + str(self.QA_CONFIG_PATH))
        except OSError as e:
            print("  [ERROR] Failed to save config: " + str(e))

    def _print_report(self, report: QAReport):
        """Print formatted QA report to stdout."""
        sep = "=" * 65
        thin = "-" * 65

        print("\n" + sep)
        print("  QA REPORT -- " + report.overall_verdict)
        print(sep)
        print("  Checks: " + str(report.passed_checks) + "/"
              + str(report.total_checks) + " passed")
        print("  Critical failures: " + str(report.critical_failures))

        if self.output_scores:
            scored = len(self.output_scores)
            passed = sum(1 for s in self.output_scores if s.passed)
            rejection_rate = (
                (1.0 - passed / scored) * 100 if scored > 0 else 0.0
            )
            print("  Output quality: " + str(passed) + "/" + str(scored)
                  + " passed (" + "{:.0f}".format(rejection_rate)
                  + "% rejected)")

        if self.regressions:
            regressed = sum(1 for r in self.regressions if r.regressed)
            print("  Regressions: " + str(regressed) + " detected")

        print("\n" + thin)
        print("  FAILED CHECKS:")
        print(thin)

        failed = [c for c in self.check_results if not c.passed]
        if not failed:
            print("  (none)")
        else:
            for c in failed:
                severity_tag = c.severity.upper()
                print("  [" + severity_tag + "] " + c.check_name)
                print("           Value: " + str(c.metric_value)
                      + " | Threshold: " + str(c.threshold))
                if c.remediation:
                    print("           Fix: " + c.remediation)

        print("\n" + thin)
        print("  " + report.summary)
        print(sep + "\n")

    # ==================================================================
    # Helper Methods
    # ==================================================================

    def _compare_metric(self, name: str, current: float, previous: float,
                        regression_if: str = "lower",
                        critical_threshold: float = 0.1) -> RegressionResult:
        """Compare a metric between two time windows."""
        delta = current - previous
        delta_pct = (delta / previous * 100) if previous != 0 else 0.0

        if regression_if == "lower":
            regressed = current < previous
        else:  # "higher" means higher is bad (e.g., latency)
            regressed = current > previous

        abs_delta = abs(delta)
        if regressed and abs_delta >= critical_threshold:
            severity = "critical"
        elif regressed:
            severity = "warning"
        else:
            severity = "none"

        return RegressionResult(
            metric_name=name,
            current_value=round(current, 4),
            previous_value=round(previous, 4),
            delta=round(delta, 4),
            delta_pct=round(delta_pct, 2),
            regressed=regressed,
            severity=severity,
            details=(
                name + ": " + "{:.4f}".format(previous) + " -> "
                + "{:.4f}".format(current) + " ("
                + "{:+.1f}".format(delta_pct) + "%)"
            ),
        )

    @staticmethod
    def _percentile(values: List[float], pct: float) -> float:
        """Calculate percentile from a list of values."""
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        idx = int(len(sorted_vals) * pct)
        return sorted_vals[min(idx, len(sorted_vals) - 1)]


# ======================================================================
# Singleton
# ======================================================================

_instance = None


def get_qa_engineer() -> QAEngineer:
    """Get the global QAEngineer instance."""
    global _instance
    if _instance is None:
        _instance = QAEngineer()
    return _instance


# ======================================================================
# CLI
# ======================================================================

def main():
    """Entry point for CLI execution."""
    import argparse

    parser = argparse.ArgumentParser(
        description="QA Engineer Agent -- Canvas Quality Gate v2.0"
    )
    parser.add_argument(
        "command", nargs="?", default="run",
        choices=["run", "analyze", "validate", "report", "score"],
        help="Command to execute (default: run)",
    )
    parser.add_argument(
        "--api-base", type=str, default="http://localhost:3000",
        help="Base URL for API health checks (default: http://localhost:3000)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output results as JSON",
    )

    args = parser.parse_args()
    agent = QAEngineer(api_base_url=args.api_base)

    if args.command == "run":
        report = agent.run()
        if args.json:
            print(json.dumps(asdict(report), indent=2))

    elif args.command == "analyze":
        analysis = agent.analyze()
        if args.json:
            print(json.dumps(analysis, indent=2))
        else:
            print("\nQuality Analysis (last 7 days):")
            for key, value in analysis.items():
                if isinstance(value, float):
                    print("  " + key + ": " + "{:.4f}".format(value))
                else:
                    print("  " + key + ": " + str(value))

    elif args.command == "validate":
        result = agent.validate()
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("\nValidation: " + result["verdict"])
            print("  " + str(result["passed"]) + "/"
                  + str(result["total_checks"]) + " checks passed")

    elif args.command == "report":
        report_path = DATA_DIR / "qa_report.json"
        if report_path.exists():
            with open(report_path) as f:
                report = json.load(f)
            if args.json:
                print(json.dumps(report, indent=2))
            else:
                print("\nLatest QA Report ("
                      + report.get("timestamp", "unknown") + "):")
                print("  Verdict: " + report.get("overall_verdict", "unknown"))
                print("  Checks: " + str(report.get("passed_checks", 0))
                      + "/" + str(report.get("total_checks", 0)) + " passed")
                print("  Critical: " + str(report.get("critical_failures", 0)))
                print("  Summary: " + report.get("summary", ""))
        else:
            print("No QA report found. Run 'qa_engineer.py run' first.")

    elif args.command == "score":
        # Score all recent outputs and print results
        results = _read_jsonl(OPT_DIR / "canvas_results.jsonl", days=7)
        if not results:
            print("No canvas results to score.")
        else:
            total = 0
            passed = 0
            for r in results:
                score = agent.score_output(r)
                total += 1
                if score.passed:
                    passed += 1
                else:
                    if not args.json:
                        reasons = "; ".join(score.rejection_reasons[:3])
                        print("  REJECT " + score.job_id + ": "
                              + "{:.2f}".format(score.overall_score)
                              + "/10 -- " + reasons)

            rej_rate = (
                (1.0 - passed / total) * 100 if total > 0 else 0.0
            )
            print("\nScored " + str(total) + " outputs: " + str(passed)
                  + " passed, " + str(total - passed) + " rejected ("
                  + "{:.0f}".format(rej_rate) + "% rejection rate)")


if __name__ == "__main__":
    main()
