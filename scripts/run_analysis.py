#!/usr/bin/env python3
"""Run the Project Arceus analysis pipeline without importing a new game."""

import argparse
import json
import subprocess
import sys
from pathlib import Path


ANALYSIS_DIR = Path("data/analysis")


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
    if allow_failure and result.returncode:
        if verbose:
            print(f"\nStep failed but analysis can continue: {' '.join(command)}")
        return False, result.stdout if hasattr(result, "stdout") else ""
    return True, result.stdout if hasattr(result, "stdout") else ""


def read_json(path):
    path = Path(path)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def record_line():
    summary = read_json(ANALYSIS_DIR / "deterministic_analysis.json").get("summary", {})
    if not summary:
        summary = read_json(ANALYSIS_DIR / "summary.json")
    wins = summary.get("wins", 0)
    losses = summary.get("losses", 0)
    return f"Last 10: {wins}-{losses}" if wins or losses else "Last 10: unknown"


def top_issue_line():
    evidence = read_json(ANALYSIS_DIR / "deterministic_analysis.json")
    factors = evidence.get("possible_loss_factors", [])
    if not factors:
        return "Top issue: no clear issue detected"
    top = factors[0]
    return f"Top issue: {top.get('factor', 'unknown')} ({top.get('confidence', 'medium')} confidence)"


def main():
    parser = argparse.ArgumentParser(description="Run the Project Arceus local analysis pipeline.")
    parser.add_argument("--last", type=int, default=10, help="Number of recent games for the report.")
    parser.add_argument("--with-workbook", action="store_true", help="Also rebuild the XLSX workbook.")
    parser.add_argument("--verbose", action="store_true", help="Show command output and full reports.")
    parser.add_argument("--verbose-coach", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--ai-coach", action="store_true", help="Generate the AI-written Deck Coach report from deterministic evidence.")
    parser.add_argument("--game-coach", action="store_true", help="Generate the AI-written Game Coach report for the latest game.")
    parser.add_argument("--ai-dry-run", action="store_true", help="Write the AI prompt/context without calling the LLM.")
    args = parser.parse_args()
    verbose = args.verbose or args.verbose_coach

    run_step([sys.executable, "scripts/analyze_logs.py"], verbose=verbose)
    run_step([sys.executable, "scripts/evaluate_success.py"], verbose=verbose)
    coach_command = [sys.executable, "scripts/coach_report.py", "--last", str(args.last)]
    if verbose:
        coach_command.append("--verbose")
    run_step(coach_command, verbose=verbose)
    if args.with_workbook:
        run_step(["node", "scripts/build_workbook.mjs"], verbose=verbose)

    if args.game_coach:
        game_command = [sys.executable, "scripts/game_coach.py", "--game", "latest"]
        if args.ai_dry_run:
            game_command.append("--dry-run")
        if verbose:
            game_command.append("--verbose")
        ok, output = run_step(game_command, verbose=verbose, allow_failure=True)
        if not verbose and output:
            print(output.strip())
        if not ok and not verbose:
            print("Game Coach unavailable. Deterministic evidence was still generated.")
        return 0

    if args.ai_coach or args.ai_dry_run:
        ai_command = [sys.executable, "scripts/deck_coach.py", "--last", str(args.last)]
        if args.ai_dry_run:
            ai_command.append("--dry-run")
        if verbose:
            ai_command.append("--verbose")
        ok, output = run_step(ai_command, verbose=verbose, allow_failure=True)
        if not verbose and output:
            print(output.strip())
        if not ok and not verbose:
            print("Deck Coach unavailable. Deterministic evidence was still generated.")
        return 0

    if verbose:
        return 0
    print(f"Deterministic report: {ANALYSIS_DIR / 'deterministic_analysis.json'}")
    print(record_line())
    print(top_issue_line())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
