#!/usr/bin/env python3
"""Run Project Arceus safety checks before committing changes."""

import argparse
import json
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def run(command: list[str], *, env: Optional[dict[str, str]] = None) -> None:
    print(f"$ {' '.join(command)}")
    result = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True)
    if result.returncode:
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        result.check_returncode()


def syntax_check() -> None:
    print("\nSyntax check")
    pycache = Path(tempfile.mkdtemp(prefix="project-arceus-pycache-"))
    old_prefix = sys.pycache_prefix
    sys.pycache_prefix = str(pycache)
    try:
        for path in sorted([*ROOT.glob("scripts/*.py"), *ROOT.glob("tests/*.py")]):
            py_compile.compile(str(path), doraise=True)
    finally:
        sys.pycache_prefix = old_prefix
        shutil.rmtree(pycache, ignore_errors=True)


def pytest_check() -> None:
    print("\nPytest")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "tests"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode and "No module named pytest" in result.stderr:
        raise SystemExit(
            "pytest is required for Project Arceus checks. Install dependencies with: "
            "python3 -m pip install -r requirements.txt"
        )
    result.check_returncode()


def sample_analysis_check() -> None:
    print("\nSample log analysis")
    with tempfile.TemporaryDirectory(prefix="project-arceus-check-") as tmp:
        analysis = Path(tmp) / "analysis"
        experiment_state = Path(tmp) / "current_experiment.json"
        experiment_state.write_text(json.dumps({
            "id": "test",
            "name": "Fixture experiment",
            "deck_changes": ["fixture cards"],
            "hypothesis": "Fixture checks should exercise current experiment scoping.",
            "success_criteria": ["sample pipeline runs"],
            "start_game": 1,
            "games_target": 4,
            "target_games": 4,
            "cards_being_tested": ["Waitress", "Annihilape SSP 100"],
            "games_completed": 4,
            "games": [],
            "completed": True,
            "status": "completed",
            "final_verdict": "",
            "next_experiment": "",
        }, indent=2) + "\n", encoding="utf-8")
        env = os.environ.copy()
        env.setdefault("PYTHONPYCACHEPREFIX", str(Path(tmp) / "pycache"))
        run([sys.executable, "scripts/analyze_logs.py", "--input-dir", str(FIXTURES), "--output-dir", str(analysis)], env=env)
        run([sys.executable, "scripts/evaluate_success.py", "--analysis-dir", str(analysis)], env=env)
        run(
            [
                sys.executable,
                "scripts/coach_report.py",
                "--analysis-dir",
                str(analysis),
                "--last",
                "10",
                "--output-md",
                str(analysis / "coach_report.md"),
                "--output-json",
                str(analysis / "coach_report.json"),
                "--snapshot-dir",
                str(analysis / "snapshots"),
                "--no-snapshot",
            ],
            env=env,
        )
        run(
            [
                sys.executable,
                "scripts/game_coach.py",
                "--evidence-json",
                str(analysis / "deterministic_analysis.json"),
                "--game",
                "latest",
                "--output-md",
                str(analysis / "game_coach_report.md"),
                "--output-json",
                str(analysis / "game_coach_report.json"),
                "--prompt-out",
                str(analysis / "game_coach_prompt.json"),
                "--experiment-state",
                str(experiment_state),
                "--dry-run",
            ],
            env=env,
        )
        run(
            [
                sys.executable,
                "scripts/deck_coach.py",
                "--evidence-json",
                str(analysis / "deterministic_analysis.json"),
                "--experiment",
                "current",
                "--experiment-state",
                str(experiment_state),
                "--card-db",
                str(FIXTURES / "standard_cards.json"),
                "--last",
                "10",
                "--output-md",
                str(analysis / "deck_coach_report.md"),
                "--output-json",
                str(analysis / "deck_coach_report.json"),
                "--prompt-out",
                str(analysis / "deck_coach_prompt.json"),
                "--dry-run",
            ],
            env=env,
        )
        run(
            [
                sys.executable,
                "scripts/recommend_cards.py",
                "--evidence-json",
                str(analysis / "deterministic_analysis.json"),
                "--card-db",
                str(FIXTURES / "standard_cards.json"),
                "--output-json",
                str(analysis / "card_recommendations.json"),
            ],
            env=env,
        )
        expected = [
            "summary.json",
            "games.csv",
            "raw_events.csv",
            "opening_hands.csv",
            "card_usage.csv",
            "attack_usage.csv",
            "success_condition_details.csv",
            "deterministic_analysis.json",
            "coach_report.json",
            "coach_report.md",
            "game_coach_report.json",
            "game_coach_report.md",
            "game_coach_prompt.json",
            "deck_coach_report.json",
            "deck_coach_report.md",
            "deck_coach_prompt.json",
            "card_recommendations.json",
        ]
        missing = [name for name in expected if not (analysis / name).exists()]
        if missing:
            raise SystemExit(f"Sample analysis missing expected output files: {', '.join(missing)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Project Arceus syntax, test, and sample-analysis checks.")
    parser.parse_args()
    syntax_check()
    pytest_check()
    sample_analysis_check()
    print("\nProject Arceus checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
