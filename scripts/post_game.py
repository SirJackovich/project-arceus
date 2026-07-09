#!/usr/bin/env python3
"""Import one pasted battle log and run the normal post-game workflow."""

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.experiment_memory import is_completed, progress_line, sync_current_from_manifest


ANALYSIS_DIR = Path("data/analysis")
MANIFEST = Path("data/manifest.csv")
CURRENT_EXPERIMENT = Path("data/experiments/current.json")
DEFAULT_DECK_VERSION = "decks/annihilape/v01.json"


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


def canonical_deck_version(deck_version):
    if not deck_version:
        return DEFAULT_DECK_VERSION
    deck_path = Path(deck_version)
    if deck_path.exists():
        return deck_version
    if deck_path.parts and deck_path.parts[0] == "deck":
        corrected = Path("decks", *deck_path.parts[1:])
        if corrected.exists():
            return str(corrected)
    return deck_version


def latest_deck_version():
    row = latest_manifest_row()
    return canonical_deck_version(row.get("deck_version", ""))


def game_number_from_id(game_id):
    if not game_id.startswith("game_"):
        return "?"
    digits = ""
    for char in game_id[5:]:
        if not char.isdigit():
            break
        digits += char
    return str(int(digits)) if digits else "?"


def latest_game_number():
    row = latest_manifest_row()
    number = game_number_from_id(row.get("game_id", "")) if row else "?"
    return int(number) if str(number).isdigit() else 0


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


def main():
    parser = argparse.ArgumentParser(description="Import a battle log and run the normal Project Arceus post-game workflow.")
    parser.add_argument("--last", type=int, default=10, help="Number of recent games for the AI coach report.")
    parser.add_argument("--no-ai", action="store_true", help="Skip the AI coach and print deterministic evidence path only.")
    parser.add_argument("--deck-review", action="store_true", help="Also run the last-N-games Deck Coach after the Game Coach.")
    parser.add_argument("--verbose", action="store_true", help="Show command output, deterministic evidence, and full AI report.")
    parser.add_argument("--ai-dry-run", action="store_true", help="Write AI prompt/context without calling the LLM.")
    args = parser.parse_args()

    import_command = [
        sys.executable,
        "scripts/import_log.py",
        "--deck-version",
        latest_deck_version(),
    ]
    if not args.verbose:
        import_command.append("--quiet")
    subprocess.run(import_command, check=True)

    deck_version = latest_deck_version()
    run_step([sys.executable, "scripts/analyze_logs.py"], verbose=args.verbose)
    run_step([sys.executable, "scripts/evaluate_success.py", "--deck", deck_version], verbose=args.verbose)
    coach_command = [sys.executable, "scripts/coach_report.py", "--last", str(args.last), "--deck", deck_version]
    if args.verbose:
        coach_command.append("--verbose")
    run_step(coach_command, verbose=args.verbose)
    experiment = sync_current_from_manifest(str(CURRENT_EXPERIMENT), str(MANIFEST))
    deck_review_due = is_completed(experiment)

    if not args.verbose:
        print_saved_summary()
        print(record_line())
        print(progress_line(experiment))

    if args.no_ai:
        if args.verbose:
            return 0
        print(f"Deterministic report: {ANALYSIS_DIR / 'deterministic_analysis.json'}")
        print(top_issue_line())
        return 0

    game_command = [sys.executable, "scripts/game_coach.py", "--game", "latest", "--deck", deck_version]
    if args.ai_dry_run:
        game_command.append("--dry-run")
    if args.verbose:
        game_command.append("--verbose")
    result = run_step(game_command, verbose=args.verbose, allow_failure=True)
    if args.verbose:
        if args.deck_review or deck_review_due:
            deck_command = [
                sys.executable,
                "scripts/deck_coach.py",
                "--experiment",
                "current",
                "--last",
                str(args.last),
                "--deck",
                deck_version,
                "--verbose",
            ]
            if args.ai_dry_run:
                deck_command.append("--dry-run")
            run_step(deck_command, verbose=True, allow_failure=True)
        return 0
    if result.stdout:
        print()
        print(result.stdout.strip())
    if result.returncode:
        print("Game Coach unavailable. Deterministic evidence was still generated.")

    if args.deck_review or deck_review_due:
        deck_command = [
            sys.executable,
            "scripts/deck_coach.py",
            "--experiment",
            "current",
            "--last",
            str(args.last),
            "--deck",
            deck_version,
        ]
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
