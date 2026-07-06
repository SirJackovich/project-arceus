"""Experiment memory helpers for Project Arceus."""

import csv
import json
from copy import deepcopy
from pathlib import Path
from typing import Iterable, Optional


DEFAULT_CURRENT_EXPERIMENT = {
    "id": "004",
    "name": "SSP Annihilape + Waitress",
    "deck_changes": ["1 Annihilape SSP 100", "2 Waitress ASC 215"],
    "hypothesis": "SSP Annihilape and Waitress improve rebuilds, tempo, or awkward evolution/energy games enough to keep them.",
    "success_criteria": [
        "Waitress creates visible energy acceleration more often than it whiffs.",
        "SSP Annihilape attacks produce positive or neutral prize swings.",
        "The package improves rebuilds after the first evolution line breaks.",
    ],
    "start_game": 41,
    "games_target": 10,
    "target_games": 10,
    "cards_being_tested": ["Annihilape SSP 100", "Waitress ASC 215"],
    "games_completed": 0,
    "games": [],
    "completed": False,
    "status": "active",
    "final_verdict": "",
    "next_experiment": "",
}


def game_number(game_id: str) -> int:
    if not game_id.startswith("game_"):
        return 0
    digits = ""
    for char in game_id[5:]:
        if not char.isdigit():
            break
        digits += char
    return int(digits) if digits else 0


def game_label(game_id: str) -> str:
    number = game_number(game_id)
    return f"Game {number}" if number else game_id


def default_experiment() -> dict:
    return deepcopy(DEFAULT_CURRENT_EXPERIMENT)


def read_current(path: str = "data/experiments/current.json") -> dict:
    path_obj = Path(path)
    if not path_obj.exists():
        return default_experiment()
    return json.loads(path_obj.read_text(encoding="utf-8"))


def write_current(experiment: dict, path: str = "data/experiments/current.json") -> None:
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    path_obj.write_text(json.dumps(experiment, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def manifest_rows(path: str = "data/manifest.csv") -> list[dict]:
    path_obj = Path(path)
    if not path_obj.exists():
        return []
    with path_obj.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def experiment_window(experiment: dict) -> tuple[int, int]:
    start = int(experiment.get("start_game") or 0)
    target = int(experiment.get("games_target") or experiment.get("target_games") or 10)
    return start, target


def rows_in_experiment(rows: Iterable[dict], experiment: dict) -> list[dict]:
    start, target = experiment_window(experiment)
    if not start or not target:
        return []
    end = start + target - 1
    selected = []
    for row in rows:
        number = game_number(row.get("game_id", ""))
        if start <= number <= end:
            selected.append(row)
    return sorted(selected, key=lambda row: game_number(row.get("game_id", "")))


def sync_progress(experiment: dict, rows: Iterable[dict]) -> dict:
    updated = deepcopy(experiment)
    selected = rows_in_experiment(rows, updated)
    _, target = experiment_window(updated)
    games = [
        {
            "game_id": row.get("game_id", ""),
            "game": game_label(row.get("game_id", "")),
            "result": row.get("result", ""),
            "opponent": row.get("opponent", ""),
        }
        for row in selected
    ]
    updated["games"] = games
    updated["games_completed"] = len(games)
    updated["games_target"] = target
    updated["target_games"] = target
    updated["completed"] = len(games) >= target
    if updated["completed"] and updated.get("status") == "active":
        updated["status"] = "completed"
    elif not updated["completed"] and updated.get("status") == "completed":
        updated["status"] = "active"
    return updated


def sync_current_from_manifest(current_path: str = "data/experiments/current.json",
                               manifest_path: str = "data/manifest.csv") -> dict:
    experiment = read_current(current_path)
    updated = sync_progress(experiment, manifest_rows(manifest_path))
    write_current(updated, current_path)
    return updated


def progress_line(experiment: dict) -> str:
    name = experiment.get("name") or f"Experiment {experiment.get('id', '')}".strip()
    completed = experiment.get("games_completed", 0)
    target = experiment.get("games_target") or experiment.get("target_games") or 10
    return f"Experiment {experiment.get('id', '').strip() or name}: {completed}/{target} games complete."


def is_completed(experiment: Optional[dict]) -> bool:
    if not experiment:
        return False
    return bool(experiment.get("completed") or experiment.get("status") == "completed")
