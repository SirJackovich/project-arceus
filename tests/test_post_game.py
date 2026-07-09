import csv
from pathlib import Path

import scripts.post_game as post_game


def write_manifest(path: Path, deck_version: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "imported_at",
                "match_date",
                "log_file",
                "game_id",
                "deck_version",
                "opponent",
                "result",
                "went_first",
                "conceded",
                "ranked_points_before",
                "ranked_points_after",
                "source",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerow({"game_id": "game_052_test", "deck_version": deck_version})


def test_latest_deck_version_uses_previous_manifest_row(tmp_path, monkeypatch) -> None:
    manifest = tmp_path / "manifest.csv"
    write_manifest(manifest, "decks/annihilape/v02.json")
    monkeypatch.setattr(post_game, "MANIFEST", manifest)

    assert post_game.latest_deck_version() == "decks/annihilape/v02.json"


def test_latest_deck_version_repairs_singular_deck_path(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "decks" / "annihilape").mkdir(parents=True)
    (tmp_path / "decks" / "annihilape" / "v02.json").write_text("{}", encoding="utf-8")
    manifest = tmp_path / "manifest.csv"
    write_manifest(manifest, "deck/annihilape/v02.json")
    monkeypatch.setattr(post_game, "MANIFEST", manifest)

    assert post_game.latest_deck_version() == "decks/annihilape/v02.json"
