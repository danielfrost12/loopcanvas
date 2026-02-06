#!/usr/bin/env python3
"""
Tests for Autonomous Engineering Agents
100+ tests covering RetentionEngineer, OnboardingOptimizer, GrowthEngineer
"""

import json
import os
import sys
import shutil
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from dataclasses import asdict

# Add canvas-engine to path
ENGINE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ENGINE_DIR.parent))
sys.path.insert(0, str(ENGINE_DIR))


# ═══════════════════════════════════════════════════════════════════
#  Helper: Create isolated test environment
# ═══════════════════════════════════════════════════════════════════

class AgentTestBase(unittest.TestCase):
    """Base class that creates isolated temp directories for each test"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.engine_dir = Path(self.tmpdir) / "canvas-engine"
        self.app_dir = Path(self.tmpdir)
        self.data_dir = self.engine_dir / "checklist_data"
        self.opt_dir = self.engine_dir / "optimization_data"
        self.template_dir = self.app_dir / "templates"
        self.agents_dir = self.engine_dir / "agents"

        for d in [self.data_dir, self.opt_dir, self.template_dir, self.agents_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def write_jsonl(self, filepath: Path, entries: list):
        """Write a list of dicts as JSONL"""
        with open(filepath, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

    def make_funnel_data(self, counts: dict) -> list:
        """Create funnel JSONL entries from stage counts"""
        entries = []
        for event, count in counts.items():
            for i in range(count):
                entries.append({
                    "event": event,
                    "data": {"sessionId": f"sess_{i}", "is_mobile": False},
                    "ts": int(datetime.utcnow().timestamp() * 1000),
                })
        return entries

    def make_mobile_funnel_data(self, counts: dict) -> list:
        """Create mobile funnel JSONL entries"""
        entries = []
        for event, count in counts.items():
            for i in range(count):
                entries.append({
                    "event": event,
                    "data": {"sessionId": f"mob_{i}", "is_mobile": True},
                    "ts": int(datetime.utcnow().timestamp() * 1000),
                })
        return entries


# ═══════════════════════════════════════════════════════════════════
#  RETENTION ENGINEER TESTS
# ═══════════════════════════════════════════════════════════════════

class TestRetentionEngineerInit(AgentTestBase):
    """Test RetentionEngineer initialization"""

    def _make_engineer(self):
        from agents.retention_engineer import RetentionEngineer
        with patch('agents.retention_engineer.ENGINE_DIR', self.engine_dir), \
             patch('agents.retention_engineer.APP_DIR', self.app_dir), \
             patch('agents.retention_engineer.DATA_DIR', self.data_dir), \
             patch('agents.retention_engineer.OPT_DATA_DIR', self.opt_dir), \
             patch('agents.retention_engineer.TEMPLATE_DIR', self.template_dir), \
             patch('agents.retention_engineer.CONFIG_DIR', self.app_dir):
            return RetentionEngineer()

    def test_init_no_existing_config(self):
        eng = self._make_engineer()
        self.assertIsNotNone(eng.current_config)
        self.assertEqual(eng.current_config["phase"], 1)

    def test_init_with_existing_config(self):
        config = {"version": 2, "phase": 3, "features": {"gallery": {"enabled": True}}}
        (self.app_dir / "retention_config.json").write_text(json.dumps(config))
        eng = self._make_engineer()
        self.assertEqual(eng.current_config["phase"], 3)

    def test_init_with_corrupt_config(self):
        (self.app_dir / "retention_config.json").write_text("not json{{{")
        eng = self._make_engineer()
        self.assertEqual(eng.current_config["phase"], 1)  # Falls back to defaults

    def test_init_metrics_zeroed(self):
        eng = self._make_engineer()
        self.assertEqual(eng.metrics.total_users, 0)
        self.assertEqual(eng.metrics.return_rate, 0.0)

    def test_init_decisions_log_empty(self):
        eng = self._make_engineer()
        self.assertEqual(len(eng.decisions_log), 0)


class TestRetentionEngineerAnalyze(AgentTestBase):
    """Test RetentionEngineer.analyze()"""

    def _make_engineer(self):
        from agents.retention_engineer import RetentionEngineer
        with patch('agents.retention_engineer.ENGINE_DIR', self.engine_dir), \
             patch('agents.retention_engineer.APP_DIR', self.app_dir), \
             patch('agents.retention_engineer.DATA_DIR', self.data_dir), \
             patch('agents.retention_engineer.OPT_DATA_DIR', self.opt_dir), \
             patch('agents.retention_engineer.TEMPLATE_DIR', self.template_dir), \
             patch('agents.retention_engineer.CONFIG_DIR', self.app_dir):
            return RetentionEngineer()

    def test_analyze_empty_data(self):
        eng = self._make_engineer()
        metrics = eng.analyze()
        self.assertEqual(metrics.total_users, 1)  # min 1 to avoid div by zero
        self.assertEqual(metrics.return_rate, 0.0)

    def test_analyze_with_users(self):
        self.write_jsonl(self.data_dir / "user_activity.jsonl", [
            {"session_id": "a", "timestamp": datetime.utcnow().isoformat(), "event": "page_load"},
            {"session_id": "b", "timestamp": datetime.utcnow().isoformat(), "event": "page_load"},
            {"session_id": "a", "timestamp": datetime.utcnow().isoformat(), "event": "page_load", "is_return": True},
        ])
        eng = self._make_engineer()
        metrics = eng.analyze()
        self.assertEqual(metrics.total_users, 2)
        self.assertEqual(metrics.returning_users, 1)
        self.assertAlmostEqual(metrics.return_rate, 0.5)

    def test_analyze_export_rate(self):
        self.write_jsonl(self.data_dir / "onboarding_funnel.jsonl", [
            {"event": "generate_complete"}, {"event": "generate_complete"},
            {"event": "export"}, {"event": "page_load"},
        ])
        eng = self._make_engineer()
        metrics = eng.analyze()
        self.assertAlmostEqual(metrics.export_rate, 0.5)  # 1 export / 2 generates

    def test_analyze_share_rate(self):
        self.write_jsonl(self.data_dir / "onboarding_funnel.jsonl", [
            {"event": "generate_complete"}, {"event": "generate_complete"},
            {"event": "share"}, {"event": "page_load"},
        ])
        eng = self._make_engineer()
        metrics = eng.analyze()
        self.assertAlmostEqual(metrics.share_rate, 0.5)

    def test_analyze_gallery_usage(self):
        self.write_jsonl(self.data_dir / "onboarding_funnel.jsonl", [
            {"event": "page_load"}, {"event": "page_load"},
            {"event": "gallery_view"},
        ])
        eng = self._make_engineer()
        metrics = eng.analyze()
        self.assertAlmostEqual(metrics.gallery_usage_rate, 0.5)

    def test_analyze_malformed_jsonl(self):
        with open(self.data_dir / "user_activity.jsonl", "w") as f:
            f.write('{"session_id":"a"}\n')
            f.write('not json\n')
            f.write('{"session_id":"b"}\n')
        eng = self._make_engineer()
        metrics = eng.analyze()
        self.assertEqual(metrics.total_users, 2)  # Skips malformed line

    def test_analyze_missing_files(self):
        eng = self._make_engineer()
        metrics = eng.analyze()
        self.assertIsNotNone(metrics)  # Should not crash

    def test_analyze_canvases_per_user(self):
        self.write_jsonl(self.data_dir / "user_activity.jsonl", [
            {"session_id": "a", "event": "generate_complete", "timestamp": datetime.utcnow().isoformat()},
            {"session_id": "a", "event": "generate_complete", "timestamp": datetime.utcnow().isoformat()},
            {"session_id": "b", "event": "generate_complete", "timestamp": datetime.utcnow().isoformat()},
        ])
        eng = self._make_engineer()
        metrics = eng.analyze()
        self.assertAlmostEqual(metrics.avg_canvases_per_user, 1.5)

    def test_analyze_zero_generations(self):
        self.write_jsonl(self.data_dir / "onboarding_funnel.jsonl", [
            {"event": "page_load"},
        ])
        eng = self._make_engineer()
        metrics = eng.analyze()
        self.assertEqual(metrics.share_rate, 0.0)
        self.assertEqual(metrics.export_rate, 0.0)

    def test_analyze_batch_interest(self):
        self.write_jsonl(self.data_dir / "onboarding_funnel.jsonl", [
            {"event": "page_load"}, {"event": "page_load"},
            {"event": "batch_interest"},
        ])
        eng = self._make_engineer()
        metrics = eng.analyze()
        self.assertAlmostEqual(metrics.batch_mode_interest, 0.5)


class TestRetentionEngineerDecide(AgentTestBase):
    """Test RetentionEngineer.decide()"""

    def _make_engineer(self):
        from agents.retention_engineer import RetentionEngineer
        with patch('agents.retention_engineer.ENGINE_DIR', self.engine_dir), \
             patch('agents.retention_engineer.APP_DIR', self.app_dir), \
             patch('agents.retention_engineer.DATA_DIR', self.data_dir), \
             patch('agents.retention_engineer.OPT_DATA_DIR', self.opt_dir), \
             patch('agents.retention_engineer.TEMPLATE_DIR', self.template_dir), \
             patch('agents.retention_engineer.CONFIG_DIR', self.app_dir):
            return RetentionEngineer()

    def test_decide_phase1_default(self):
        eng = self._make_engineer()
        eng.analyze()
        decision = eng.decide()
        self.assertEqual(decision.phase, 1)
        self.assertIn("gallery", decision.features_enabled)
        self.assertIn("return_banner", decision.features_enabled)

    def test_decide_phase2_on_metrics(self):
        eng = self._make_engineer()
        eng.analyze()
        eng.metrics.return_rate = 0.06
        eng.metrics.gallery_usage_rate = 0.15
        decision = eng.decide()
        self.assertEqual(decision.phase, 2)
        self.assertIn("share_modal", decision.features_enabled)

    def test_decide_phase3_on_metrics(self):
        eng = self._make_engineer()
        eng.analyze()
        eng.metrics.return_rate = 0.20
        eng.metrics.share_rate = 0.08
        decision = eng.decide()
        self.assertEqual(decision.phase, 3)
        self.assertIn("director_comparison", decision.features_enabled)

    def test_decide_phase4_on_metrics(self):
        eng = self._make_engineer()
        eng.analyze()
        eng.metrics.return_rate = 0.30
        eng.metrics.share_rate = 0.15
        decision = eng.decide()
        self.assertEqual(decision.phase, 4)
        self.assertIn("smart_prompts", decision.features_enabled)

    def test_decide_no_regress_more_than_one(self):
        config = {"version": 1, "phase": 4, "features": {
            "gallery": {"enabled": True}, "return_banner": {"enabled": True},
            "share_modal": {"enabled": True}, "batch_teaser": {"enabled": True},
            "director_comparison": {"enabled": True}, "ab_testing": {"enabled": True, "variant": "control", "split": 0.5},
            "smart_prompts": {"enabled": True},
        }, "copy": {}, "thresholds": {}, "last_updated": "", "last_decision": ""}
        (self.app_dir / "retention_config.json").write_text(json.dumps(config))
        eng = self._make_engineer()
        eng.analyze()
        # Metrics are all 0 → should be phase 1, but can only go down 1 from 4 → phase 3
        decision = eng.decide()
        self.assertGreaterEqual(decision.phase, 3)

    def test_decide_has_reasoning(self):
        eng = self._make_engineer()
        eng.analyze()
        decision = eng.decide()
        self.assertIn("Phase", decision.reasoning)
        self.assertIn("return_rate", decision.reasoning)

    def test_decide_has_timestamp(self):
        eng = self._make_engineer()
        eng.analyze()
        decision = eng.decide()
        self.assertTrue(decision.timestamp.endswith("Z"))

    def test_decide_has_metrics_snapshot(self):
        eng = self._make_engineer()
        eng.analyze()
        decision = eng.decide()
        self.assertIn("total_users", decision.metrics_snapshot)

    def test_decide_ab_test_variant(self):
        eng = self._make_engineer()
        eng.analyze()
        eng.metrics.return_rate = 0.20
        eng.metrics.share_rate = 0.08
        decision = eng.decide()
        self.assertTrue(decision.ab_test_active)
        self.assertIn(decision.ab_test_variant, ["control", "variant_a"])

    def test_decide_features_disabled(self):
        config = {"version": 1, "phase": 3, "features": {
            "gallery": {"enabled": True}, "return_banner": {"enabled": True},
            "share_modal": {"enabled": True}, "batch_teaser": {"enabled": True},
            "director_comparison": {"enabled": True}, "ab_testing": {"enabled": True, "variant": "control", "split": 0.5},
            "smart_prompts": {"enabled": True},
        }, "copy": {}, "thresholds": {}, "last_updated": "", "last_decision": ""}
        (self.app_dir / "retention_config.json").write_text(json.dumps(config))
        eng = self._make_engineer()
        eng.analyze()
        # Phase 1 metrics → disables features from phase 3
        decision = eng.decide()
        self.assertTrue(len(decision.features_disabled) > 0 or decision.phase >= 2)


class TestRetentionEngineerConfig(AgentTestBase):
    """Test RetentionEngineer config writing"""

    def _make_engineer(self):
        from agents.retention_engineer import RetentionEngineer, RetentionDecision
        with patch('agents.retention_engineer.ENGINE_DIR', self.engine_dir), \
             patch('agents.retention_engineer.APP_DIR', self.app_dir), \
             patch('agents.retention_engineer.DATA_DIR', self.data_dir), \
             patch('agents.retention_engineer.OPT_DATA_DIR', self.opt_dir), \
             patch('agents.retention_engineer.TEMPLATE_DIR', self.template_dir), \
             patch('agents.retention_engineer.CONFIG_DIR', self.app_dir):
            return RetentionEngineer()

    def test_write_config_creates_file(self):
        from agents.retention_engineer import RetentionDecision
        eng = self._make_engineer()
        eng.analyze()
        decision = eng.decide()
        with patch('agents.retention_engineer.CONFIG_PATH', self.app_dir / "retention_config.json"):
            path = eng.write_config(decision)
        self.assertTrue((self.app_dir / "retention_config.json").exists())

    def test_write_config_valid_json(self):
        from agents.retention_engineer import RetentionDecision
        eng = self._make_engineer()
        eng.analyze()
        decision = eng.decide()
        with patch('agents.retention_engineer.CONFIG_PATH', self.app_dir / "retention_config.json"):
            eng.write_config(decision)
        data = json.loads((self.app_dir / "retention_config.json").read_text())
        self.assertIn("features", data)
        self.assertIn("phase", data)

    def test_write_config_updates_phase(self):
        from agents.retention_engineer import RetentionDecision
        eng = self._make_engineer()
        eng.analyze()
        decision = eng.decide()
        decision.phase = 2
        with patch('agents.retention_engineer.CONFIG_PATH', self.app_dir / "retention_config.json"):
            eng.write_config(decision)
        data = json.loads((self.app_dir / "retention_config.json").read_text())
        self.assertEqual(data["phase"], 2)

    def test_write_config_updates_timestamp(self):
        from agents.retention_engineer import RetentionDecision
        eng = self._make_engineer()
        eng.analyze()
        decision = eng.decide()
        with patch('agents.retention_engineer.CONFIG_PATH', self.app_dir / "retention_config.json"):
            eng.write_config(decision)
        data = json.loads((self.app_dir / "retention_config.json").read_text())
        self.assertTrue(len(data["last_updated"]) > 0)

    def test_write_config_feature_flags(self):
        from agents.retention_engineer import RetentionDecision
        eng = self._make_engineer()
        eng.analyze()
        decision = eng.decide()
        decision.features_enabled = ["gallery", "return_banner"]
        with patch('agents.retention_engineer.CONFIG_PATH', self.app_dir / "retention_config.json"):
            eng.write_config(decision)
        data = json.loads((self.app_dir / "retention_config.json").read_text())
        self.assertTrue(data["features"]["gallery"]["enabled"])
        self.assertTrue(data["features"]["return_banner"]["enabled"])
        self.assertFalse(data["features"]["share_modal"]["enabled"])

    def test_write_config_share_cta_phase2(self):
        from agents.retention_engineer import RetentionDecision
        eng = self._make_engineer()
        eng.analyze()
        decision = eng.decide()
        decision.phase = 2
        with patch('agents.retention_engineer.CONFIG_PATH', self.app_dir / "retention_config.json"):
            eng.write_config(decision)
        data = json.loads((self.app_dir / "retention_config.json").read_text())
        self.assertIn("world", data["copy"]["share_cta"].lower())

    def test_write_config_stores_reasoning(self):
        from agents.retention_engineer import RetentionDecision
        eng = self._make_engineer()
        eng.analyze()
        decision = eng.decide()
        with patch('agents.retention_engineer.CONFIG_PATH', self.app_dir / "retention_config.json"):
            eng.write_config(decision)
        data = json.loads((self.app_dir / "retention_config.json").read_text())
        self.assertTrue(len(data["last_decision"]) > 0)

    def test_write_config_idempotent(self):
        from agents.retention_engineer import RetentionDecision
        eng = self._make_engineer()
        eng.analyze()
        decision = eng.decide()
        with patch('agents.retention_engineer.CONFIG_PATH', self.app_dir / "retention_config.json"):
            eng.write_config(decision)
            data1 = json.loads((self.app_dir / "retention_config.json").read_text())
            eng.write_config(decision)
            data2 = json.loads((self.app_dir / "retention_config.json").read_text())
        self.assertEqual(data1["phase"], data2["phase"])


class TestRetentionEngineerTemplates(AgentTestBase):
    """Test RetentionEngineer template writing"""

    def _make_engineer(self):
        from agents.retention_engineer import RetentionEngineer
        with patch('agents.retention_engineer.ENGINE_DIR', self.engine_dir), \
             patch('agents.retention_engineer.APP_DIR', self.app_dir), \
             patch('agents.retention_engineer.DATA_DIR', self.data_dir), \
             patch('agents.retention_engineer.OPT_DATA_DIR', self.opt_dir), \
             patch('agents.retention_engineer.TEMPLATE_DIR', self.template_dir), \
             patch('agents.retention_engineer.CONFIG_DIR', self.app_dir):
            return RetentionEngineer()

    def test_write_templates_phase1(self):
        from agents.retention_engineer import RetentionDecision
        eng = self._make_engineer()
        eng.analyze()
        decision = eng.decide()
        decision.phase = 1
        with patch('agents.retention_engineer.TEMPLATE_DIR', self.template_dir):
            paths = eng.write_templates(decision)
        self.assertEqual(len(paths), 2)  # gallery + banner
        self.assertTrue((self.template_dir / "gallery_component.html").exists())
        self.assertTrue((self.template_dir / "return_banner.html").exists())

    def test_write_templates_phase2_includes_share(self):
        from agents.retention_engineer import RetentionDecision
        eng = self._make_engineer()
        eng.analyze()
        decision = eng.decide()
        decision.phase = 2
        with patch('agents.retention_engineer.TEMPLATE_DIR', self.template_dir):
            paths = eng.write_templates(decision)
        self.assertEqual(len(paths), 3)  # gallery + banner + share
        self.assertTrue((self.template_dir / "share_modal.html").exists())

    def test_templates_contain_html(self):
        from agents.retention_engineer import RetentionDecision
        eng = self._make_engineer()
        eng.analyze()
        decision = eng.decide()
        with patch('agents.retention_engineer.TEMPLATE_DIR', self.template_dir):
            eng.write_templates(decision)
        content = (self.template_dir / "gallery_component.html").read_text()
        self.assertIn("<div", content)
        self.assertIn("gallery", content.lower())

    def test_templates_contain_glass_design(self):
        from agents.retention_engineer import RetentionDecision
        eng = self._make_engineer()
        eng.analyze()
        decision = eng.decide()
        with patch('agents.retention_engineer.TEMPLATE_DIR', self.template_dir):
            eng.write_templates(decision)
        content = (self.template_dir / "gallery_component.html").read_text()
        self.assertIn("Inter", content)  # Uses Inter font

    def test_templates_contain_scripts(self):
        from agents.retention_engineer import RetentionDecision
        eng = self._make_engineer()
        eng.analyze()
        decision = eng.decide()
        with patch('agents.retention_engineer.TEMPLATE_DIR', self.template_dir):
            eng.write_templates(decision)
        content = (self.template_dir / "gallery_component.html").read_text()
        self.assertIn("<script>", content)


class TestRetentionEngineerRun(AgentTestBase):
    """Test RetentionEngineer.run() full cycle"""

    def _make_engineer(self):
        from agents.retention_engineer import RetentionEngineer
        with patch('agents.retention_engineer.ENGINE_DIR', self.engine_dir), \
             patch('agents.retention_engineer.APP_DIR', self.app_dir), \
             patch('agents.retention_engineer.DATA_DIR', self.data_dir), \
             patch('agents.retention_engineer.OPT_DATA_DIR', self.opt_dir), \
             patch('agents.retention_engineer.TEMPLATE_DIR', self.template_dir), \
             patch('agents.retention_engineer.CONFIG_DIR', self.app_dir):
            return RetentionEngineer()

    def test_run_returns_success(self):
        eng = self._make_engineer()
        with patch('agents.retention_engineer.CONFIG_PATH', self.app_dir / "retention_config.json"), \
             patch('agents.retention_engineer.TEMPLATE_DIR', self.template_dir), \
             patch('agents.retention_engineer.DATA_DIR', self.data_dir):
            result = eng.run()
        self.assertEqual(result["status"], "success")

    def test_run_creates_config(self):
        eng = self._make_engineer()
        with patch('agents.retention_engineer.CONFIG_PATH', self.app_dir / "retention_config.json"), \
             patch('agents.retention_engineer.TEMPLATE_DIR', self.template_dir), \
             patch('agents.retention_engineer.DATA_DIR', self.data_dir):
            eng.run()
        self.assertTrue((self.app_dir / "retention_config.json").exists())

    def test_run_creates_templates(self):
        eng = self._make_engineer()
        with patch('agents.retention_engineer.CONFIG_PATH', self.app_dir / "retention_config.json"), \
             patch('agents.retention_engineer.TEMPLATE_DIR', self.template_dir), \
             patch('agents.retention_engineer.DATA_DIR', self.data_dir):
            eng.run()
        self.assertTrue((self.template_dir / "gallery_component.html").exists())

    def test_run_logs_decision(self):
        eng = self._make_engineer()
        with patch('agents.retention_engineer.CONFIG_PATH', self.app_dir / "retention_config.json"), \
             patch('agents.retention_engineer.TEMPLATE_DIR', self.template_dir), \
             patch('agents.retention_engineer.DATA_DIR', self.data_dir):
            eng.run()
        self.assertTrue((self.data_dir / "retention_decisions.jsonl").exists())

    def test_run_result_has_all_fields(self):
        eng = self._make_engineer()
        with patch('agents.retention_engineer.CONFIG_PATH', self.app_dir / "retention_config.json"), \
             patch('agents.retention_engineer.TEMPLATE_DIR', self.template_dir), \
             patch('agents.retention_engineer.DATA_DIR', self.data_dir):
            result = eng.run()
        for key in ["status", "phase", "features_enabled", "templates_written",
                     "config_path", "metrics", "reasoning"]:
            self.assertIn(key, result)


# ═══════════════════════════════════════════════════════════════════
#  ONBOARDING OPTIMIZER TESTS
# ═══════════════════════════════════════════════════════════════════

class TestOnboardingOptimizerInit(AgentTestBase):
    """Test OnboardingOptimizer initialization"""

    def _make_optimizer(self):
        from agents.onboarding_optimizer import OnboardingOptimizer
        with patch('agents.onboarding_optimizer.ENGINE_DIR', self.engine_dir), \
             patch('agents.onboarding_optimizer.APP_DIR', self.app_dir), \
             patch('agents.onboarding_optimizer.DATA_DIR', self.data_dir), \
             patch('agents.onboarding_optimizer.TEMPLATE_DIR', self.template_dir), \
             patch('agents.onboarding_optimizer.ONBOARDING_CONFIG_PATH', self.app_dir / "onboarding_config.json"), \
             patch('agents.onboarding_optimizer.LANDING_CONFIG_PATH', self.app_dir / "landing_config.json"):
            return OnboardingOptimizer()

    def test_init_no_config(self):
        opt = self._make_optimizer()
        self.assertTrue(opt.onboarding_config["tips_enabled"])

    def test_init_with_config(self):
        config = {"version": 2, "tips_enabled": False, "last_updated": "2024-01-01"}
        (self.app_dir / "onboarding_config.json").write_text(json.dumps(config))
        opt = self._make_optimizer()
        self.assertFalse(opt.onboarding_config["tips_enabled"])

    def test_init_landing_defaults(self):
        opt = self._make_optimizer()
        self.assertEqual(opt.landing_config["hero_variant"], "default")

    def test_init_with_corrupt_config(self):
        (self.app_dir / "onboarding_config.json").write_text("{bad")
        opt = self._make_optimizer()
        self.assertTrue(opt.onboarding_config["tips_enabled"])  # Falls back to defaults

    def test_init_metrics_zeroed(self):
        opt = self._make_optimizer()
        self.assertEqual(opt.metrics.overall_conversion, 0.0)


class TestOnboardingOptimizerFunnel(AgentTestBase):
    """Test OnboardingOptimizer funnel analysis"""

    def _make_optimizer(self):
        from agents.onboarding_optimizer import OnboardingOptimizer
        with patch('agents.onboarding_optimizer.ENGINE_DIR', self.engine_dir), \
             patch('agents.onboarding_optimizer.APP_DIR', self.app_dir), \
             patch('agents.onboarding_optimizer.DATA_DIR', self.data_dir), \
             patch('agents.onboarding_optimizer.TEMPLATE_DIR', self.template_dir), \
             patch('agents.onboarding_optimizer.ONBOARDING_CONFIG_PATH', self.app_dir / "onboarding_config.json"), \
             patch('agents.onboarding_optimizer.LANDING_CONFIG_PATH', self.app_dir / "landing_config.json"):
            return OnboardingOptimizer()

    def test_funnel_empty_data(self):
        opt = self._make_optimizer()
        metrics = opt.analyze_funnel()
        self.assertEqual(metrics.overall_conversion, 0.0)

    def test_funnel_full_conversion(self):
        entries = self.make_funnel_data({
            "page_load": 10, "upload_start": 10, "upload_complete": 10,
            "analyze_start": 10, "director_select": 10,
            "generate_start": 10, "generate_complete": 10, "export": 10,
        })
        self.write_jsonl(self.data_dir / "onboarding_funnel.jsonl", entries)
        opt = self._make_optimizer()
        metrics = opt.analyze_funnel()
        self.assertAlmostEqual(metrics.overall_conversion, 1.0)
        self.assertAlmostEqual(metrics.bounce_rate, 0.0)

    def test_funnel_bounce_rate(self):
        entries = self.make_funnel_data({"page_load": 100, "upload_start": 20})
        self.write_jsonl(self.data_dir / "onboarding_funnel.jsonl", entries)
        opt = self._make_optimizer()
        metrics = opt.analyze_funnel()
        self.assertAlmostEqual(metrics.bounce_rate, 0.8)

    def test_funnel_identifies_biggest_dropoff(self):
        entries = self.make_funnel_data({
            "page_load": 100, "upload_start": 80, "upload_complete": 75,
            "analyze_start": 70, "director_select": 20,  # big drop here
            "generate_start": 18, "generate_complete": 15, "export": 12,
        })
        self.write_jsonl(self.data_dir / "onboarding_funnel.jsonl", entries)
        opt = self._make_optimizer()
        metrics = opt.analyze_funnel()
        self.assertIn("director_select", metrics.biggest_dropoff)

    def test_funnel_stage_rates(self):
        entries = self.make_funnel_data({
            "page_load": 100, "upload_start": 50, "upload_complete": 50,
        })
        self.write_jsonl(self.data_dir / "onboarding_funnel.jsonl", entries)
        opt = self._make_optimizer()
        metrics = opt.analyze_funnel()
        self.assertAlmostEqual(metrics.stage_rates["page_load→upload_start"], 0.5)
        self.assertAlmostEqual(metrics.stage_rates["upload_start→upload_complete"], 1.0)

    def test_funnel_malformed_data(self):
        with open(self.data_dir / "onboarding_funnel.jsonl", "w") as f:
            f.write('{"event":"page_load"}\n')
            f.write('GARBAGE\n')
            f.write('{"event":"upload_start"}\n')
        opt = self._make_optimizer()
        metrics = opt.analyze_funnel()
        self.assertEqual(metrics.stage_counts["page_load"], 1)
        self.assertEqual(metrics.stage_counts["upload_start"], 1)

    def test_funnel_demo_conversion(self):
        entries = [
            {"event": "page_load", "data": {"mode": "demo"}},
            {"event": "page_load", "data": {"mode": "demo"}},
            {"event": "upload_start", "data": {"from_demo": True}},
        ]
        self.write_jsonl(self.data_dir / "onboarding_funnel.jsonl", entries)
        opt = self._make_optimizer()
        metrics = opt.analyze_funnel()
        self.assertAlmostEqual(metrics.demo_conversion, 0.5)

    def test_funnel_mobile_ratio(self):
        desktop = self.make_funnel_data({"page_load": 70})
        mobile = self.make_mobile_funnel_data({"page_load": 30})
        self.write_jsonl(self.data_dir / "onboarding_funnel.jsonl", desktop + mobile)
        opt = self._make_optimizer()
        metrics = opt.analyze_funnel()
        self.assertAlmostEqual(metrics.mobile_ratio, 0.3, places=1)

    def test_funnel_mobile_bounce(self):
        mobile = self.make_mobile_funnel_data({"page_load": 100, "upload_start": 20})
        self.write_jsonl(self.data_dir / "onboarding_funnel.jsonl", mobile)
        opt = self._make_optimizer()
        metrics = opt.analyze_funnel()
        self.assertAlmostEqual(metrics.mobile_bounce_rate, 0.8)

    def test_funnel_mobile_conversion(self):
        mobile = self.make_mobile_funnel_data({"page_load": 100, "export": 5})
        self.write_jsonl(self.data_dir / "onboarding_funnel.jsonl", mobile)
        opt = self._make_optimizer()
        metrics = opt.analyze_funnel()
        self.assertAlmostEqual(metrics.mobile_conversion, 0.05)


class TestOnboardingOptimizerOptimize(AgentTestBase):
    """Test OnboardingOptimizer.optimize()"""

    def _make_optimizer(self):
        from agents.onboarding_optimizer import OnboardingOptimizer
        with patch('agents.onboarding_optimizer.ENGINE_DIR', self.engine_dir), \
             patch('agents.onboarding_optimizer.APP_DIR', self.app_dir), \
             patch('agents.onboarding_optimizer.DATA_DIR', self.data_dir), \
             patch('agents.onboarding_optimizer.TEMPLATE_DIR', self.template_dir), \
             patch('agents.onboarding_optimizer.ONBOARDING_CONFIG_PATH', self.app_dir / "onboarding_config.json"), \
             patch('agents.onboarding_optimizer.LANDING_CONFIG_PATH', self.app_dir / "landing_config.json"):
            return OnboardingOptimizer()

    def test_optimize_returns_decision(self):
        opt = self._make_optimizer()
        decision = opt.optimize()
        self.assertIsNotNone(decision)
        self.assertTrue(len(decision.timestamp) > 0)

    def test_optimize_identifies_bottleneck(self):
        entries = self.make_funnel_data({
            "page_load": 100, "upload_start": 10,
        })
        self.write_jsonl(self.data_dir / "onboarding_funnel.jsonl", entries)
        opt = self._make_optimizer()
        decision = opt.optimize()
        self.assertIn("page_load", decision.bottleneck)

    def test_optimize_high_bounce_forces_demo(self):
        entries = self.make_funnel_data({"page_load": 100, "upload_start": 10})
        self.write_jsonl(self.data_dir / "onboarding_funnel.jsonl", entries)
        opt = self._make_optimizer()
        decision = opt.optimize()
        self.assertTrue(
            decision.config_changes.get("demo_mode_enabled", False) or
            decision.landing_changes.get("show_demo_reel", False)
        )

    def test_optimize_has_reasoning(self):
        opt = self._make_optimizer()
        decision = opt.optimize()
        self.assertIn("Bottleneck", decision.reasoning)

    def test_optimize_has_config_changes(self):
        entries = self.make_funnel_data({
            "page_load": 100, "upload_start": 10,
        })
        self.write_jsonl(self.data_dir / "onboarding_funnel.jsonl", entries)
        opt = self._make_optimizer()
        decision = opt.optimize()
        self.assertTrue(
            len(decision.config_changes) > 0 or len(decision.landing_changes) > 0
        )

    def test_optimize_director_paralysis(self):
        entries = self.make_funnel_data({
            "page_load": 100, "upload_start": 90, "upload_complete": 85,
            "analyze_start": 80, "director_select": 20,
        })
        self.write_jsonl(self.data_dir / "onboarding_funnel.jsonl", entries)
        opt = self._make_optimizer()
        decision = opt.optimize()
        self.assertIn("director", decision.bottleneck.lower())

    def test_optimize_export_friction(self):
        entries = self.make_funnel_data({
            "page_load": 100, "upload_start": 95, "upload_complete": 90,
            "analyze_start": 85, "director_select": 80,
            "generate_start": 75, "generate_complete": 70, "export": 10,
        })
        self.write_jsonl(self.data_dir / "onboarding_funnel.jsonl", entries)
        opt = self._make_optimizer()
        decision = opt.optimize()
        self.assertIn("export", decision.bottleneck.lower())

    def test_optimize_mobile_changes(self):
        # High mobile bounce rate should trigger mobile optimizations
        mobile = self.make_mobile_funnel_data({"page_load": 100, "upload_start": 10})
        desktop = self.make_funnel_data({"page_load": 50, "upload_start": 40})
        self.write_jsonl(self.data_dir / "onboarding_funnel.jsonl", desktop + mobile)
        opt = self._make_optimizer()
        decision = opt.optimize()
        # If mobile ratio > 30% and bounce > 60%, mobile changes should be present
        mobile_changes = decision.config_changes.get("mobile", {})
        if opt.metrics.mobile_ratio > 0.3 and opt.metrics.mobile_bounce_rate > 0.6:
            self.assertTrue(len(mobile_changes) > 0)


class TestOnboardingOptimizerConfig(AgentTestBase):
    """Test OnboardingOptimizer config writing"""

    def _make_optimizer(self):
        from agents.onboarding_optimizer import OnboardingOptimizer
        with patch('agents.onboarding_optimizer.ENGINE_DIR', self.engine_dir), \
             patch('agents.onboarding_optimizer.APP_DIR', self.app_dir), \
             patch('agents.onboarding_optimizer.DATA_DIR', self.data_dir), \
             patch('agents.onboarding_optimizer.TEMPLATE_DIR', self.template_dir), \
             patch('agents.onboarding_optimizer.ONBOARDING_CONFIG_PATH', self.app_dir / "onboarding_config.json"), \
             patch('agents.onboarding_optimizer.LANDING_CONFIG_PATH', self.app_dir / "landing_config.json"):
            return OnboardingOptimizer()

    def test_write_configs_creates_files(self):
        opt = self._make_optimizer()
        decision = opt.optimize()
        with patch('agents.onboarding_optimizer.ONBOARDING_CONFIG_PATH', self.app_dir / "onboarding_config.json"), \
             patch('agents.onboarding_optimizer.LANDING_CONFIG_PATH', self.app_dir / "landing_config.json"):
            paths = opt.write_configs(decision)
        self.assertEqual(len(paths), 2)
        self.assertTrue((self.app_dir / "onboarding_config.json").exists())
        self.assertTrue((self.app_dir / "landing_config.json").exists())

    def test_write_configs_valid_json(self):
        opt = self._make_optimizer()
        decision = opt.optimize()
        with patch('agents.onboarding_optimizer.ONBOARDING_CONFIG_PATH', self.app_dir / "onboarding_config.json"), \
             patch('agents.onboarding_optimizer.LANDING_CONFIG_PATH', self.app_dir / "landing_config.json"):
            opt.write_configs(decision)
        json.loads((self.app_dir / "onboarding_config.json").read_text())
        json.loads((self.app_dir / "landing_config.json").read_text())

    def test_write_configs_updates_timestamp(self):
        opt = self._make_optimizer()
        decision = opt.optimize()
        with patch('agents.onboarding_optimizer.ONBOARDING_CONFIG_PATH', self.app_dir / "onboarding_config.json"), \
             patch('agents.onboarding_optimizer.LANDING_CONFIG_PATH', self.app_dir / "landing_config.json"):
            opt.write_configs(decision)
        data = json.loads((self.app_dir / "onboarding_config.json").read_text())
        self.assertTrue(len(data["last_updated"]) > 0)

    def test_write_configs_ab_test_id(self):
        opt = self._make_optimizer()
        decision = opt.optimize()
        with patch('agents.onboarding_optimizer.ONBOARDING_CONFIG_PATH', self.app_dir / "onboarding_config.json"), \
             patch('agents.onboarding_optimizer.LANDING_CONFIG_PATH', self.app_dir / "landing_config.json"):
            opt.write_configs(decision)
        data = json.loads((self.app_dir / "landing_config.json").read_text())
        self.assertTrue(data["ab_test_id"].startswith("ab_"))

    def test_write_configs_applies_changes(self):
        entries = self.make_funnel_data({"page_load": 100, "upload_start": 10})
        self.write_jsonl(self.data_dir / "onboarding_funnel.jsonl", entries)
        opt = self._make_optimizer()
        decision = opt.optimize()
        with patch('agents.onboarding_optimizer.ONBOARDING_CONFIG_PATH', self.app_dir / "onboarding_config.json"), \
             patch('agents.onboarding_optimizer.LANDING_CONFIG_PATH', self.app_dir / "landing_config.json"):
            opt.write_configs(decision)
        data = json.loads((self.app_dir / "onboarding_config.json").read_text())
        self.assertEqual(data["last_bottleneck"], decision.bottleneck)


class TestOnboardingOptimizerTemplates(AgentTestBase):
    """Test OnboardingOptimizer template writing"""

    def _make_optimizer(self):
        from agents.onboarding_optimizer import OnboardingOptimizer
        with patch('agents.onboarding_optimizer.ENGINE_DIR', self.engine_dir), \
             patch('agents.onboarding_optimizer.APP_DIR', self.app_dir), \
             patch('agents.onboarding_optimizer.DATA_DIR', self.data_dir), \
             patch('agents.onboarding_optimizer.TEMPLATE_DIR', self.template_dir), \
             patch('agents.onboarding_optimizer.ONBOARDING_CONFIG_PATH', self.app_dir / "onboarding_config.json"), \
             patch('agents.onboarding_optimizer.LANDING_CONFIG_PATH', self.app_dir / "landing_config.json"):
            return OnboardingOptimizer()

    def test_write_templates_creates_files(self):
        opt = self._make_optimizer()
        with patch('agents.onboarding_optimizer.TEMPLATE_DIR', self.template_dir):
            paths = opt.write_templates()
        self.assertEqual(len(paths), 2)
        self.assertTrue((self.template_dir / "onboarding_tips.html").exists())
        self.assertTrue((self.template_dir / "landing_hero_variant.html").exists())

    def test_templates_contain_html(self):
        opt = self._make_optimizer()
        with patch('agents.onboarding_optimizer.TEMPLATE_DIR', self.template_dir):
            opt.write_templates()
        content = (self.template_dir / "onboarding_tips.html").read_text()
        self.assertIn("<div", content)
        self.assertIn("tip", content.lower())

    def test_templates_contain_scripts(self):
        opt = self._make_optimizer()
        with patch('agents.onboarding_optimizer.TEMPLATE_DIR', self.template_dir):
            opt.write_templates()
        content = (self.template_dir / "onboarding_tips.html").read_text()
        self.assertIn("<script>", content)

    def test_hero_template_has_variants(self):
        opt = self._make_optimizer()
        with patch('agents.onboarding_optimizer.TEMPLATE_DIR', self.template_dir):
            opt.write_templates()
        content = (self.template_dir / "landing_hero_variant.html").read_text()
        self.assertIn("hero", content.lower())

    def test_templates_use_inter_font(self):
        opt = self._make_optimizer()
        with patch('agents.onboarding_optimizer.TEMPLATE_DIR', self.template_dir):
            opt.write_templates()
        content = (self.template_dir / "onboarding_tips.html").read_text()
        self.assertIn("Inter", content)


class TestOnboardingOptimizerRun(AgentTestBase):
    """Test OnboardingOptimizer.run() full cycle"""

    def _make_optimizer(self):
        from agents.onboarding_optimizer import OnboardingOptimizer
        with patch('agents.onboarding_optimizer.ENGINE_DIR', self.engine_dir), \
             patch('agents.onboarding_optimizer.APP_DIR', self.app_dir), \
             patch('agents.onboarding_optimizer.DATA_DIR', self.data_dir), \
             patch('agents.onboarding_optimizer.TEMPLATE_DIR', self.template_dir), \
             patch('agents.onboarding_optimizer.ONBOARDING_CONFIG_PATH', self.app_dir / "onboarding_config.json"), \
             patch('agents.onboarding_optimizer.LANDING_CONFIG_PATH', self.app_dir / "landing_config.json"):
            return OnboardingOptimizer()

    def test_run_returns_success(self):
        opt = self._make_optimizer()
        with patch('agents.onboarding_optimizer.ONBOARDING_CONFIG_PATH', self.app_dir / "onboarding_config.json"), \
             patch('agents.onboarding_optimizer.LANDING_CONFIG_PATH', self.app_dir / "landing_config.json"), \
             patch('agents.onboarding_optimizer.TEMPLATE_DIR', self.template_dir), \
             patch('agents.onboarding_optimizer.DATA_DIR', self.data_dir):
            result = opt.run()
        self.assertEqual(result["status"], "success")

    def test_run_creates_all_outputs(self):
        opt = self._make_optimizer()
        with patch('agents.onboarding_optimizer.ONBOARDING_CONFIG_PATH', self.app_dir / "onboarding_config.json"), \
             patch('agents.onboarding_optimizer.LANDING_CONFIG_PATH', self.app_dir / "landing_config.json"), \
             patch('agents.onboarding_optimizer.TEMPLATE_DIR', self.template_dir), \
             patch('agents.onboarding_optimizer.DATA_DIR', self.data_dir):
            opt.run()
        self.assertTrue((self.app_dir / "onboarding_config.json").exists())
        self.assertTrue((self.app_dir / "landing_config.json").exists())

    def test_run_logs_decision(self):
        opt = self._make_optimizer()
        with patch('agents.onboarding_optimizer.ONBOARDING_CONFIG_PATH', self.app_dir / "onboarding_config.json"), \
             patch('agents.onboarding_optimizer.LANDING_CONFIG_PATH', self.app_dir / "landing_config.json"), \
             patch('agents.onboarding_optimizer.TEMPLATE_DIR', self.template_dir), \
             patch('agents.onboarding_optimizer.DATA_DIR', self.data_dir):
            opt.run()
        self.assertTrue((self.data_dir / "onboarding_decisions.jsonl").exists())

    def test_run_result_fields(self):
        opt = self._make_optimizer()
        with patch('agents.onboarding_optimizer.ONBOARDING_CONFIG_PATH', self.app_dir / "onboarding_config.json"), \
             patch('agents.onboarding_optimizer.LANDING_CONFIG_PATH', self.app_dir / "landing_config.json"), \
             patch('agents.onboarding_optimizer.TEMPLATE_DIR', self.template_dir), \
             patch('agents.onboarding_optimizer.DATA_DIR', self.data_dir):
            result = opt.run()
        for key in ["status", "bottleneck", "action", "configs_written",
                     "templates_written", "changes", "metrics", "reasoning"]:
            self.assertIn(key, result)

    def test_run_with_data(self):
        entries = self.make_funnel_data({
            "page_load": 100, "upload_start": 50, "upload_complete": 45,
            "analyze_start": 40, "director_select": 35,
            "generate_start": 30, "generate_complete": 25, "export": 20,
        })
        self.write_jsonl(self.data_dir / "onboarding_funnel.jsonl", entries)
        opt = self._make_optimizer()
        with patch('agents.onboarding_optimizer.ONBOARDING_CONFIG_PATH', self.app_dir / "onboarding_config.json"), \
             patch('agents.onboarding_optimizer.LANDING_CONFIG_PATH', self.app_dir / "landing_config.json"), \
             patch('agents.onboarding_optimizer.TEMPLATE_DIR', self.template_dir), \
             patch('agents.onboarding_optimizer.DATA_DIR', self.data_dir):
            result = opt.run()
        self.assertEqual(result["status"], "success")
        self.assertTrue(len(result["bottleneck"]) > 0)


# ═══════════════════════════════════════════════════════════════════
#  GROWTH ENGINEER TESTS
# ═══════════════════════════════════════════════════════════════════

class TestGrowthEngineerInit(AgentTestBase):
    """Test GrowthEngineer initialization"""

    def _make_engineer(self):
        from agents.growth_engineer import GrowthEngineer
        with patch('agents.growth_engineer.ENGINE_DIR', self.engine_dir), \
             patch('agents.growth_engineer.APP_DIR', self.app_dir), \
             patch('agents.growth_engineer.DATA_DIR', self.data_dir), \
             patch('agents.growth_engineer.OPT_DIR', self.opt_dir), \
             patch('agents.growth_engineer.TEMPLATE_DIR', self.template_dir), \
             patch('agents.growth_engineer.CONFIG_PATH', self.app_dir / "growth_config.json"):
            return GrowthEngineer()

    def test_init_no_config(self):
        eng = self._make_engineer()
        self.assertEqual(eng.current_config["phase"], 1)

    def test_init_with_config(self):
        config = {"version": 2, "phase": 3, "features": {}}
        (self.app_dir / "growth_config.json").write_text(json.dumps(config))
        eng = self._make_engineer()
        self.assertEqual(eng.current_config["phase"], 3)

    def test_init_with_corrupt_config(self):
        (self.app_dir / "growth_config.json").write_text("broken{{{")
        eng = self._make_engineer()
        self.assertEqual(eng.current_config["phase"], 1)

    def test_init_default_features(self):
        eng = self._make_engineer()
        self.assertTrue(eng.current_config["features"]["copy_link"]["enabled"])
        self.assertFalse(eng.current_config["features"]["platform_sharing"]["enabled"])

    def test_init_metrics_zeroed(self):
        eng = self._make_engineer()
        self.assertEqual(eng.metrics.k_factor, 0.0)


class TestGrowthEngineerAnalyze(AgentTestBase):
    """Test GrowthEngineer.analyze()"""

    def _make_engineer(self):
        from agents.growth_engineer import GrowthEngineer
        with patch('agents.growth_engineer.ENGINE_DIR', self.engine_dir), \
             patch('agents.growth_engineer.APP_DIR', self.app_dir), \
             patch('agents.growth_engineer.DATA_DIR', self.data_dir), \
             patch('agents.growth_engineer.OPT_DIR', self.opt_dir), \
             patch('agents.growth_engineer.TEMPLATE_DIR', self.template_dir), \
             patch('agents.growth_engineer.CONFIG_PATH', self.app_dir / "growth_config.json"):
            return GrowthEngineer()

    def test_analyze_empty_data(self):
        eng = self._make_engineer()
        metrics = eng.analyze()
        self.assertEqual(metrics.k_factor, 0.0)
        self.assertEqual(metrics.total_shares, 0)

    def test_analyze_share_count(self):
        self.write_jsonl(self.data_dir / "onboarding_funnel.jsonl", [
            {"event": "share", "data": {"platform": "twitter"}},
            {"event": "share", "data": {"platform": "copy"}},
            {"event": "share", "data": {"platform": "twitter"}},
        ])
        eng = self._make_engineer()
        metrics = eng.analyze()
        self.assertEqual(metrics.total_shares, 3)

    def test_analyze_shares_by_platform(self):
        self.write_jsonl(self.data_dir / "onboarding_funnel.jsonl", [
            {"event": "share", "data": {"platform": "twitter"}},
            {"event": "share", "data": {"platform": "twitter"}},
            {"event": "share", "data": {"platform": "copy"}},
        ])
        eng = self._make_engineer()
        metrics = eng.analyze()
        self.assertEqual(metrics.shares_by_platform.get("twitter", 0), 2)
        self.assertEqual(metrics.shares_by_platform.get("copy", 0), 1)

    def test_analyze_share_rate(self):
        self.write_jsonl(self.data_dir / "onboarding_funnel.jsonl", [
            {"event": "generate_complete"}, {"event": "generate_complete"},
            {"event": "share", "data": {"platform": "copy"}},
        ])
        eng = self._make_engineer()
        metrics = eng.analyze()
        self.assertAlmostEqual(metrics.share_rate, 0.5)

    def test_analyze_export_count(self):
        self.write_jsonl(self.data_dir / "onboarding_funnel.jsonl", [
            {"event": "export"}, {"event": "export"}, {"event": "export"},
        ])
        eng = self._make_engineer()
        metrics = eng.analyze()
        self.assertEqual(metrics.total_exports, 3)

    def test_analyze_k_factor_zero(self):
        self.write_jsonl(self.data_dir / "user_activity.jsonl", [
            {"session_id": "a"}, {"session_id": "b"},
        ])
        eng = self._make_engineer()
        metrics = eng.analyze()
        self.assertEqual(metrics.k_factor, 0.0)

    def test_analyze_referral_claims(self):
        self.write_jsonl(self.data_dir / "onboarding_funnel.jsonl", [
            {"event": "share", "data": {"type": "referral_bonus_claimed"}},
            {"event": "share", "data": {"type": "referral_bonus_claimed"}},
        ])
        eng = self._make_engineer()
        metrics = eng.analyze()
        self.assertEqual(metrics.referral_bonus_claims, 2)

    def test_analyze_malformed_data(self):
        with open(self.data_dir / "onboarding_funnel.jsonl", "w") as f:
            f.write('{"event":"share","data":{"platform":"x"}}\n')
            f.write('BAD LINE\n')
            f.write('{"event":"share","data":{"platform":"y"}}\n')
        eng = self._make_engineer()
        metrics = eng.analyze()
        self.assertEqual(metrics.total_shares, 2)


class TestGrowthEngineerDecide(AgentTestBase):
    """Test GrowthEngineer.decide()"""

    def _make_engineer(self):
        from agents.growth_engineer import GrowthEngineer
        with patch('agents.growth_engineer.ENGINE_DIR', self.engine_dir), \
             patch('agents.growth_engineer.APP_DIR', self.app_dir), \
             patch('agents.growth_engineer.DATA_DIR', self.data_dir), \
             patch('agents.growth_engineer.OPT_DIR', self.opt_dir), \
             patch('agents.growth_engineer.TEMPLATE_DIR', self.template_dir), \
             patch('agents.growth_engineer.CONFIG_PATH', self.app_dir / "growth_config.json"):
            return GrowthEngineer()

    def test_decide_phase1_default(self):
        eng = self._make_engineer()
        eng.analyze()
        decision = eng.decide()
        self.assertEqual(decision.phase, 1)
        self.assertIn("copy_link", decision.features_enabled)

    def test_decide_phase2(self):
        eng = self._make_engineer()
        eng.analyze()
        eng.metrics.k_factor = 0.15
        decision = eng.decide()
        self.assertEqual(decision.phase, 2)
        self.assertIn("platform_sharing", decision.features_enabled)
        self.assertIn("referral_bonus", decision.features_enabled)

    def test_decide_phase3(self):
        eng = self._make_engineer()
        eng.analyze()
        eng.metrics.k_factor = 0.35
        decision = eng.decide()
        self.assertEqual(decision.phase, 3)
        self.assertIn("real_social_proof", decision.features_enabled)

    def test_decide_phase4(self):
        eng = self._make_engineer()
        eng.analyze()
        eng.metrics.k_factor = 0.55
        decision = eng.decide()
        self.assertEqual(decision.phase, 4)
        self.assertIn("public_gallery", decision.features_enabled)

    def test_decide_no_regress(self):
        config = {"version": 1, "phase": 4, "features": {
            "copy_link": {"enabled": True}, "platform_sharing": {"enabled": True, "platforms": []},
            "referral_bonus": {"enabled": True, "shares_required": 3, "bonus_exports": 3},
            "real_social_proof": {"enabled": True, "stats": {}},
            "watermark": {"enabled": True, "text": "", "opacity": 0.15, "position": "bottom-right"},
            "public_gallery": {"enabled": True, "max_items": 50, "sort": "recent"},
        }, "share_copy": {}, "og_tags": {}, "last_updated": "", "last_decision": ""}
        (self.app_dir / "growth_config.json").write_text(json.dumps(config))
        eng = self._make_engineer()
        eng.analyze()
        decision = eng.decide()
        self.assertGreaterEqual(decision.phase, 3)

    def test_decide_has_social_proof(self):
        eng = self._make_engineer()
        eng.analyze()
        decision = eng.decide()
        self.assertIn("canvases_generated", decision.social_proof_update)

    def test_decide_has_reasoning(self):
        eng = self._make_engineer()
        eng.analyze()
        decision = eng.decide()
        self.assertIn("K-factor", decision.reasoning)

    def test_decide_has_timestamp(self):
        eng = self._make_engineer()
        eng.analyze()
        decision = eng.decide()
        self.assertTrue(decision.timestamp.endswith("Z"))


class TestGrowthEngineerConfig(AgentTestBase):
    """Test GrowthEngineer config writing"""

    def _make_engineer(self):
        from agents.growth_engineer import GrowthEngineer
        with patch('agents.growth_engineer.ENGINE_DIR', self.engine_dir), \
             patch('agents.growth_engineer.APP_DIR', self.app_dir), \
             patch('agents.growth_engineer.DATA_DIR', self.data_dir), \
             patch('agents.growth_engineer.OPT_DIR', self.opt_dir), \
             patch('agents.growth_engineer.TEMPLATE_DIR', self.template_dir), \
             patch('agents.growth_engineer.CONFIG_PATH', self.app_dir / "growth_config.json"):
            return GrowthEngineer()

    def test_write_config_creates_file(self):
        eng = self._make_engineer()
        eng.analyze()
        decision = eng.decide()
        with patch('agents.growth_engineer.CONFIG_PATH', self.app_dir / "growth_config.json"):
            eng.write_config(decision)
        self.assertTrue((self.app_dir / "growth_config.json").exists())

    def test_write_config_valid_json(self):
        eng = self._make_engineer()
        eng.analyze()
        decision = eng.decide()
        with patch('agents.growth_engineer.CONFIG_PATH', self.app_dir / "growth_config.json"):
            eng.write_config(decision)
        data = json.loads((self.app_dir / "growth_config.json").read_text())
        self.assertIn("features", data)

    def test_write_config_updates_phase(self):
        eng = self._make_engineer()
        eng.analyze()
        eng.metrics.k_factor = 0.15
        decision = eng.decide()
        with patch('agents.growth_engineer.CONFIG_PATH', self.app_dir / "growth_config.json"):
            eng.write_config(decision)
        data = json.loads((self.app_dir / "growth_config.json").read_text())
        self.assertEqual(data["phase"], 2)

    def test_write_config_social_proof_stats(self):
        eng = self._make_engineer()
        eng.analyze()
        decision = eng.decide()
        decision.social_proof_update = {"canvases_generated": 42, "artists_served": 10, "exports_total": 25}
        with patch('agents.growth_engineer.CONFIG_PATH', self.app_dir / "growth_config.json"):
            eng.write_config(decision)
        data = json.loads((self.app_dir / "growth_config.json").read_text())
        self.assertEqual(data["features"]["real_social_proof"]["stats"]["canvases_generated"], 42)

    def test_write_config_share_copy_phase2(self):
        eng = self._make_engineer()
        eng.analyze()
        eng.metrics.k_factor = 0.15
        decision = eng.decide()
        with patch('agents.growth_engineer.CONFIG_PATH', self.app_dir / "growth_config.json"):
            eng.write_config(decision)
        data = json.loads((self.app_dir / "growth_config.json").read_text())
        self.assertIn("Share", data["share_copy"]["referral_prompt"])


class TestGrowthEngineerTemplates(AgentTestBase):
    """Test GrowthEngineer template writing"""

    def _make_engineer(self):
        from agents.growth_engineer import GrowthEngineer
        with patch('agents.growth_engineer.ENGINE_DIR', self.engine_dir), \
             patch('agents.growth_engineer.APP_DIR', self.app_dir), \
             patch('agents.growth_engineer.DATA_DIR', self.data_dir), \
             patch('agents.growth_engineer.OPT_DIR', self.opt_dir), \
             patch('agents.growth_engineer.TEMPLATE_DIR', self.template_dir), \
             patch('agents.growth_engineer.CONFIG_PATH', self.app_dir / "growth_config.json"):
            return GrowthEngineer()

    def test_write_templates_creates_file(self):
        eng = self._make_engineer()
        eng.analyze()
        decision = eng.decide()
        with patch('agents.growth_engineer.TEMPLATE_DIR', self.template_dir):
            paths = eng.write_templates(decision)
        self.assertEqual(len(paths), 1)
        self.assertTrue((self.template_dir / "growth_share.html").exists())

    def test_template_contains_share_html(self):
        eng = self._make_engineer()
        eng.analyze()
        decision = eng.decide()
        with patch('agents.growth_engineer.TEMPLATE_DIR', self.template_dir):
            eng.write_templates(decision)
        content = (self.template_dir / "growth_share.html").read_text()
        self.assertIn("share", content.lower())
        self.assertIn("<script>", content)

    def test_template_has_platform_buttons(self):
        eng = self._make_engineer()
        eng.analyze()
        decision = eng.decide()
        with patch('agents.growth_engineer.TEMPLATE_DIR', self.template_dir):
            eng.write_templates(decision)
        content = (self.template_dir / "growth_share.html").read_text()
        self.assertIn("twitter", content.lower())


class TestGrowthEngineerRun(AgentTestBase):
    """Test GrowthEngineer.run() full cycle"""

    def _make_engineer(self):
        from agents.growth_engineer import GrowthEngineer
        with patch('agents.growth_engineer.ENGINE_DIR', self.engine_dir), \
             patch('agents.growth_engineer.APP_DIR', self.app_dir), \
             patch('agents.growth_engineer.DATA_DIR', self.data_dir), \
             patch('agents.growth_engineer.OPT_DIR', self.opt_dir), \
             patch('agents.growth_engineer.TEMPLATE_DIR', self.template_dir), \
             patch('agents.growth_engineer.CONFIG_PATH', self.app_dir / "growth_config.json"):
            return GrowthEngineer()

    def test_run_returns_success(self):
        eng = self._make_engineer()
        with patch('agents.growth_engineer.CONFIG_PATH', self.app_dir / "growth_config.json"), \
             patch('agents.growth_engineer.TEMPLATE_DIR', self.template_dir), \
             patch('agents.growth_engineer.DATA_DIR', self.data_dir):
            result = eng.run()
        self.assertEqual(result["status"], "success")

    def test_run_creates_config(self):
        eng = self._make_engineer()
        with patch('agents.growth_engineer.CONFIG_PATH', self.app_dir / "growth_config.json"), \
             patch('agents.growth_engineer.TEMPLATE_DIR', self.template_dir), \
             patch('agents.growth_engineer.DATA_DIR', self.data_dir):
            eng.run()
        self.assertTrue((self.app_dir / "growth_config.json").exists())

    def test_run_creates_template(self):
        eng = self._make_engineer()
        with patch('agents.growth_engineer.CONFIG_PATH', self.app_dir / "growth_config.json"), \
             patch('agents.growth_engineer.TEMPLATE_DIR', self.template_dir), \
             patch('agents.growth_engineer.DATA_DIR', self.data_dir):
            eng.run()
        self.assertTrue((self.template_dir / "growth_share.html").exists())

    def test_run_logs_decision(self):
        eng = self._make_engineer()
        with patch('agents.growth_engineer.CONFIG_PATH', self.app_dir / "growth_config.json"), \
             patch('agents.growth_engineer.TEMPLATE_DIR', self.template_dir), \
             patch('agents.growth_engineer.DATA_DIR', self.data_dir):
            eng.run()
        self.assertTrue((self.data_dir / "growth_decisions.jsonl").exists())

    def test_run_result_fields(self):
        eng = self._make_engineer()
        with patch('agents.growth_engineer.CONFIG_PATH', self.app_dir / "growth_config.json"), \
             patch('agents.growth_engineer.TEMPLATE_DIR', self.template_dir), \
             patch('agents.growth_engineer.DATA_DIR', self.data_dir):
            result = eng.run()
        for key in ["status", "phase", "k_factor", "features_enabled",
                     "social_proof", "templates_written", "config_path",
                     "metrics", "reasoning"]:
            self.assertIn(key, result)


if __name__ == "__main__":
    unittest.main()
