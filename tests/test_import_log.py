import csv
from pathlib import Path

from scripts.import_log import previous_deck_version


def test_previous_deck_version_defaults_to_last_manifest_deck(tmp_path) -> None:
    manifest = tmp_path / "manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["deck_version"])
        writer.writeheader()
        writer.writerow({"deck_version": "decks/annihilape/v02.json"})

    assert previous_deck_version(manifest) == "decks/annihilape/v02.json"


def test_previous_deck_version_falls_back_without_manifest(tmp_path) -> None:
    assert previous_deck_version(tmp_path / "missing.csv") == "decks/annihilape/v01.json"
