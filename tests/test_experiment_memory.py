import csv
import json
from pathlib import Path

from src.experiment_memory import (
    active_experiment_change,
    authoritative_next_experiment,
    progress_line,
    read_current,
    rollover_to_next_experiment,
    sync_current_from_manifest,
)


def write_manifest(path: Path, game_numbers: range) -> None:
    fields = ["game_id", "result", "opponent"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for number in game_numbers:
            writer.writerow({
                "game_id": f"game_{number:03d}_test",
                "result": "win" if number % 2 else "loss",
                "opponent": f"Opponent{number}",
            })


def test_current_experiment_completes_at_target_game_count(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    current = tmp_path / "current.json"
    write_manifest(manifest, range(41, 51))

    experiment = sync_current_from_manifest(str(current), str(manifest))

    assert experiment["games_completed"] == 10
    assert experiment["completed"] is True
    assert experiment["status"] == "completed"
    assert experiment["games"][0]["game"] == "Game 41"
    assert experiment["games"][-1]["game"] == "Game 50"
    assert progress_line(experiment) == "Experiment 004: 10/10 games complete."


def test_completed_experiment_004_has_authoritative_lana_aid_next_experiment(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    current = tmp_path / "current.json"
    write_manifest(manifest, range(41, 51))

    experiment = sync_current_from_manifest(str(current), str(manifest))
    experiment["final_verdict"] = "SSP Annihilape = KEEP; Waitress = KEEP FOR NOW."
    experiment["next_experiment"] = "Test Lana's Aid, likely replacing Energy Switch first."

    next_experiment = authoritative_next_experiment(experiment)

    assert next_experiment["remove"] == [{"card": "Energy Switch", "count": 2}]
    assert next_experiment["add"] == [{"card": "Lana's Aid", "count": 2}]
    assert "Energy Switch only works when Energy remains in play" in next_experiment["hypothesis"]


def test_rollover_to_lana_aid_experiment_archives_completed_current(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    current = tmp_path / "current.json"
    write_manifest(manifest, range(41, 51))

    experiment = sync_current_from_manifest(str(current), str(manifest))
    experiment["final_verdict"] = "SSP Annihilape = KEEP; Waitress = KEEP FOR NOW."
    experiment["next_experiment"] = "Test Lana's Aid, likely replacing Energy Switch first."
    current.write_text(json.dumps(experiment), encoding="utf-8")

    next_experiment = rollover_to_next_experiment(str(current))

    assert next_experiment["id"] == "005"
    assert next_experiment["name"] == "Lana's Aid Rebuild Consistency"
    assert next_experiment["deck_changes"] == ["Remove Energy Switch x2", "Add Lana's Aid x2"]
    assert next_experiment["start_game"] == 51
    assert next_experiment["completed"] is False
    assert (tmp_path / "005-lanas-aid.json").exists()
    assert (tmp_path / "004-ssp-annihilape-waitress.json").exists()
    assert read_current(str(current))["id"] == "005"


def test_active_experiment_change_parses_remove_add_counts() -> None:
    experiment = {
        "id": "005",
        "name": "Lana's Aid Rebuild Consistency",
        "deck_changes": ["Remove Energy Switch x2", "Add Lana's Aid x2"],
    }

    assert active_experiment_change(experiment) == {
        "remove": [{"card": "Energy Switch", "count": 2}],
        "add": [{"card": "Lana's Aid", "count": 2}],
        "name": "Lana's Aid Rebuild Consistency",
        "id": "005",
    }


def test_current_experiment_stays_active_before_target(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    current = tmp_path / "current.json"
    write_manifest(manifest, range(41, 50))

    experiment = sync_current_from_manifest(str(current), str(manifest))

    assert experiment["games_completed"] == 9
    assert experiment["completed"] is False
    assert experiment["status"] == "active"
