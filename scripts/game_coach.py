#!/usr/bin/env python3
"""Generate an AI coach report for only the current game."""

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


def game_number(game_id: str) -> int:
    if game_id.startswith("game_"):
        digits = ""
        for char in game_id[5:]:
            if not char.isdigit():
                break
            digits += char
        if digits:
            return int(digits)
    return 0


def select_game(evidence: dict, selector: str) -> dict:
    games = evidence.get("games", [])
    if not games:
        raise SystemExit("No games found in deterministic evidence.")
    if selector == "latest":
        return sorted(games, key=lambda row: game_number(row.get("game_id", "")))[-1]
    if selector.isdigit():
        target = int(selector)
        match = next((game for game in games if game_number(game.get("game_id", "")) == target), None)
        if match:
            return match
    match = next((game for game in games if game.get("game_id") == selector or game.get("game") == selector), None)
    if not match:
        raise SystemExit(f"Game not found in deterministic evidence: {selector}")
    return match


def rows_for_game(rows: list, game_id: str) -> list:
    return [row for row in rows if row.get("game_id") == game_id]


def details_for_game(payload: dict, game_id: str) -> list:
    return [row for row in payload.get("details", []) if row.get("game_id") == game_id]


def experiment_for_game(metrics: dict, game_label: str, game_id: str) -> dict:
    waitress = [row for row in metrics.get("evidence", []) if row.get("game") == game_label and row.get("card") == "Waitress"]
    ssp_attacks = [row for row in metrics.get("ssp_attacks", []) if row.get("game") == game_label]
    return {
        "current_experiment": metrics.get("current_experiment", {}),
        "game_id": game_id,
        "game": game_label,
        "waitress_events_this_game": waitress,
        "ssp_attacks_this_game": ssp_attacks,
    }


def compact_game_evidence(evidence: dict, selected: dict) -> dict:
    game_id = selected.get("game_id", "")
    game_label = selected.get("game", game_id)
    mulligan_rate = evidence.get("mulligan_rate", {})
    return {
        "layer": evidence.get("layer", "deterministic_analyzer"),
        "scope": "single current game",
        "game": selected,
        "mulligan_warnings": rows_for_game(evidence.get("mulligan_warnings", []), game_id),
        "mulligan_rate_this_game": rows_for_game(mulligan_rate.get("mulligans_per_game", []), game_id),
        "annihilape_attack_quality": rows_for_game(evidence.get("annihilape_attack_quality", []), game_id),
        "attack_decision_quality": rows_for_game(evidence.get("attack_decision_quality", []), game_id),
        "stadium_quality": rows_for_game(evidence.get("stadium_quality", []), game_id),
        "evolution_line": rows_for_game(evidence.get("evolution_line", {}).get("rows", []), game_id),
        "line_rebuild": rows_for_game(evidence.get("line_rebuild", []), game_id),
        "backup_attacker": rows_for_game(evidence.get("backup_attacker", []), game_id),
        "first_attack_miss_reasons": details_for_game(evidence.get("annihilape_attack_miss_reasons", {}), game_id),
        "experiment_signals_this_game": experiment_for_game(evidence.get("experiment_metrics", {}), game_label, game_id),
    }


def build_context(args: argparse.Namespace) -> dict:
    evidence = read_json(args.evidence_json)
    if not evidence:
        raise SystemExit(f"Missing deterministic evidence JSON: {args.evidence_json}")
    deck = read_json(args.deck, {})
    experiment = read_json(args.experiment_state, DEFAULT_EXPERIMENT) or DEFAULT_EXPERIMENT
    selected = select_game(evidence, args.game)
    return {
        "generated_at": generated_at(),
        "coach_type": "game_coach",
        "instructions": "Analyze only the selected current game. Do not compare to previous games except active experiment context.",
        "deck": compact_deck(deck),
        "current_experiment": experiment,
        "deterministic_evidence": compact_game_evidence(evidence, selected),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the AI-written Project Arceus game coach report.")
    parser.add_argument("--evidence-json", default="data/analysis/deterministic_analysis.json")
    parser.add_argument("--deck", default="decks/annihilape/v01.json")
    parser.add_argument("--experiment-state", default="data/experiment_tracker.json")
    parser.add_argument("--prompt", default="prompts/game_coach.md")
    parser.add_argument("--game", default="latest", help="Game number, game_id, or latest.")
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", DEFAULT_MODEL))
    parser.add_argument("--output-md", default="data/analysis/game_coach_report.md")
    parser.add_argument("--output-json", default="data/analysis/game_coach_report.json")
    parser.add_argument("--prompt-out", default="data/analysis/game_coach_prompt.json")
    parser.add_argument("--dry-run", action="store_true", help="Write the prompt/context without calling the LLM.")
    parser.add_argument("--verbose", action="store_true", help="Print the full report and output paths.")
    args = parser.parse_args()

    prompt = Path(args.prompt).read_text(encoding="utf-8")
    context = build_context(args)
    labels = [
        ("Verdict", "verdict"),
        ("Why", "why"),
        ("Biggest Positive", "biggest_positive"),
        ("Biggest Mistake", "biggest_mistake"),
        ("Next Focus", "next_focus"),
        ("Confidence", "confidence"),
    ]
    return run_llm_report(args, prompt, context, "Game Coach", labels)


if __name__ == "__main__":
    raise SystemExit(main())
