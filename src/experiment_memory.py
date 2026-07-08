"""Experiment memory helpers for Project Arceus."""

import csv
import json
import re
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

LANA_AID_EXPERIMENT_ID = "005"
LANA_AID_EXPERIMENT_NAME = "Lana's Aid Rebuild Consistency"
LANA_AID_HYPOTHESIS = (
    "Lana's Aid improves rebuild after KOs better than Energy Switch, "
    "because Energy Switch only works when Energy remains in play."
)
LANA_AID_SUCCESS_CRITERIA = [
    "After the first Annihilape line is KO'd, the deck can rebuild to another attacker more often.",
    "Lana's Aid creates visible recovery or energy attachment value in multiple games.",
    "Replacing Energy Switch does not noticeably reduce early attack tempo.",
]


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


def slugify(value: str) -> str:
    value = value.lower().replace("'", "")
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "experiment"


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


def last_completed_game_number(experiment: dict) -> int:
    games = experiment.get("games", [])
    numbers = [game_number(game.get("game_id", "")) for game in games if isinstance(game, dict)]
    return max(numbers) if numbers else int(experiment.get("start_game") or 0) - 1


def authoritative_next_experiment(experiment: dict) -> dict:
    """Convert completed experiment memory into a structured next experiment when possible."""
    text = (experiment.get("next_experiment") or "").lower()
    is_lana_aid_request = "lana" in text and "energy switch" in text
    if experiment.get("id") == "004" or is_lana_aid_request:
        return {
            "remove": [{"card": "Energy Switch", "count": 2}],
            "add": [{"card": "Lana's Aid", "count": 2}],
            "hypothesis": LANA_AID_HYPOTHESIS,
            "success_criteria": LANA_AID_SUCCESS_CRITERIA,
            "confidence": "medium",
            "source": "current_experiment.next_experiment",
        }
    return {}


def build_lana_aid_experiment(previous_experiment: dict) -> dict:
    start_game = last_completed_game_number(previous_experiment) + 1
    return {
        "id": LANA_AID_EXPERIMENT_ID,
        "name": LANA_AID_EXPERIMENT_NAME,
        "deck_changes": [
            "Remove Energy Switch x2",
            "Add Lana's Aid x2",
        ],
        "hypothesis": LANA_AID_HYPOTHESIS,
        "success_criteria": LANA_AID_SUCCESS_CRITERIA,
        "start_game": start_game,
        "games_target": 10,
        "target_games": 10,
        "cards_being_tested": ["Lana's Aid"],
        "games_completed": 0,
        "games": [],
        "completed": False,
        "status": "active",
        "previous_experiment_id": previous_experiment.get("id", ""),
        "rejected_cards": ["Salvatore"],
        "reconsiderable_cards": [],
        "final_verdict": "",
        "next_experiment": "",
    }


def parse_deck_change_line(line: str) -> dict:
    normalized = line.strip()
    match = re.match(r"^(Remove|Add)\s+(.+?)\s+x(\d+)$", normalized, flags=re.IGNORECASE)
    if not match:
        return {}
    action, card, count = match.groups()
    return {"action": action.lower(), "card": card.strip(), "count": int(count)}


def active_experiment_change(experiment: dict) -> dict:
    """Return the active experiment's exact Remove/Add change in a coach-friendly shape."""
    changes = {"remove": [], "add": []}
    for line in experiment.get("deck_changes", []):
        parsed = parse_deck_change_line(str(line))
        if not parsed:
            continue
        changes[f"{parsed['action']}"].append({"card": parsed["card"], "count": parsed["count"]})
    if not changes["remove"] and not changes["add"]:
        return {}
    changes["name"] = experiment.get("name", "")
    changes["id"] = experiment.get("id", "")
    return changes


def archive_experiment_path(experiment: dict, directory: Path) -> Path:
    experiment_id = experiment.get("id", "unknown")
    name = slugify(experiment.get("name") or experiment_id)
    return directory / f"{experiment_id}-{name}.json"


def rollover_to_next_experiment(current_path: str = "data/experiments/current.json") -> dict:
    """Archive a completed current experiment and make the next experiment active."""
    current_path_obj = Path(current_path)
    experiment = read_current(current_path)
    if not is_completed(experiment):
        return experiment
    next_change = authoritative_next_experiment(experiment)
    if not next_change:
        return experiment

    directory = current_path_obj.parent
    directory.mkdir(parents=True, exist_ok=True)
    archive_path = archive_experiment_path(experiment, directory)
    archive_path.write_text(json.dumps(experiment, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    next_experiment = build_lana_aid_experiment(experiment)
    next_path = directory / "005-lanas-aid.json"
    next_path.write_text(json.dumps(next_experiment, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_current(next_experiment, current_path)
    return next_experiment


def progress_line(experiment: dict) -> str:
    name = experiment.get("name") or f"Experiment {experiment.get('id', '')}".strip()
    completed = experiment.get("games_completed", 0)
    target = experiment.get("games_target") or experiment.get("target_games") or 10
    return f"Experiment {experiment.get('id', '').strip() or name}: {completed}/{target} games complete."


def is_completed(experiment: Optional[dict]) -> bool:
    if not experiment:
        return False
    return bool(experiment.get("completed") or experiment.get("status") == "completed")
