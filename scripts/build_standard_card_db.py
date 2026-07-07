#!/usr/bin/env python3
"""Build a local Standard-format card database from the Pokemon TCG API."""

import argparse
import json
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path


API_URL = "https://api.pokemontcg.io/v2/cards"
STANDARD_REGULATION_MARKS = ["H", "I", "J"]


def curl_json(url: str) -> dict:
    last_error = None
    for attempt in range(1, 4):
        result = subprocess.run(["curl", "-s", "--max-time", "30", url], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
        last_error = subprocess.CalledProcessError(result.returncode, result.args, output=result.stdout, stderr=result.stderr)
        time.sleep(attempt)
    raise last_error


def summarize_card(card: dict) -> dict:
    attacks = [
        {
            "name": attack.get("name", ""),
            "cost": attack.get("cost", []),
            "converted_energy_cost": attack.get("convertedEnergyCost", ""),
            "damage": attack.get("damage", ""),
            "text": attack.get("text", ""),
        }
        for attack in card.get("attacks", [])
    ]
    abilities = [
        {
            "name": ability.get("name", ""),
            "type": ability.get("type", ""),
            "text": ability.get("text", ""),
        }
        for ability in card.get("abilities", [])
    ]
    return {
        "name": card.get("name", ""),
        "id": card.get("id", ""),
        "supertype": card.get("supertype", ""),
        "subtypes": card.get("subtypes", []),
        "hp": card.get("hp", ""),
        "types": card.get("types", []),
        "evolves_from": card.get("evolvesFrom", ""),
        "evolves_to": card.get("evolvesTo", []),
        "rules": card.get("rules", []),
        "abilities": abilities,
        "attacks": attacks,
        "weaknesses": card.get("weaknesses", []),
        "resistances": card.get("resistances", []),
        "retreat_cost": card.get("retreatCost", []),
        "converted_retreat_cost": card.get("convertedRetreatCost", ""),
        "set": {
            "id": card.get("set", {}).get("id", ""),
            "name": card.get("set", {}).get("name", ""),
            "ptcgo_code": card.get("set", {}).get("ptcgoCode", ""),
            "release_date": card.get("set", {}).get("releaseDate", ""),
        },
        "number": card.get("number", ""),
        "rarity": card.get("rarity", ""),
        "regulation_mark": card.get("regulationMark", ""),
        "legalities": card.get("legalities", {}),
        "standard_legal_by_regulation_mark": card.get("regulationMark", "") in STANDARD_REGULATION_MARKS,
        "standard_legality_basis": f"regulation mark {card.get('regulationMark', '')}",
    }


def fetch_mark(mark: str, page_size: int) -> list[dict]:
    cards = []
    page = 1
    while True:
        query = urllib.parse.quote(f"regulationMark:{mark}")
        url = f"{API_URL}?q={query}&pageSize={page_size}&page={page}"
        payload = curl_json(url)
        batch = payload.get("data", [])
        if not batch:
            break
        cards.extend(summarize_card(card) for card in batch)
        if len(cards) >= int(payload.get("totalCount", len(cards))):
            break
        page += 1
    return cards


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a local H/I/J Standard card database.")
    parser.add_argument("--output", default="data/cards/standard_cards.json")
    parser.add_argument("--page-size", type=int, default=250)
    parser.add_argument("--marks", nargs="+", default=STANDARD_REGULATION_MARKS)
    args = parser.parse_args()

    cards = []
    seen = set()
    for mark in args.marks:
        print(f"Fetching regulation mark {mark}...", flush=True)
        for card in fetch_mark(mark, args.page_size):
            key = card.get("id") or (card.get("name"), card.get("set", {}).get("id"), card.get("number"))
            if key in seen:
                continue
            seen.add(key)
            cards.append(card)
    output = {
        "source": API_URL,
        "standard_regulation_marks": args.marks,
        "cards": sorted(cards, key=lambda card: (card.get("name", ""), card.get("set", {}).get("id", ""), card.get("number", ""))),
    }
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"cards": len(cards), "output": str(path.resolve())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
