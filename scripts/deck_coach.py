#!/usr/bin/env python3
"""Generate an AI deck review from the last N games of deterministic evidence."""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ai_coaching import (
    DEFAULT_EXPERIMENT,
    DEFAULT_MODEL,
    compact_deck,
    generated_at,
    read_json,
    run_llm_report,
)


def compact_evidence(evidence: dict, last: int) -> dict:
    recent_games = evidence.get("games", [])[-last:]
    return {
        "layer": evidence.get("layer", "deterministic_analyzer"),
        "scope": evidence.get("scope", ""),
        "summary": evidence.get("summary", {}),
        "recent_games": recent_games,
        "success_conditions": evidence.get("success_conditions", []),
        "mulligan_warnings": evidence.get("mulligan_warnings", []),
        "mulligan_rate": evidence.get("mulligan_rate", {}),
        "card_tracking": evidence.get("card_tracking", [])[:15],
        "annihilape_attack_quality": evidence.get("annihilape_attack_quality", [])[-last:],
        "attack_decision_quality": evidence.get("attack_decision_quality", [])[-30:],
        "stadium_quality": evidence.get("stadium_quality", [])[-last:],
        "evolution_line": evidence.get("evolution_line", {}),
        "line_rebuild": evidence.get("line_rebuild", [])[-last:],
        "backup_attacker": evidence.get("backup_attacker", [])[-last:],
        "possible_loss_factors": evidence.get("possible_loss_factors", []),
        "experiment_metrics": evidence.get("experiment_metrics", {}),
        "candidate_strengths": evidence.get("candidate_strengths", []),
        "legacy_first_attack_miss_reasons": evidence.get("annihilape_attack_miss_reasons", {}),
    }


def build_context(args: argparse.Namespace) -> dict:
    evidence = read_json(args.evidence_json)
    if not evidence:
        raise SystemExit(f"Missing deterministic evidence JSON: {args.evidence_json}")
    deck = read_json(args.deck, {})
    experiment = read_json(args.experiment_state, DEFAULT_EXPERIMENT) or DEFAULT_EXPERIMENT
    return {
        "generated_at": generated_at(),
        "coach_type": "deck_coach",
        "instructions": "Use deterministic evidence only. Analyze last-N trends, deck construction, and experiment results.",
        "deck": compact_deck(deck),
        "current_experiment": experiment,
        "deterministic_evidence": compact_evidence(evidence, args.last),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the AI-written Project Arceus deck coach report.")
    parser.add_argument("--evidence-json", default="data/analysis/deterministic_analysis.json")
    parser.add_argument("--deck", default="decks/annihilape/v01.json")
    parser.add_argument("--experiment-state", default="data/experiment_tracker.json")
    parser.add_argument("--prompt", default="prompts/deck_coach.md")
    parser.add_argument("--last", type=int, default=10)
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", DEFAULT_MODEL))
    parser.add_argument("--output-md", default="data/analysis/deck_coach_report.md")
    parser.add_argument("--output-json", default="data/analysis/deck_coach_report.json")
    parser.add_argument("--prompt-out", default="data/analysis/deck_coach_prompt.json")
    parser.add_argument("--dry-run", action="store_true", help="Write the prompt/context without calling the LLM.")
    parser.add_argument("--verbose", action="store_true", help="Print the full report and output paths.")
    args = parser.parse_args()

    prompt = Path(args.prompt).read_text(encoding="utf-8")
    context = build_context(args)
    labels = [
        ("Verdict", "verdict"),
        ("Why", "why"),
        ("Experiment Status", "experiment_status"),
        ("Next Focus", "next_focus"),
        ("Confidence", "confidence"),
    ]
    return run_llm_report(args, prompt, context, "Deck Coach", labels)


if __name__ == "__main__":
    raise SystemExit(main())
