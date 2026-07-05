#!/usr/bin/env python3
import argparse
import subprocess
import sys


def run_step(command):
    print(f"\n$ {' '.join(command)}")
    subprocess.run(command, check=True)


def main():
    parser = argparse.ArgumentParser(description="Import the latest pasted battle log and run the coach analysis.")
    parser.add_argument("--last", type=int, default=10, help="Number of recent games for the coach report.")
    parser.add_argument("--verbose-coach", action="store_true", help="Render the longer coach report.")
    parser.add_argument("--ai-coach", action="store_true", help="Generate the final AI-written coach report.")
    parser.add_argument("--ai-dry-run", action="store_true", help="Write AI prompt/context without calling the LLM.")
    args = parser.parse_args()

    run_step([sys.executable, "scripts/import_log.py"])
    command = [sys.executable, "scripts/run_analysis.py", "--last", str(args.last)]
    if args.verbose_coach:
        command.append("--verbose-coach")
    if args.ai_coach:
        command.append("--ai-coach")
    if args.ai_dry_run:
        command.append("--ai-dry-run")
    run_step(command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
