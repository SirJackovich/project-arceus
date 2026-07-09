#!/usr/bin/env python3
"""Interactively save a pasted Pokemon TCG Live battle log and manifest row."""

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path


DEFAULT_LOGS_DIR = Path("data/logs")
DEFAULT_MANIFEST = Path("data/manifest.csv")
DEFAULT_MANIFEST_JSON = Path("data/manifest.json")
DEFAULT_DECK_VERSION = "decks/annihilape/v01.json"
DEFAULT_PLAYER = "SirJackovich"
END_MARKER = "::END_LOG::"

MANIFEST_FIELDS = [
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
]


def ask(prompt, default=""):
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or default


def ask_choice(prompt, choices, default=""):
    choices_text = "/".join(choices)
    while True:
        value = ask(f"{prompt} ({choices_text})", default).lower()
        if not value or value in choices:
            return value
        print(f"Please enter one of: {choices_text}")


def slugify(text):
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def deck_code(deck_version):
    path = Path(deck_version)
    if len(path.parts) >= 2 and path.parts[0] == "decks":
        return slugify(f"{path.parts[1]}_{path.stem}")
    return slugify(path.stem or deck_version) or "unknown_deck"


def compact_date(match_date):
    return re.sub(r"[^0-9]", "", match_date) or datetime.now().strftime("%Y%m%d")


def build_filename(game_number, match_date, result, opponent, deck_version, conceded):
    status = slugify(result) or "unknown"
    if conceded == "yes":
        status = f"{status}_conceded"
    opponent_code = slugify(opponent) or "unknown"
    return (
        f"game_{game_number:03d}_{compact_date(match_date)}_"
        f"{status}_vs_{opponent_code}_{deck_code(deck_version)}.txt"
    )


def unique_path(path):
    if not path.exists():
        return path
    for number in range(2, 1000):
        candidate = path.with_name(f"{path.stem}_{number}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not find an available filename for {path}")


def first_non_user(players, player_name):
    for player in players:
        if player and player != player_name:
            return player
    return ""


def infer_log_metadata(log_text, player_name):
    players = []
    opening_player = ""
    went_first = "unknown"
    winner = ""
    conceded = "yes" if re.search(r"\bconced", log_text, flags=re.IGNORECASE) else "unknown"

    for raw_line in log_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("-") or line.startswith("•"):
            continue

        for pattern in [
            r"^(.+?) chose .+ for the opening coin flip\.$",
            r"^(.+?) drew 7 cards for the opening hand\.$",
            r"^(.+?)'s Turn$",
            r"^(.+?) decided to go (?:first|second)\.$",
            r"^(.+?) (?:played|attached|evolved|drew|retreated|took|won)\b",
        ]:
            match = re.match(pattern, line)
            if match:
                name = match.group(1).strip()
                if name and name not in players:
                    players.append(name)
                break

        match = re.match(r"^(.+?) decided to go (first|second)\.$", line)
        if match:
            opening_player = match.group(1).strip()
            choice = match.group(2)
            if opening_player == player_name:
                went_first = "yes" if choice == "first" else "no"
            else:
                went_first = "no" if choice == "first" else "yes"

        match = re.search(r"(?:^|\.\s)([^\s.]+) wins\.$", line)
        if match:
            winner = match.group(1).strip()

    opponent = first_non_user(players, player_name)
    if not opponent and winner and winner != player_name:
        opponent = winner

    if winner == player_name:
        result = "win"
    elif winner:
        result = "loss"
    else:
        result = "unknown"

    if conceded == "unknown" and winner:
        conceded = "no"

    return {
        "opponent": opponent,
        "result": result,
        "went_first": went_first,
        "conceded": conceded,
        "winner": winner,
        "opening_player": opening_player,
    }


def next_game_number(logs_dir):
    max_number = 0
    for path in logs_dir.glob("*.txt"):
        match = re.match(r"(?:game_)?(\d+)(?:_|$)", path.stem, flags=re.IGNORECASE)
        if match:
            max_number = max(max_number, int(match.group(1)))
    return max_number + 1


def read_pasted_log():
    print("Paste the Pokemon TCG Live battle log below.")
    print(f"When finished, type {END_MARKER} on its own line and press Enter.")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == END_MARKER:
            break
        lines.append(line)
    return "\n".join(lines).strip() + "\n"


def append_manifest_row(manifest_path, row):
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    exists = manifest_path.exists()
    with manifest_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow({field: row.get(field, "") for field in MANIFEST_FIELDS})


def read_manifest_rows(manifest_path):
    if not manifest_path.exists():
        return []
    with manifest_path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_manifest_csv(manifest_path, rows):
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in MANIFEST_FIELDS})


def write_manifest_json(manifest_path, rows):
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "games": [{field: row.get(field, "") for field in MANIFEST_FIELDS} for row in rows],
    }
    manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def append_manifest(manifest_csv_path, manifest_json_path, row):
    rows = read_manifest_rows(manifest_csv_path)
    rows.append(row)
    write_manifest_csv(manifest_csv_path, rows)
    write_manifest_json(manifest_json_path, rows)


def previous_ending_rank(manifest_path):
    rows = read_manifest_rows(manifest_path)
    if not rows:
        return ""
    return rows[-1].get("ranked_points_after", "")


def canonical_deck_version(deck_version):
    if not deck_version:
        return DEFAULT_DECK_VERSION
    deck_path = Path(deck_version)
    if deck_path.exists():
        return deck_version
    if deck_path.parts and deck_path.parts[0] == "deck":
        corrected = Path("decks", *deck_path.parts[1:])
        if corrected.exists():
            return str(corrected)
    return deck_version


def previous_deck_version(manifest_path):
    rows = read_manifest_rows(manifest_path)
    if not rows:
        return DEFAULT_DECK_VERSION
    return canonical_deck_version(rows[-1].get("deck_version", ""))


def main():
    parser = argparse.ArgumentParser(
        description="Paste a Pokemon TCG Live battle log and save it with match metadata."
    )
    parser.add_argument("--logs-dir", default=DEFAULT_LOGS_DIR, type=Path)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST, type=Path)
    parser.add_argument("--manifest-json", default=DEFAULT_MANIFEST_JSON, type=Path)
    parser.add_argument("--deck-version", default="")
    parser.add_argument("--filename", help="Override the generated log filename.")
    parser.add_argument("--player", default=DEFAULT_PLAYER)
    parser.add_argument("--source", default="terminal_paste")
    parser.add_argument("--quiet", action="store_true", help="Suppress post-import command suggestions.")
    args = parser.parse_args()

    args.logs_dir.mkdir(parents=True, exist_ok=True)
    imported_at = datetime.now().astimezone().isoformat(timespec="seconds")
    default_match_date = datetime.now().strftime("%Y-%m-%d")

    print("Project Arceus Log Import")
    log_text = read_pasted_log()
    if not log_text.strip():
        print("No log text received. Nothing was saved.", file=sys.stderr)
        return 1

    inferred = infer_log_metadata(log_text, args.player)

    print()
    print("Inferred from log:")
    print(f"  Opponent: {inferred['opponent'] or 'unknown'}")
    print(f"  Result: {inferred['result']}")
    print(f"  Went first: {inferred['went_first']}")
    print(f"  Concession: {inferred['conceded']}")

    print()
    print("Now add the remaining match metadata. Press Enter to accept defaults.")
    match_date = ask("Match date", default_match_date)
    deck_version = ask("Deck version", args.deck_version or previous_deck_version(args.manifest))
    ranked_before = ask("Ranked points before", previous_ending_rank(args.manifest))
    ranked_after = ask("Ranked points after")
    notes = ask("Short notes")

    game_number = next_game_number(args.logs_dir)
    filename = args.filename or build_filename(
        game_number,
        match_date,
        inferred["result"],
        inferred["opponent"],
        deck_version,
        inferred["conceded"],
    )
    if not filename.endswith(".txt"):
        filename += ".txt"
    log_path = unique_path(args.logs_dir / filename)

    log_path.write_text(log_text, encoding="utf-8")

    row = {
        "imported_at": imported_at,
        "match_date": match_date,
        "log_file": str(log_path),
        "game_id": log_path.stem,
        "deck_version": deck_version,
        "opponent": inferred["opponent"],
        "result": inferred["result"],
        "went_first": inferred["went_first"],
        "conceded": inferred["conceded"],
        "ranked_points_before": ranked_before,
        "ranked_points_after": ranked_after,
        "source": args.source,
        "notes": notes,
    }
    append_manifest(args.manifest, args.manifest_json, row)

    if not args.quiet:
        print()
        print(f"Saved Game {game_number}: {inferred['result']} vs {inferred['opponent'] or 'unknown'}")
        print(f"Saved log: {log_path}")
        print(f"Updated manifest: {args.manifest}")
        print(f"Updated JSON manifest: {args.manifest_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
