#!/usr/bin/env python3
import argparse
import json
from datetime import date
from pathlib import Path


DEFAULT_STATE = "data/experiment_tracker.json"


def read_state(path):
    path = Path(path)
    if not path.exists():
        return {
            "current_experiment": None,
            "history": [],
        }
    return json.loads(path.read_text(encoding="utf-8"))


def write_state(path, state):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def split_values(value):
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def active_experiment(state):
    experiment = state.get("current_experiment")
    if not experiment:
        raise SystemExit("No current experiment. Start one with `python3 scripts/experiment_tracker.py start ...`.")
    return experiment


def command_start(args):
    state = read_state(args.state)
    if state.get("current_experiment"):
        state.setdefault("history", []).append(state["current_experiment"])
    state["current_experiment"] = {
        "name": args.name,
        "started_on": date.today().isoformat(),
        "changed_cards": split_values(args.changed_cards),
        "target_question": args.target_question,
        "target_games": args.target_games,
        "games": [],
        "evidence_for": [],
        "evidence_against": [],
        "status": "active",
        "recommendation_after_10_games": "insufficient data",
    }
    write_state(args.state, state)
    print(json.dumps(state["current_experiment"], indent=2, ensure_ascii=False))


def command_record(args):
    state = read_state(args.state)
    experiment = active_experiment(state)
    game_entry = {
        "game": args.game,
        "result": args.result,
        "evidence_for": split_values(args.evidence_for),
        "evidence_against": split_values(args.evidence_against),
        "notes": args.notes,
    }
    experiment.setdefault("games", []).append(game_entry)
    experiment.setdefault("evidence_for", []).extend(game_entry["evidence_for"])
    experiment.setdefault("evidence_against", []).extend(game_entry["evidence_against"])
    update_recommendation(experiment)
    write_state(args.state, state)
    print(json.dumps(experiment, indent=2, ensure_ascii=False))


def update_recommendation(experiment):
    games = experiment.get("games", [])
    if len(games) < experiment.get("target_games", 10):
        experiment["recommendation_after_10_games"] = "keep testing until target game count"
        return
    for_count = len(experiment.get("evidence_for", []))
    against_count = len(experiment.get("evidence_against", []))
    if for_count > against_count:
        experiment["recommendation_after_10_games"] = "evidence leans keep testing"
    elif against_count > for_count:
        experiment["recommendation_after_10_games"] = "evidence leans change cards"
    else:
        experiment["recommendation_after_10_games"] = "mixed evidence; ask AI coach to decide"


def command_show(args):
    state = read_state(args.state)
    print(json.dumps(state, indent=2, ensure_ascii=False))


def command_close(args):
    state = read_state(args.state)
    experiment = active_experiment(state)
    experiment["status"] = "closed"
    experiment["closed_on"] = date.today().isoformat()
    experiment["final_decision"] = args.decision
    if args.notes:
        experiment["final_notes"] = args.notes
    state.setdefault("history", []).append(experiment)
    state["current_experiment"] = None
    write_state(args.state, state)
    print(json.dumps(state, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Track the current Project Arceus deck experiment.")
    parser.add_argument("--state", default=DEFAULT_STATE)
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="Start a new current experiment.")
    start.add_argument("--name", required=True)
    start.add_argument("--changed-cards", default="", help="Comma-separated changed cards.")
    start.add_argument("--target-question", required=True)
    start.add_argument("--target-games", type=int, default=10)
    start.set_defaults(func=command_start)

    record = subparsers.add_parser("record", help="Record evidence from a game.")
    record.add_argument("--game", required=True)
    record.add_argument("--result", choices=["win", "loss", "unknown"], default="unknown")
    record.add_argument("--evidence-for", default="", help="Comma-separated evidence supporting the experiment.")
    record.add_argument("--evidence-against", default="", help="Comma-separated evidence against the experiment.")
    record.add_argument("--notes", default="")
    record.set_defaults(func=command_record)

    show = subparsers.add_parser("show", help="Show experiment state.")
    show.set_defaults(func=command_show)

    close = subparsers.add_parser("close", help="Close the current experiment.")
    close.add_argument("--decision", required=True, choices=["keep testing", "change cards", "inconclusive"])
    close.add_argument("--notes", default="")
    close.set_defaults(func=command_close)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
