#!/usr/bin/env python3
"""Import one pasted battle log and run the normal post-game workflow."""

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path


ANALYSIS_DIR = Path("data/analysis")
MANIFEST = Path("data/manifest.csv")
EXPERIMENT_STATE = Path("data/experiment_tracker.json")


def run_step(command, verbose=False, allow_failure=False):
    if verbose:
        print(f"\n$ {' '.join(command)}")
        result = subprocess.run(command, check=not allow_failure)
    else:
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        if result.returncode and not allow_failure:
            if result.stdout:
                print(result.stdout, end="")
            if result.stderr:
                print(result.stderr, end="", file=sys.stderr)
            raise subprocess.CalledProcessError(result.returncode, command)
    return result


def read_json(path):
    path = Path(path)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def latest_manifest_row():
    if not MANIFEST.exists():
        return {}
    with MANIFEST.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return rows[-1] if rows else {}


def game_number_from_id(game_id):
    if not game_id.startswith("game_"):
        return "?"
    digits = ""
    for char in game_id[5:]:
        if not char.isdigit():
            break
        digits += char
    return str(int(digits)) if digits else "?"


def record_line():
    summary = read_json(ANALYSIS_DIR / "deterministic_analysis.json").get("summary", {})
    return f"Last 10: {summary.get('wins', 0)}-{summary.get('losses', 0)}"


def top_issue_line():
    evidence = read_json(ANALYSIS_DIR / "deterministic_analysis.json")
    factors = evidence.get("possible_loss_factors", [])
    if not factors:
        return "Top issue: no clear issue detected"
    top = factors[0]
    return f"Top issue: {top.get('factor', 'unknown')} ({top.get('confidence', 'medium')} confidence)"


def print_saved_summary():
    row = latest_manifest_row()
    if not row:
        return
    print(f"Saved Game {game_number_from_id(row.get('game_id', ''))}: {row.get('result', 'unknown')} vs {row.get('opponent', 'unknown') or 'unknown'}")


def experiment_review_due():
    state = read_json(EXPERIMENT_STATE)
    experiment = state.get("current_experiment") if isinstance(state, dict) else None
    if not experiment or experiment.get("status") not in {"active", ""}:
        return False
    try:
        target = int(experiment.get("target_games") or 10)
    except (TypeError, ValueError):
        target = 10
    games = experiment.get("games") or []
    return len(games) >= target


def main():
    parser = argparse.ArgumentParser(description="Import a battle log and run the normal Project Arceus post-game workflow.")
    parser.add_argument("--last", type=int, default=10, help="Number of recent games for the AI coach report.")
    parser.add_argument("--no-ai", action="store_true", help="Skip the AI coach and print deterministic evidence path only.")
    parser.add_argument("--deck-review", action="store_true", help="Also run the last-N-games Deck Coach after the Game Coach.")
    parser.add_argument("--verbose", action="store_true", help="Show command output, deterministic evidence, and full AI report.")
    parser.add_argument("--ai-dry-run", action="store_true", help="Write AI prompt/context without calling the LLM.")
    args = parser.parse_args()

    import_command = [sys.executable, "scripts/import_log.py"]
    if not args.verbose:
        import_command.append("--quiet")
    subprocess.run(import_command, check=True)

    run_step([sys.executable, "scripts/analyze_logs.py"], verbose=args.verbose)
    run_step([sys.executable, "scripts/evaluate_success.py"], verbose=args.verbose)
    coach_command = [sys.executable, "scripts/coach_report.py", "--last", str(args.last)]
    if args.verbose:
        coach_command.append("--verbose")
    run_step(coach_command, verbose=args.verbose)

    if not args.verbose:
        print_saved_summary()
        print(record_line())

    if args.no_ai:
        if args.verbose:
            return 0
        print(f"Deterministic report: {ANALYSIS_DIR / 'deterministic_analysis.json'}")
        print(top_issue_line())
        return 0

    game_command = [sys.executable, "scripts/game_coach.py", "--game", "latest"]
    if args.ai_dry_run:
        game_command.append("--dry-run")
    if args.verbose:
        game_command.append("--verbose")
    result = run_step(game_command, verbose=args.verbose, allow_failure=True)
    if args.verbose:
        if args.deck_review or experiment_review_due():
            deck_command = [sys.executable, "scripts/deck_coach.py", "--last", str(args.last), "--verbose"]
            if args.ai_dry_run:
                deck_command.append("--dry-run")
            run_step(deck_command, verbose=True, allow_failure=True)
        return 0
    if result.stdout:
        print()
        print(result.stdout.strip())
    if result.returncode:
        print("Game Coach unavailable. Deterministic evidence was still generated.")

    if args.deck_review or experiment_review_due():
        deck_command = [sys.executable, "scripts/deck_coach.py", "--last", str(args.last)]
        if args.ai_dry_run:
            deck_command.append("--dry-run")
        deck_result = run_step(deck_command, verbose=False, allow_failure=True)
        if deck_result.stdout:
            print()
            print(deck_result.stdout.strip())
        if deck_result.returncode:
            print("Deck Coach unavailable. Deterministic evidence was still generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
