#!/usr/bin/env python3
"""Run Project Arceus safety checks before committing changes."""

import argparse
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
