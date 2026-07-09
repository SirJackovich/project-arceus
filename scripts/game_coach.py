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
from src.experiment_memory import read_current


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


def as_int(value) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


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


def turn_summary(attack_decisions: list, stadium_rows: list, evolution_rows: list) -> list[dict]:
    rows = []
    for row in attack_decisions:
        rows.append({
            "turn": row.get("turn", "unknown"),
            "event": "attack",
            "summary": (
                f"{row.get('attacker', '')} used {row.get('attack', '')} into {row.get('target', '')}; "
                f"damage {row.get('damage', 0)}, prizes {row.get('prize_value', 0)}"
            ).strip(),
            "evidence": row.get("evidence", ""),
        })
    for row in stadium_rows:
        rows.append({
            "turn": row.get("risky_ruins_played_by_turn", "unknown"),
            "event": "stadium",
            "summary": f"Risky Ruins timing: {row.get('risky_ruins_played_by_turn', 'none')}",
            "evidence": "stadium_quality",
        })
    for row in evolution_rows:
        rows.append({
            "turn": row.get("first_complete_line_turn", row.get("completed_turn", "unknown")),
            "event": "evolution_line",
            "summary": f"Evolution bottleneck: {row.get('bottleneck', 'none')}",
            "evidence": "evolution_line",
        })
    return sorted(rows, key=lambda row: as_int(row.get("turn")))[:12]


def prize_swing_events(attack_decisions: list) -> list[dict]:
    return [
        row for row in attack_decisions
        if as_int(row.get("prize_value")) > 0 or row.get("opponent_immediately_ko_attacker") == "yes"
    ]


def key_turning_point(timing_context: dict, attack_decisions: list, selected: dict) -> dict:
    prize_events = prize_swing_events(attack_decisions)
    if timing_context.get("early_prize_attackers_before_annihilape"):
        first = timing_context["early_prize_attackers_before_annihilape"][0]
        return {
            "type": "early_attacker_prize_pressure",
            "summary": f"{first.get('attacker')} started the prize plan before Annihilape was online.",
            "evidence": first.get("evidence", ""),
        }
    if prize_events:
        first = prize_events[0]
        return {
            "type": "prize_swing",
            "summary": f"{first.get('attacker')} prize swing on Turn {first.get('turn')}: {first.get('prize_value')} prize(s).",
            "evidence": first.get("evidence", ""),
        }
    return {
        "type": "result_context",
        "summary": f"Game result: {selected.get('result', 'unknown')} vs {selected.get('opponent', 'unknown')}",
        "evidence": selected.get("game_id", ""),
    }


def why_win_loss_candidates(selected: dict, timing_context: dict, attack_decisions: list,
                            backup_rows: list, experiment_signals: dict) -> list[dict]:
    candidates = []
    result = selected.get("result", "unknown")
    if timing_context.get("classification"):
        candidates.append({
            "candidate": timing_context["classification"],
            "supports_result": "yes" if result == "win" and "successfully bought time" in timing_context["classification"] else "unknown",
            "confidence": timing_context.get("confidence", "low"),
        })
    prize_total = sum(as_int(row.get("prize_value")) for row in attack_decisions)
    if prize_total:
        candidates.append({
            "candidate": f"visible attacks took {prize_total} prize(s)",
            "supports_result": "yes" if result == "win" else "mixed",
            "confidence": "high",
        })
    for row in backup_rows:
        state = row.get("state", "")
        if state and state != "not tested":
            candidates.append({"candidate": f"backup attacker state: {state}", "supports_result": "mixed", "confidence": "medium"})
    if experiment_signals.get("waitress_events_this_game") or experiment_signals.get("ssp_attacks_this_game"):
        candidates.append({"candidate": "experiment cards appeared in this game", "supports_result": "unknown", "confidence": "medium"})
    return candidates[:6]


def annihilape_timing_context(selected: dict, attack_quality: list, attack_decisions: list,
                              evolution_line: list, miss_reasons: list) -> dict:
    first_attack = attack_quality[0] if attack_quality else {}
    first_turn_raw = first_attack.get("first_attack_turn", "none")
    first_turn = as_int(first_turn_raw)
    is_late = first_turn_raw == "none" or first_turn > 4
    early_attackers = [
        row for row in attack_decisions
        if row.get("attacker") in {"Hawlucha", "Primeape"}
        and as_int(row.get("prize_value")) > 0
        and (first_turn_raw == "none" or as_int(row.get("turn")) < first_turn)
    ]
    evolution_bottleneck = next((row.get("bottleneck", "") for row in evolution_line if row.get("bottleneck")), "")

    if not is_late:
        classification = "Annihilape was on time"
        confidence = "high"
        recommendation_hint = "Do not focus on first Annihilape timing for this game."
    elif early_attackers:
        classification = "early attacker successfully bought time"
        confidence = "high"
        recommendation_hint = "Do not treat late Annihilape as the main problem; review whether the early attacker prize plan created enough tempo."
    elif selected.get("result") == "win":
        classification = "late Annihilape because opponent conceded/was weak"
        confidence = "medium" if "conceded" in selected.get("game_id", "") else "low"
        recommendation_hint = "Do not over-correct Annihilape timing from this game; the win did not require the normal attacker curve."
    elif miss_reasons or evolution_bottleneck:
        classification = "late Annihilape because setup failed"
        confidence = "medium"
        recommendation_hint = "Focus next game on the specific setup bottleneck before blaming attack timing alone."
    else:
        classification = "late Annihilape for unknown reason"
        confidence = "low"
        recommendation_hint = "Keep the conclusion tentative because hidden hand/prize information may explain the delay."

    return {
        "first_annihilape_attack_turn": first_turn_raw,
        "classification": classification,
        "confidence": confidence,
        "early_prize_attackers_before_annihilape": early_attackers,
        "evolution_bottleneck": evolution_bottleneck,
        "miss_reasons": miss_reasons,
        "recommendation_hint": recommendation_hint,
    }


def compact_game_evidence(evidence: dict, selected: dict) -> dict:
    game_id = selected.get("game_id", "")
    game_label = selected.get("game", game_id)
    mulligan_rate = evidence.get("mulligan_rate", {})
    attack_quality = rows_for_game(evidence.get("annihilape_attack_quality", []), game_id)
    attack_decisions = rows_for_game(evidence.get("attack_decision_quality", []), game_id)
    stadium_rows = rows_for_game(evidence.get("stadium_quality", []), game_id)
    evolution_line = rows_for_game(evidence.get("evolution_line", {}).get("rows", []), game_id)
    miss_reasons = details_for_game(evidence.get("annihilape_attack_miss_reasons", {}), game_id)
    backup_rows = rows_for_game(evidence.get("backup_attacker", []), game_id)
    experiment_signals = experiment_for_game(evidence.get("experiment_metrics", {}), game_label, game_id)
    timing_context = annihilape_timing_context(selected, attack_quality, attack_decisions, evolution_line, miss_reasons)
    return {
        "layer": evidence.get("layer", "deterministic_analyzer"),
        "scope": "single current game",
        "game": selected,
        "mulligan_warnings": rows_for_game(evidence.get("mulligan_warnings", []), game_id),
        "mulligan_rate_this_game": rows_for_game(mulligan_rate.get("mulligans_per_game", []), game_id),
        "annihilape_attack_quality": attack_quality,
        "attack_decision_quality": attack_decisions,
        "turn_summary": turn_summary(attack_decisions, stadium_rows, evolution_line),
        "key_turning_point": key_turning_point(timing_context, attack_decisions, selected),
        "prize_swing_events": prize_swing_events(attack_decisions),
        "stadium_quality": stadium_rows,
        "evolution_line": evolution_line,
        "line_rebuild": rows_for_game(evidence.get("line_rebuild", []), game_id),
        "backup_attacker": backup_rows,
        "first_attack_miss_reasons": miss_reasons,
        "annihilape_timing_context": timing_context,
        "experiment_signals_this_game": experiment_signals,
        "why_win_loss_candidates": why_win_loss_candidates(selected, timing_context, attack_decisions, backup_rows, experiment_signals),
    }


def build_context(args: argparse.Namespace) -> dict:
    evidence = read_json(args.evidence_json)
    if not evidence:
        raise SystemExit(f"Missing deterministic evidence JSON: {args.evidence_json}")
    deck = read_json(args.deck, {})
    experiment = read_current(args.experiment_state)
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
    parser.add_argument("--experiment-state", default="data/experiments/current.json")
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
        ("Win/Loss", "win_loss"),
        ("Biggest Lesson", "biggest_lesson"),
        ("Experiment Status", "experiment_status"),
        ("Biggest Mistake", "biggest_mistake"),
        ("Next Game Focus", "next_game_focus"),
    ]
    return run_llm_report(args, prompt, context, "Game Coach", labels)


if __name__ == "__main__":
    raise SystemExit(main())
