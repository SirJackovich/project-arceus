#!/usr/bin/env python3
import argparse
import shutil
from datetime import datetime
from pathlib import Path

from import_log import (
    DEFAULT_DECK_VERSION,
    DEFAULT_LOGS_DIR,
    DEFAULT_MANIFEST,
    DEFAULT_MANIFEST_JSON,
    DEFAULT_PLAYER,
    build_filename,
    infer_log_metadata,
    unique_path,
    write_manifest_csv,
    write_manifest_json,
)


def source_logs(logs_dir):
    return sorted(
        path for path in logs_dir.glob("*.txt")
        if path.is_file()
    )


def manifest_sort_key(row):
    game_id = row.get("game_id", "")
    number = ""
    for char in game_id.replace("game_", "", 1):
        if not char.isdigit():
            break
        number += char
    return (int(number) if number else 10_000, game_id)


def existing_game_number(path, fallback):
    stem = path.stem.lower()
    for prefix in ("game_", ""):
        if stem.startswith(prefix):
            rest = stem[len(prefix):]
            number = ""
            for char in rest:
                if not char.isdigit():
                    break
                number += char
            if number:
                return int(number)
    return fallback


def file_match_date(path):
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")


def normalize_logs(args):
    logs = source_logs(args.logs_dir)
    imported_at = datetime.now().astimezone().isoformat(timespec="seconds")
    rows = []
    planned = []

    for index, source_path in enumerate(logs, start=1):
        log_text = source_path.read_text(encoding="utf-8-sig", errors="replace")
        inferred = infer_log_metadata(log_text, args.player)
        game_number = existing_game_number(source_path, index)
        match_date = args.match_date or file_match_date(source_path)
        filename = build_filename(
            game_number,
            match_date,
            inferred["result"],
            inferred["opponent"],
            args.deck_version,
            inferred["conceded"],
        )
        target_path = args.logs_dir / filename
        if target_path != source_path:
            target_path = unique_path(target_path)

        row = {
            "imported_at": imported_at,
            "match_date": match_date,
            "log_file": str(target_path),
            "game_id": target_path.stem,
            "deck_version": args.deck_version,
            "opponent": inferred["opponent"],
            "result": inferred["result"],
            "went_first": inferred["went_first"],
            "conceded": inferred["conceded"],
            "ranked_points_before": "",
            "ranked_points_after": "",
            "source": "normalized_existing_log",
            "notes": f"Original file: {source_path.name}",
        }
        rows.append(row)
        planned.append((source_path, target_path, log_text))

    rows.sort(key=manifest_sort_key)
    planned.sort(key=lambda item: item[1].name)

    if args.dry_run:
        for source_path, target_path, _ in planned:
            print(f"{source_path.name} -> {target_path.name}")
        print(f"Would write {len(rows)} manifest rows.")
        return 0

    args.archive_dir.mkdir(parents=True, exist_ok=True)
    for source_path, target_path, log_text in planned:
        archive_path = unique_path(args.archive_dir / source_path.name)
        shutil.move(str(source_path), str(archive_path))
        target_path.write_text(log_text, encoding="utf-8")

    write_manifest_csv(args.manifest, rows)
    write_manifest_json(args.manifest_json, rows)

    print(f"Archived originals: {args.archive_dir}")
    print(f"Normalized logs: {args.logs_dir}")
    print(f"Wrote CSV manifest: {args.manifest}")
    print(f"Wrote JSON manifest: {args.manifest_json}")
    print(f"Games normalized: {len(rows)}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Rename existing logs to the Project Arceus convention and rebuild manifests."
    )
    parser.add_argument("--logs-dir", default=DEFAULT_LOGS_DIR, type=Path)
    parser.add_argument("--archive-dir", default=Path("data/logs_original"), type=Path)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST, type=Path)
    parser.add_argument("--manifest-json", default=DEFAULT_MANIFEST_JSON, type=Path)
    parser.add_argument("--deck-version", default=DEFAULT_DECK_VERSION)
    parser.add_argument("--player", default=DEFAULT_PLAYER)
    parser.add_argument("--match-date", help="Override match date for every log. Defaults to each file's modified date.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    return normalize_logs(args)


if __name__ == "__main__":
    raise SystemExit(main())
