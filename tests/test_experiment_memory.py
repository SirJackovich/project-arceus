import csv
from pathlib import Path

from src.experiment_memory import progress_line, sync_current_from_manifest


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


def test_current_experiment_stays_active_before_target(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    current = tmp_path / "current.json"
    write_manifest(manifest, range(41, 50))

    experiment = sync_current_from_manifest(str(current), str(manifest))

    assert experiment["games_completed"] == 9
    assert experiment["completed"] is False
    assert experiment["status"] == "active"
