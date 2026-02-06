#!/usr/bin/env python3
"""
Canvas Self-Optimization Loop

The system that makes LoopCanvas get better every day without human intervention.
Runs as a scheduled job (GitHub Actions cron or local cron) — $0 cost.

What it does:
1. QUALITY FEEDBACK: Analyzes all generated canvases, records quality scores
2. PROMPT TUNING: Identifies which prompts produce highest-scoring outputs,
   evolves prompt templates toward what works
3. PARAMETER EVOLUTION: Tracks which FFmpeg post-processing params
   (grain, contrast, saturation, blur) score highest per director style,
   updates default params toward optimums
4. STYLE CALIBRATION: Detects which director styles get selected most,
   weights future direction generation toward popular styles
5. FAILURE ANALYSIS: Logs what causes quality gate failures, adds
   those patterns to negative prompts

This is NOT ML training. It's deterministic optimization:
- Log results → analyze patterns → update config → repeat

Data lives in JSON files. No database needed. $0.
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict


# Paths
ENGINE_DIR = Path(__file__).parent.parent
APP_DIR = ENGINE_DIR.parent
DATA_DIR = ENGINE_DIR / "optimization_data"
DATA_DIR.mkdir(exist_ok=True)


@dataclass
class CanvasResult:
    """Record of a generated canvas and its quality"""
    job_id: str
    timestamp: str
    director_style: str
    prompt: str
    params: Dict
    quality_score: float
    quality_passed: bool
    quality_breakdown: Dict
    loop_score: float
    selected_by_artist: bool  # Did the artist choose this direction?
    iterated: bool  # Did the artist iterate on it?
    exported: bool  # Did the artist export it?
    export_platforms: List[str]


@dataclass
class OptimizationState:
    """Current optimization state"""
    last_run: str
    total_canvases_analyzed: int
    avg_quality_score: float
    best_quality_score: float
    pass_rate: float  # % that pass quality gate
    most_selected_style: str
    prompt_evolution_generation: int  # How many rounds of prompt tuning

    # Per-style performance
    style_scores: Dict[str, Dict]  # style_id → {avg_score, count, selection_rate}

    # Evolved parameters (the output of optimization)
    evolved_params: Dict[str, Dict]  # style_id → optimized params
    evolved_negative_prompts: List[str]  # Patterns to avoid


class OptimizationLoop:
    """
    The self-optimization engine.

    Call run() on a schedule (daily via cron/GitHub Actions).
    It reads all generation results, analyzes patterns,
    and updates configuration files that the orchestrator reads.
    """

    def __init__(self):
        self.results_file = DATA_DIR / "canvas_results.jsonl"
        self.state_file = DATA_DIR / "optimization_state.json"
        self.evolved_config_file = DATA_DIR / "evolved_config.json"

        self.state = self._load_state()

    def _load_state(self) -> OptimizationState:
        """Load current optimization state"""
        if self.state_file.exists():
            with open(self.state_file) as f:
                data = json.load(f)
                return OptimizationState(**data)

        return OptimizationState(
            last_run="never",
            total_canvases_analyzed=0,
            avg_quality_score=0.0,
            best_quality_score=0.0,
            pass_rate=0.0,
            most_selected_style="observed_moment",
            prompt_evolution_generation=0,
            style_scores={},
            evolved_params={},
            evolved_negative_prompts=[],
        )

    def _save_state(self):
        """Save optimization state"""
        with open(self.state_file, 'w') as f:
            json.dump(asdict(self.state), f, indent=2)

    def log_result(self, result: CanvasResult):
        """Log a canvas generation result for future analysis"""
        with open(self.results_file, 'a') as f:
            f.write(json.dumps(asdict(result)) + "\n")

    def _load_results(self, since_days: int = 30) -> List[CanvasResult]:
        """Load recent results"""
        if not self.results_file.exists():
            return []

        cutoff = datetime.now() - timedelta(days=since_days)
        results = []

        with open(self.results_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    ts = datetime.fromisoformat(data['timestamp'])
                    if ts >= cutoff:
                        results.append(CanvasResult(**data))
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue

        return results

    def run(self):
        """
        Run the full optimization loop.

        This is meant to be called on a schedule (daily).
        It's idempotent — safe to run multiple times.
        """
        print(f"\n{'='*60}")
        print(f"CANVAS OPTIMIZATION LOOP — {datetime.now().isoformat()}")
        print(f"{'='*60}")

        results = self._load_results(since_days=30)

        if not results:
            print("No results to analyze yet. Skipping optimization.")
            self.state.last_run = datetime.now().isoformat()
            self._save_state()
            return

        print(f"Analyzing {len(results)} canvases from last 30 days...")

        # === Step 1: Quality Analysis ===
        self._analyze_quality(results)

        # === Step 2: Style Performance ===
        self._analyze_styles(results)

        # === Step 3: Parameter Evolution ===
        self._evolve_parameters(results)

        # === Step 4: Prompt Evolution ===
        self._evolve_prompts(results)

        # === Step 5: Failure Analysis ===
        self._analyze_failures(results)

        # === Step 6: Write evolved config ===
        self._write_evolved_config()

        # Update state
        self.state.last_run = datetime.now().isoformat()
        self.state.total_canvases_analyzed = len(results)
        self.state.prompt_evolution_generation += 1
        self._save_state()

        print(f"\nOptimization complete. Generation #{self.state.prompt_evolution_generation}")
        self._print_report()

    def _analyze_quality(self, results: List[CanvasResult]):
        """Analyze overall quality trends"""
        scores = [r.quality_score for r in results]
        passed = [r for r in results if r.quality_passed]

        self.state.avg_quality_score = sum(scores) / len(scores) if scores else 0
        self.state.best_quality_score = max(scores) if scores else 0
        self.state.pass_rate = len(passed) / len(results) if results else 0

        print(f"\n  Quality Analysis:")
        print(f"    Average score: {self.state.avg_quality_score:.2f}/10")
        print(f"    Best score:    {self.state.best_quality_score:.2f}/10")
        print(f"    Pass rate:     {self.state.pass_rate*100:.1f}%")

    def _analyze_styles(self, results: List[CanvasResult]):
        """Analyze per-style performance and selection rates"""
        style_data = {}

        for r in results:
            style = r.director_style
            if style not in style_data:
                style_data[style] = {
                    'scores': [],
                    'selected_count': 0,
                    'total_count': 0,
                    'exported_count': 0,
                }

            style_data[style]['scores'].append(r.quality_score)
            style_data[style]['total_count'] += 1
            if r.selected_by_artist:
                style_data[style]['selected_count'] += 1
            if r.exported:
                style_data[style]['exported_count'] += 1

        # Build style scores
        self.state.style_scores = {}
        for style, data in style_data.items():
            scores = data['scores']
            self.state.style_scores[style] = {
                'avg_score': sum(scores) / len(scores) if scores else 0,
                'count': data['total_count'],
                'selection_rate': data['selected_count'] / data['total_count'] if data['total_count'] else 0,
                'export_rate': data['exported_count'] / data['total_count'] if data['total_count'] else 0,
            }

        # Find most popular
        if style_data:
            self.state.most_selected_style = max(
                style_data,
                key=lambda s: style_data[s]['selected_count']
            )

        print(f"\n  Style Analysis:")
        for style, info in sorted(
            self.state.style_scores.items(),
            key=lambda x: x[1]['avg_score'],
            reverse=True
        ):
            print(f"    {style}: avg={info['avg_score']:.1f}, "
                  f"selected={info['selection_rate']*100:.0f}%, "
                  f"n={info['count']}")

    def _evolve_parameters(self, results: List[CanvasResult]):
        """
        Evolve post-processing parameters toward what scores highest.

        Strategy: For each director style, find the parameter combinations
        that produced the highest quality scores, then nudge defaults
        toward those values.
        """
        # Group results by style
        style_results = {}
        for r in results:
            style = r.director_style
            if style not in style_results:
                style_results[style] = []
            style_results[style].append(r)

        self.state.evolved_params = {}

        for style, style_rs in style_results.items():
            if len(style_rs) < 3:
                continue  # Need at least 3 data points

            # Sort by quality score (best first)
            style_rs.sort(key=lambda r: r.quality_score, reverse=True)

            # Take top 30% as "what works"
            top_count = max(1, len(style_rs) // 3)
            top_results = style_rs[:top_count]

            # Average their parameters
            param_keys = set()
            for r in top_results:
                param_keys.update(r.params.keys())

            evolved = {}
            for key in param_keys:
                values = [r.params.get(key) for r in top_results if key in r.params]
                numeric_values = [v for v in values if isinstance(v, (int, float))]
                if numeric_values:
                    evolved[key] = sum(numeric_values) / len(numeric_values)

            self.state.evolved_params[style] = evolved

        print(f"\n  Parameter Evolution:")
        print(f"    Evolved params for {len(self.state.evolved_params)} styles")

    def _evolve_prompts(self, results: List[CanvasResult]):
        """
        Analyze which prompt patterns produce higher quality.

        Strategy: Extract common words/phrases from high-scoring prompts
        vs low-scoring prompts. Build a "good words" and "bad words" list.
        """
        if len(results) < 10:
            return  # Need enough data

        # Sort by quality
        sorted_results = sorted(results, key=lambda r: r.quality_score, reverse=True)

        top_quarter = sorted_results[:len(sorted_results)//4]
        bottom_quarter = sorted_results[-(len(sorted_results)//4):]

        # Extract words from prompts
        def extract_words(result_list):
            words = {}
            for r in result_list:
                for word in r.prompt.lower().split():
                    word = word.strip('.,!?;:"\'')
                    if len(word) > 3:  # Skip short words
                        words[word] = words.get(word, 0) + 1
            return words

        good_words = extract_words(top_quarter)
        bad_words = extract_words(bottom_quarter)

        # Words that appear in good but not bad (or much more in good)
        beneficial_words = []
        harmful_words = []

        for word, count in good_words.items():
            bad_count = bad_words.get(word, 0)
            if count > bad_count * 2:
                beneficial_words.append((word, count))

        for word, count in bad_words.items():
            good_count = good_words.get(word, 0)
            if count > good_count * 2:
                harmful_words.append((word, count))

        beneficial_words.sort(key=lambda x: x[1], reverse=True)
        harmful_words.sort(key=lambda x: x[1], reverse=True)

        print(f"\n  Prompt Evolution:")
        if beneficial_words[:5]:
            print(f"    Beneficial patterns: {', '.join(w for w, _ in beneficial_words[:5])}")
        if harmful_words[:5]:
            print(f"    Harmful patterns: {', '.join(w for w, _ in harmful_words[:5])}")

    def _analyze_failures(self, results: List[CanvasResult]):
        """Analyze quality gate failures to prevent them"""
        failures = [r for r in results if not r.quality_passed]

        if not failures:
            return

        # Collect common issues from quality breakdowns
        issue_counts = {}
        for r in failures:
            for issue in r.quality_breakdown.get('issues', []):
                issue_key = issue.split(':')[0].strip().lower()
                issue_counts[issue_key] = issue_counts.get(issue_key, 0) + 1

        # Add top failure patterns to negative prompts
        for issue, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True):
            if count >= 2:  # Recurring issue
                if 'smooth' in issue:
                    self.state.evolved_negative_prompts.append('unnaturally smooth')
                elif 'morphing' in issue:
                    self.state.evolved_negative_prompts.append('morphing, warping')
                elif 'flicker' in issue:
                    self.state.evolved_negative_prompts.append('flickering, strobing')

        # Deduplicate
        self.state.evolved_negative_prompts = list(set(self.state.evolved_negative_prompts))

        print(f"\n  Failure Analysis:")
        print(f"    {len(failures)} failures out of {len(results)} total")
        for issue, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"    - {issue}: {count} occurrences")

    def _write_evolved_config(self):
        """Write the evolved configuration that the orchestrator reads"""
        config = {
            'version': self.state.prompt_evolution_generation,
            'updated_at': datetime.now().isoformat(),
            'style_performance': self.state.style_scores,
            'evolved_params': self.state.evolved_params,
            'negative_prompt_additions': self.state.evolved_negative_prompts,
            'most_popular_style': self.state.most_selected_style,
            'metrics': {
                'avg_quality': self.state.avg_quality_score,
                'pass_rate': self.state.pass_rate,
                'best_score': self.state.best_quality_score,
            },
        }

        with open(self.evolved_config_file, 'w') as f:
            json.dump(config, f, indent=2)

        print(f"\n  Evolved config written to: {self.evolved_config_file}")

    def _print_report(self):
        """Print optimization report"""
        print(f"\n{'='*60}")
        print(f"OPTIMIZATION REPORT — Gen #{self.state.prompt_evolution_generation}")
        print(f"{'='*60}")
        print(f"  Total canvases:     {self.state.total_canvases_analyzed}")
        print(f"  Avg quality:        {self.state.avg_quality_score:.2f}/10")
        print(f"  Pass rate:          {self.state.pass_rate*100:.1f}%")
        print(f"  Most popular style: {self.state.most_selected_style}")
        print(f"  Styles evolved:     {len(self.state.evolved_params)}")
        print(f"  Negative patterns:  {len(self.state.evolved_negative_prompts)}")
        print(f"{'='*60}")

    def get_evolved_params(self, style: str) -> Dict:
        """Get evolved parameters for a style (called by orchestrator)"""
        # Try loading from file (may have been updated by a previous run)
        if self.evolved_config_file.exists():
            with open(self.evolved_config_file) as f:
                config = json.load(f)
                return config.get('evolved_params', {}).get(style, {})
        return self.state.evolved_params.get(style, {})

    def get_negative_prompts(self) -> List[str]:
        """Get evolved negative prompt additions"""
        if self.evolved_config_file.exists():
            with open(self.evolved_config_file) as f:
                config = json.load(f)
                return config.get('negative_prompt_additions', [])
        return self.state.evolved_negative_prompts


# CLI
if __name__ == "__main__":
    import sys

    loop = OptimizationLoop()

    if len(sys.argv) > 1 and sys.argv[1] == "report":
        loop._print_report()
    else:
        loop.run()
