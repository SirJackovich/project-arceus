#!/usr/bin/env python3
import argparse
import subprocess
import sys


def run_step(command, allow_failure=False):
    print(f"\n$ {' '.join(command)}")
    result = subprocess.run(command, check=not allow_failure)
    if allow_failure and result.returncode:
        print(f"\nStep failed but analysis can continue: {' '.join(command)}")
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description="Run the Project Arceus local analysis pipeline.")
    parser.add_argument("--last", type=int, default=10, help="Number of recent games for the coach report.")
    parser.add_argument("--with-workbook", action="store_true", help="Also rebuild the XLSX workbook.")
    parser.add_argument("--verbose-coach", action="store_true", help="Render the longer coach report.")
    parser.add_argument("--ai-coach", action="store_true", help="Generate the final AI-written coach report from deterministic evidence.")
    parser.add_argument("--ai-dry-run", action="store_true", help="Write the AI prompt/context without calling the LLM.")
    args = parser.parse_args()

    run_step([sys.executable, "scripts/analyze_logs.py"])
    run_step([sys.executable, "scripts/evaluate_success.py"])
    coach_command = [sys.executable, "scripts/coach_report.py", "--last", str(args.last)]
    if args.verbose_coach:
        coach_command.append("--verbose")
    run_step(coach_command)
    if args.with_workbook:
        run_step(["node", "scripts/build_workbook.mjs"])
    if args.ai_coach or args.ai_dry_run:
        ai_command = [sys.executable, "scripts/ai_coach_report.py", "--last", str(args.last)]
        if args.ai_dry_run:
            ai_command.append("--dry-run")
        run_step(ai_command, allow_failure=True)

    print("\nDone. Start with data/analysis/ai_coach_report.md when using --ai-coach, otherwise data/analysis/deterministic_analysis.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
