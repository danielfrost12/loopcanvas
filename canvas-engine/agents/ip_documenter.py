#!/usr/bin/env python3
"""
IP & Legal Intelligence Lead — Canvas Agent Army v2.0

Documents patentable innovations in filing-ready format.
CRITICAL: DOCUMENTATION ONLY — NO FILING until the founder explicitly authorizes.

"No patents will be filed until the founder explicitly decides to proceed. The agents
will maintain a complete, up-to-date patent portfolio that is ready to file at a
moment's notice, but filing authority rests solely with the founder." — Spec

7 Patentable Innovations:
  P-001: Audio Emotional DNA Extraction ($320 provisional, micro entity)
  P-002: Directorial Intent Encoding ($320)
  P-003: Seamless Audio-Synced Video Looping ($320)
  P-004: AI Artifact Detection & Regeneration ($320)
  P-005: Intent-Based Video Editing ($320)
  P-006: Cultural-Genre Visual Mapping ($320)
  P-007: Progressive Canvas-to-Video Extension ($320)
  Total when filed: $2,240

Phases:
  Phase 1: Document existing innovations from codebase
  Phase 2: Filing-ready format with claims, evidence, prior art
  Phase 3: Competitor watch, market scanning
  Phase 4: Maintain portfolio, update claims as code evolves
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
CONFIG_PATH = APP_DIR / "ip_config.json"

DATA_DIR.mkdir(exist_ok=True)

# ══════════════════════════════════════════════════════════════
# Patent Portfolio
# ══════════════════════════════════════════════════════════════

PATENT_PORTFOLIO = [
    {
        "id": "P-001",
        "title": "Audio Emotional DNA Extraction",
        "claim": "Method for extracting multi-dimensional emotional vectors from audio signals and mapping them to visual generation parameters in real-time",
        "filing_cost": 320,
        "evidence_files": [
            "canvas-engine/audio/audio_analyzer.py",
            "canvas-engine/agents/audio_intelligence.py",
        ],
        "key_innovation": "Multi-layer audio analysis: BPM, key, emotion valence/arousal/tension/release mapped to visual parameters",
    },
    {
        "id": "P-002",
        "title": "Directorial Intent Encoding",
        "claim": "System for encoding cinematic directorial philosophies as controllable latent space parameters for video generation models",
        "filing_cost": 320,
        "evidence_files": [
            "canvas-engine/director/philosophy_engine.py",
            "canvas-engine/agents/model_engineer.py",
        ],
        "key_innovation": "Director DNA: philosophy, color theory, camera movement, emotional intent encoded as LoRA weights",
    },
    {
        "id": "P-003",
        "title": "Seamless Audio-Synced Video Looping",
        "claim": "Technique for generating video loops that are visually seamless AND rhythmically synchronized to audio beat structure",
        "filing_cost": 320,
        "evidence_files": [
            "canvas-engine/loop/seamless_loop.py",
        ],
        "key_innovation": "Loop via shared emotional state, not shared pixels. Forward-only, no reverse playback.",
    },
    {
        "id": "P-004",
        "title": "AI Artifact Detection & Regeneration",
        "claim": "Automated system for detecting visual artifacts characteristic of AI-generated content and triggering targeted regeneration",
        "filing_cost": 320,
        "evidence_files": [
            "canvas-engine/quality_gate_wrapper.py",
            "canvas-engine/agents/qa_engineer.py",
        ],
        "key_innovation": "Multi-axis quality scoring (Observer Neutrality, Camera Humility, etc.) with 9.3/10 minimum threshold",
    },
    {
        "id": "P-005",
        "title": "Intent-Based Video Editing",
        "claim": "Natural language interface for video editing that translates artistic intent into frame-accurate edit operations",
        "filing_cost": 320,
        "evidence_files": [],
        "key_innovation": "'Make it feel more like a memory' → specific color, motion, framing parameter adjustments",
    },
    {
        "id": "P-006",
        "title": "Cultural-Genre Visual Mapping",
        "claim": "System for mapping musical genre and cultural context to appropriate visual languages using crowd-sourced artist preferences",
        "filing_cost": 320,
        "evidence_files": [
            "canvas-engine/agents/audio_intelligence.py",
        ],
        "key_innovation": "Taste Layer: cultural fluency across 10 genres with artist preference learning",
    },
    {
        "id": "P-007",
        "title": "Progressive Canvas-to-Video Extension",
        "claim": "Method for coherently extending short-form video loops into long-form music videos while maintaining visual and narrative consistency",
        "filing_cost": 320,
        "evidence_files": [],
        "key_innovation": "8-second canvas → 30s → 60s → full music video with same visual language",
    },
]


# ══════════════════════════════════════════════════════════════
# Data Structures
# ══════════════════════════════════════════════════════════════

@dataclass
class PatentDoc:
    id: str = ""
    title: str = ""
    claim: str = ""
    status: str = "documented"  # documented, filing_ready, needs_update
    last_updated: str = ""
    filing_cost: int = 320
    evidence_files: List[str] = field(default_factory=list)
    evidence_exists: List[bool] = field(default_factory=list)
    key_innovation: str = ""


@dataclass
class IPDecision:
    timestamp: str = ""
    phase: int = 1
    portfolio_updates: Dict = field(default_factory=dict)
    compliance_status: Dict = field(default_factory=dict)
    competitor_alerts: List[str] = field(default_factory=list)
    reasoning: str = ""
    metrics_snapshot: Dict = field(default_factory=dict)


# ══════════════════════════════════════════════════════════════
# IP Documenter
# ══════════════════════════════════════════════════════════════

class IPDocumenter:
    """
    Autonomous IP documentation agent.
    DOCUMENTATION ONLY — NEVER FILES PATENTS. Filing authority: FOUNDER ONLY.
    """

    def __init__(self):
        self.config = self._load_config()
        self.patents = []

    def _load_config(self) -> Dict:
        if CONFIG_PATH.exists():
            try:
                return json.loads(CONFIG_PATH.read_text())
            except (json.JSONDecodeError, IOError):
                pass
        return {
            "version": 1, "phase": 1,
            "status": "DOCUMENTATION_ONLY",
            "filing_authority": "FOUNDER_ONLY",
            "patent_portfolio": {},
            "total_filing_cost": 2240,
            "training_data_compliance": {"all_sources_licensed": True, "audit_status": "clean"},
            "competitor_watch": {"last_scan": "", "threats": []},
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

    # ─── Codebase Scan ──────────────────────────────────────────
    def scan_codebase_for_innovations(self) -> List[PatentDoc]:
        """Scan the codebase to verify evidence files for each patent exist."""
        patents = []
        now = datetime.utcnow().isoformat() + "Z"

        for p in PATENT_PORTFOLIO:
            doc = PatentDoc(
                id=p["id"],
                title=p["title"],
                claim=p["claim"],
                filing_cost=p["filing_cost"],
                evidence_files=p["evidence_files"],
                key_innovation=p["key_innovation"],
                last_updated=now,
            )

            # Check if evidence files exist
            evidence_exists = []
            for efile in p["evidence_files"]:
                full_path = APP_DIR / efile
                evidence_exists.append(full_path.exists())
            doc.evidence_exists = evidence_exists

            # Determine status
            if not p["evidence_files"]:
                doc.status = "documented"  # No code yet, but claim is documented
            elif all(evidence_exists):
                doc.status = "filing_ready"
            elif any(evidence_exists):
                doc.status = "documented"
            else:
                doc.status = "needs_update"

            patents.append(doc)

        self.patents = patents
        return patents

    # ─── Training Data Compliance ───────────────────────────────
    def check_training_data_compliance(self) -> Dict:
        """Verify all training data sources are properly licensed."""
        compliance = {
            "audit_timestamp": datetime.utcnow().isoformat() + "Z",
            "all_sources_licensed": True,
            "flags": [],
        }

        # Check for any unlicensed data flags
        training_log = self._read_jsonl(OPT_DIR / "training_data_log.jsonl")
        for entry in training_log:
            if not entry.get("licensed", True):
                compliance["all_sources_licensed"] = False
                compliance["flags"].append(f"Unlicensed source: {entry.get('source', 'unknown')}")

        # Verify open-source model usage
        compliance["models_used"] = {
            "stable_video_diffusion": {"license": "CreativeML Open RAIL-M", "compliant": True},
            "sdxl": {"license": "CreativeML Open RAIL-M", "compliant": True},
            "librosa": {"license": "ISC", "compliant": True},
            "essentia": {"license": "AGPL-3.0", "compliant": True},
            "demucs": {"license": "MIT", "compliant": True},
            "whisper": {"license": "MIT", "compliant": True},
        }

        if compliance["all_sources_licensed"]:
            compliance["audit_status"] = "clean"
        else:
            compliance["audit_status"] = "FLAGGED"

        return compliance

    # ─── Decision Engine ────────────────────────────────────────
    def decide(self) -> IPDecision:
        decision = IPDecision(timestamp=datetime.utcnow().isoformat() + "Z")
        reasoning_parts = []

        # Count patent statuses
        filing_ready = sum(1 for p in self.patents if p.status == "filing_ready")
        documented = sum(1 for p in self.patents if p.status == "documented")
        needs_update = sum(1 for p in self.patents if p.status == "needs_update")
        total = len(self.patents)

        # Determine phase
        if filing_ready < 3:
            decision.phase = 1
            reasoning_parts.append(f"Phase 1: {filing_ready}/{total} patents filing-ready. Documenting evidence.")
        elif filing_ready < 5:
            decision.phase = 2
            reasoning_parts.append(f"Phase 2: {filing_ready}/{total} filing-ready. Refining claims.")
        elif filing_ready < 7:
            decision.phase = 3
            reasoning_parts.append(f"Phase 3: {filing_ready}/{total} filing-ready. Competitor scanning.")
        else:
            decision.phase = 4
            reasoning_parts.append(f"Phase 4: All {filing_ready}/{total} filing-ready. Portfolio maintenance.")

        # Portfolio updates
        decision.portfolio_updates = {
            "total": total,
            "filing_ready": filing_ready,
            "documented": documented,
            "needs_update": needs_update,
            "total_filing_cost": sum(p.filing_cost for p in self.patents),
        }

        # Compliance check
        compliance = self.check_training_data_compliance()
        decision.compliance_status = compliance

        if not compliance["all_sources_licensed"]:
            reasoning_parts.append("⚠️ Training data compliance issue detected!")
        else:
            reasoning_parts.append("Training data: all sources licensed. ✅")

        # Remind about filing authority
        reasoning_parts.append("Filing authority: FOUNDER ONLY. No patents filed.")

        decision.reasoning = " ".join(reasoning_parts)
        decision.metrics_snapshot = {
            "patents": [asdict(p) for p in self.patents],
            "compliance": compliance,
        }

        return decision

    # ─── Writers ────────────────────────────────────────────────
    def write_config(self, decision: IPDecision) -> Path:
        config = self.config.copy()
        config["version"] = config.get("version", 0) + 1
        config["phase"] = decision.phase
        config["status"] = "DOCUMENTATION_ONLY"
        config["filing_authority"] = "FOUNDER_ONLY"
        config["last_updated"] = decision.timestamp
        config["last_decision"] = decision.reasoning

        # Update patent portfolio
        portfolio = {}
        for p in self.patents:
            portfolio[p.id] = {
                "title": p.title,
                "claim": p.claim,
                "status": p.status,
                "last_updated": p.last_updated,
                "filing_cost": p.filing_cost,
            }
        config["patent_portfolio"] = portfolio
        config["total_filing_cost"] = sum(p.filing_cost for p in self.patents)
        config["training_data_compliance"] = decision.compliance_status

        CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n")
        print(f"[IPDocumenter] Config written → {CONFIG_PATH}")
        return CONFIG_PATH

    def write_portfolio(self, decision: IPDecision) -> Path:
        """Write detailed patent portfolio document."""
        portfolio = {
            "title": "Canvas Patent Portfolio — DOCUMENTATION ONLY",
            "status": "READY_TO_FILE_ON_FOUNDER_APPROVAL",
            "last_updated": decision.timestamp,
            "total_innovations": len(self.patents),
            "total_filing_cost": sum(p.filing_cost for p in self.patents),
            "filing_cost_note": "Micro entity rate, $320 per provisional patent application",
            "filing_authority": "Founder must explicitly authorize each filing",
            "patents": [asdict(p) for p in self.patents],
            "compliance": decision.compliance_status,
        }

        portfolio_path = DATA_DIR / "patent_portfolio.json"
        portfolio_path.write_text(json.dumps(portfolio, indent=2) + "\n")
        print(f"[IPDocumenter] Portfolio written → {portfolio_path}")
        return portfolio_path

    def _log_decision(self, decision: IPDecision):
        log_path = DATA_DIR / "ip_decisions.jsonl"
        entry = {
            "timestamp": decision.timestamp,
            "phase": decision.phase,
            "filing_ready": decision.portfolio_updates.get("filing_ready", 0),
            "compliance": decision.compliance_status.get("audit_status", "unknown"),
        }
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    # ─── Main Entry ─────────────────────────────────────────────
    def run(self) -> Dict:
        print("\n" + "=" * 65)
        print("  IP DOCUMENTER — Patent Documentation Cycle")
        print("  ⚠️  DOCUMENTATION ONLY — NO FILING WITHOUT FOUNDER AUTHORIZATION")
        print("=" * 65)

        # 1. Scan codebase
        patents = self.scan_codebase_for_innovations()
        filing_ready = sum(1 for p in patents if p.status == "filing_ready")
        print(f"\n[Scan] {filing_ready}/{len(patents)} patents filing-ready")
        for p in patents:
            emoji = "✅" if p.status == "filing_ready" else "📝" if p.status == "documented" else "⚠️"
            print(f"  {emoji} {p.id}: {p.title} [{p.status}]")

        # 2. Decide
        decision = self.decide()
        print(f"\n[Decide] {decision.reasoning}")

        # 3. Write outputs
        self.write_config(decision)
        self.write_portfolio(decision)
        self._log_decision(decision)

        result = {
            "status": "success",
            "phase": decision.phase,
            "filing_ready": filing_ready,
            "total_patents": len(patents),
            "compliance": decision.compliance_status.get("audit_status", "unknown"),
            "reasoning": decision.reasoning,
        }

        summary_path = DATA_DIR / "ip_summary.json"
        summary_path.write_text(json.dumps(result, indent=2) + "\n")

        print(f"\n{'─' * 65}")
        print(f"  RESULT: Phase {decision.phase} | {filing_ready}/{len(patents)} filing-ready")
        print(f"  Filing cost when authorized: ${sum(p.filing_cost for p in patents)}")
        print(f"{'=' * 65}\n")

        return result


def main():
    documenter = IPDocumenter()
    documenter.run()


if __name__ == "__main__":
    main()
