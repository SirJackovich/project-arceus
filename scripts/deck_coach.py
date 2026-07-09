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
from src.card_recommender import load_card_database, search_candidates
from src.experiment_memory import (
    active_experiment_change,
    authoritative_next_experiment,
    game_label,
    game_number,
    is_completed,
    read_current,
    rollover_to_next_experiment,
    rows_in_experiment,
)


def summarize_games(games: list[dict]) -> dict:
    wins = sum(1 for game in games if game.get("result") == "win")
    losses = sum(1 for game in games if game.get("result") == "loss")
    return {
        "games": len(games),
        "wins": wins,
        "losses": losses,
        "win_rate": round((wins / (wins + losses)) * 100) if wins + losses else 0,
    }


def filter_by_game_id(rows: list, selected_ids: set[str]) -> list:
    return [row for row in rows if row.get("game_id") in selected_ids]


def filter_by_game_label(rows: list, selected_labels: set[str]) -> list:
    return [row for row in rows if row.get("game") in selected_labels]


def compact_evolution_line(evolution_line: dict, selected_ids: set[str]) -> dict:
    rows = filter_by_game_id(evolution_line.get("rows", []), selected_ids)
    bottlenecks = {}
    hand_gaps = {}
    for row in rows:
        bottleneck = row.get("bottleneck", "")
        if bottleneck:
            bottlenecks[bottleneck] = bottlenecks.get(bottleneck, 0) + 1
        for gap in row.get("hand_gaps", []) if isinstance(row.get("hand_gaps"), list) else []:
            hand_gaps[gap] = hand_gaps.get(gap, 0) + 1
    return {"rows": rows, "bottlenecks": bottlenecks, "hand_gaps": hand_gaps}


def compact_experiment_metrics(metrics: dict, selected_labels: set[str], experiment: dict) -> dict:
    evidence_rows = filter_by_game_label(metrics.get("evidence", []), selected_labels)
    ssp_attacks = filter_by_game_label(metrics.get("ssp_attacks", []), selected_labels)
    waitress_rows = [row for row in evidence_rows if row.get("card") == "Waitress"]
    waitress_attached = sum(1 for row in waitress_rows if row.get("result") == "attached energy")
    waitress_whiff = sum(1 for row in waitress_rows if row.get("result") == "whiff/no visible attach")
    ssp_wins = sum(1 for row in ssp_attacks if row.get("outcome") == "positive")
    ssp_losses = sum(1 for row in ssp_attacks if row.get("outcome") == "negative")
    return {
        "current_experiment": experiment,
        "waitress_played_count": len(waitress_rows),
        "waitress_attached_energy_count": waitress_attached,
        "waitress_whiff_count": waitress_whiff,
        "waitress_games": sorted({row.get("game") for row in waitress_rows if row.get("game")}),
        "ssp_annihilape_attack_count": len(ssp_attacks),
        "ssp_annihilape_games": sorted({row.get("game") for row in ssp_attacks if row.get("game")}),
        "ssp_attacks": ssp_attacks,
        "ssp_outcome": {
            "positive_attacks": ssp_wins,
            "negative_attacks": ssp_losses,
            "neutral_attacks": sum(1 for row in ssp_attacks if row.get("outcome") == "neutral"),
            "classification": "neutral" if ssp_wins == ssp_losses else "won" if ssp_wins > ssp_losses else "lost",
            "inference_note": metrics.get("ssp_outcome", {}).get("inference_note", ""),
        },
        "evidence": evidence_rows,
    }


def selected_experiment_games(evidence: dict, args: argparse.Namespace, experiment: dict) -> list[dict]:
    games = evidence.get("games", [])
    if args.experiment == "current":
        return rows_in_experiment(games, experiment)
    return sorted(games, key=lambda row: game_number(row.get("game_id", "")))[-args.last:]


def compact_evidence(evidence: dict, args: argparse.Namespace, experiment: dict) -> dict:
    recent_games = selected_experiment_games(evidence, args, experiment)
    selected_ids = {game.get("game_id", "") for game in recent_games}
    selected_labels = {game.get("game") or game_label(game.get("game_id", "")) for game in recent_games}
    structured_next = authoritative_next_experiment(experiment) if is_completed(experiment) else {}
    return {
        "layer": evidence.get("layer", "deterministic_analyzer"),
        "scope": "active experiment games" if args.experiment == "current" else evidence.get("scope", ""),
        "experiment_completed": is_completed(experiment),
        "authoritative_next_experiment": structured_next,
        "summary": summarize_games(recent_games),
        "recent_games": recent_games,
        "selected_game_ids": sorted(selected_ids, key=game_number),
        "success_conditions": evidence.get("success_conditions", []),
        "mulligan_warnings": filter_by_game_id(evidence.get("mulligan_warnings", []), selected_ids),
        "mulligan_rate": evidence.get("mulligan_rate", {}),
        "card_tracking": evidence.get("card_tracking", [])[:15],
        "annihilape_attack_quality": filter_by_game_id(evidence.get("annihilape_attack_quality", []), selected_ids),
        "attack_decision_quality": filter_by_game_id(evidence.get("attack_decision_quality", []), selected_ids),
        "stadium_quality": filter_by_game_id(evidence.get("stadium_quality", []), selected_ids),
        "evolution_line": compact_evolution_line(evidence.get("evolution_line", {}), selected_ids),
        "line_rebuild": filter_by_game_id(evidence.get("line_rebuild", []), selected_ids),
        "backup_attacker": filter_by_game_id(evidence.get("backup_attacker", []), selected_ids),
        "possible_loss_factors": evidence.get("possible_loss_factors", []),
        "experiment_metrics": compact_experiment_metrics(evidence.get("experiment_metrics", {}), selected_labels, experiment),
        "candidate_strengths": evidence.get("candidate_strengths", []),
        "legacy_first_attack_miss_reasons": evidence.get("annihilape_attack_miss_reasons", {}),
    }


def build_context(args: argparse.Namespace) -> dict:
    evidence = read_json(args.evidence_json)
    if not evidence:
        raise SystemExit(f"Missing deterministic evidence JSON: {args.evidence_json}")
    deck = read_json(args.deck, {})
    experiment = read_current(args.experiment_state) if args.experiment == "current" else read_json(args.experiment_state, DEFAULT_EXPERIMENT) or DEFAULT_EXPERIMENT
    experiment_change = active_experiment_change(experiment)
    scoped_evidence = compact_evidence(evidence, args, experiment)
    if Path(args.card_db).exists():
        scoped_evidence["card_recommendations"] = search_candidates(
            scoped_evidence,
            deck,
            load_card_database(args.card_db),
            args.max_candidates,
            experiment=experiment,
        )
    else:
        scoped_evidence["card_recommendations"] = {
            "status": "missing_card_database",
            "message": f"Build the local Standard database with `python3 scripts/build_standard_card_db.py --output {args.card_db}`.",
            "candidates": [],
        }
    return {
        "generated_at": generated_at(),
        "coach_type": "deck_coach",
        "instructions": "Use deterministic evidence only. Analyze active experiment games, deck construction, and experiment results.",
        "deck": compact_deck(deck),
        "current_experiment": experiment,
        "active_experiment": experiment_change,
        "deterministic_evidence": scoped_evidence,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the AI-written Project Arceus deck coach report.")
    parser.add_argument("--evidence-json", default="data/analysis/deterministic_analysis.json")
    parser.add_argument("--deck", default="decks/annihilape/v01.json")
    parser.add_argument("--experiment-state", default="data/experiments/current.json")
    parser.add_argument("--experiment", choices=["current", "last"], default="last", help="Use current experiment games or generic last-N scope.")
    parser.add_argument("--card-db", default="data/cards/standard_cards.json", help="Local Standard card database JSON.")
    parser.add_argument("--max-candidates", type=int, default=12)
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
        ("Is The Current Experiment Finished?", "experiment_finished"),
        ("What Did We Actually Learn?", "what_we_learned"),
        ("What Deck Change Do You Recommend?", "deck_change"),
        ("Confidence", "confidence"),
        ("Next Experiment", "next_experiment"),
    ]
    result = run_llm_report(args, prompt, context, "Deck Coach", labels)
    if result == 0 and args.experiment == "current" and not args.dry_run and is_completed(context.get("current_experiment")):
        next_experiment = rollover_to_next_experiment(args.experiment_state)
        if args.verbose:
            print(f"Experiment memory advanced to {next_experiment.get('id')}: {next_experiment.get('name')}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
