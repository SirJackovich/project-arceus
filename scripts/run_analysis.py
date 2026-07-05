#!/usr/bin/env python3
import argparse
import subprocess
import sys


def run_step(command):
    print(f"\n$ {' '.join(command)}")
    subprocess.run(command, check=True)


def main():
    parser = argparse.ArgumentParser(description="Run the Project Arceus local analysis pipeline.")
    parser.add_argument("--last", type=int, default=10, help="Number of recent games for the coach report.")
    parser.add_argument("--with-workbook", action="store_true", help="Also rebuild the XLSX workbook.")
    parser.add_argument("--verbose-coach", action="store_true", help="Render the longer coach report.")
    args = parser.parse_args()

    run_step([sys.executable, "scripts/analyze_logs.py"])
    run_step([sys.executable, "scripts/evaluate_success.py"])
    coach_command = [sys.executable, "scripts/coach_report.py", "--last", str(args.last)]
    if args.verbose_coach:
        coach_command.append("--verbose")
    run_step(coach_command)
    if args.with_workbook:
        run_step(["node", "scripts/build_workbook.mjs"])

    print("\nDone. Start with data/analysis/coach_report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
