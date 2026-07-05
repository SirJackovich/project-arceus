import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def run_sample_pipeline(tmp_path: Path) -> Path:
    analysis = tmp_path / "analysis"
    subprocess.run(
        [sys.executable, "scripts/analyze_logs.py", "--input-dir", str(FIXTURES), "--output-dir", str(analysis)],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, "scripts/evaluate_success.py", "--analysis-dir", str(analysis)],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
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
        cwd=ROOT,
        check=True,
    )
    return analysis


def by_game(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row["game_id"]: row for row in rows}


def test_mulligan_reveal_does_not_become_opening_hand(tmp_path: Path) -> None:
    analysis = run_sample_pipeline(tmp_path)
    games = by_game(read_csv(analysis / "games.csv"))
    events = read_csv(analysis / "raw_events.csv")
    game_id = "game_001_mulligan_risky_hidden"

    assert games[game_id]["my_mulligans"] == "1"
    assert games[game_id]["my_opening_hand_visibility"] == "hidden_after_mulligan"
    assert any(
        event["game_id"] == game_id
        and event["event_type"] == "mulligan_revealed_card"
        and event["card_name"] == "Risky Ruins"
        for event in events
    )
    assert not any(
        event["game_id"] == game_id
        and event["event_type"] == "opening_hand"
        and event["card_name"] == "Risky Ruins"
        for event in events
    )


def test_win_loss_and_partial_log_detection(tmp_path: Path) -> None:
    analysis = run_sample_pipeline(tmp_path)
    games = by_game(read_csv(analysis / "games.csv"))

    assert games["game_002_waitress_attach_ssp_positive"]["result"] == "win"
    assert games["game_003_waitress_whiff_ssp_negative_loss"]["result"] == "loss"
    assert games["game_005_partial_corrupt"]["result"] == "unknown"
    assert games["game_005_partial_corrupt"]["has_game_log"] == "partial"


def test_risky_ruins_timing(tmp_path: Path) -> None:
    analysis = run_sample_pipeline(tmp_path)
    payload = json.loads((analysis / "deterministic_analysis.json").read_text(encoding="utf-8"))
    risky_game = next(
        row for row in payload["stadium_quality"]
        if row["game_id"] == "game_004_risky_ruins_timing_win"
    )

    assert risky_game["risky_ruins_played_by_turn"] == 1
    assert risky_game["first_full_power_depended_on_it"] == "yes"


def test_waitress_attach_and_whiff_tracking(tmp_path: Path) -> None:
    analysis = run_sample_pipeline(tmp_path)
    payload = json.loads((analysis / "deterministic_analysis.json").read_text(encoding="utf-8"))
    experiment = payload["experiment_metrics"]

    assert experiment["waitress_played_count"] == 2
    assert experiment["waitress_attached_energy_count"] == 1
    assert experiment["waitress_whiff_count"] == 1


def test_ssp_annihilape_attack_outcomes(tmp_path: Path) -> None:
    analysis = run_sample_pipeline(tmp_path)
    payload = json.loads((analysis / "deterministic_analysis.json").read_text(encoding="utf-8"))
    attacks = {
        (row["game_number"], row["attack_used"]): row
        for row in payload["experiment_metrics"]["ssp_attacks"]
    }

    positive = attacks[(2, "Destined Fight")]
    negative = attacks[(3, "Tantrum")]
    assert positive["target"] == "Jellicent ex"
    assert positive["prizes_gained"] == 3
    assert positive["opponent_prizes_gained"] == 2
    assert positive["outcome"] == "positive"
    assert negative["opponent_prizes_gained"] == 2
    assert negative["outcome"] == "negative"


def test_golden_output_for_known_fixture(tmp_path: Path) -> None:
    analysis = run_sample_pipeline(tmp_path)
    games = by_game(read_csv(analysis / "games.csv"))
    payload = json.loads((analysis / "deterministic_analysis.json").read_text(encoding="utf-8"))
    game_id = "game_002_waitress_attach_ssp_positive"
    attack = next(
        row for row in payload["experiment_metrics"]["ssp_attacks"]
        if row["game_number"] == 2
    )

    assert games[game_id]["opponent"] == "Fufu1292"
    assert games[game_id]["result"] == "win"
    assert games[game_id]["my_went_first"] == "yes"
    assert attack == {
        "game": "Game 2",
        "game_number": 2,
        "card": "Annihilape SSP 100",
        "attack_used": "Destined Fight",
        "target": "Jellicent ex",
        "prizes_gained": 3,
        "opponent_prizes_gained": 2,
        "outcome": "positive",
        "result": "Destined Fight",
        "evidence": "SirJackovich's Annihilape used Destined Fight on Fufu1292's Jellicent ex for 320 damage.",
    }
