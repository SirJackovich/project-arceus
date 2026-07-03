#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path


API_URL = "https://api.pokemontcg.io/v2/cards"
STANDARD_REGULATION_MARKS = {"H", "I", "J"}


def fetch_card(set_code, number, name):
    lookup_name = normalize_lookup_name(name)
    query = f"set.ptcgoCode:{set_code} number:{number}"
    url = f"{API_URL}?q={urllib.parse.quote(query)}"
    result = curl_json(url)
    payload = json.loads(result.stdout)
    data = payload.get("data", [])
    if not data:
        fallback_query = f'name:"{lookup_name}" number:{number}'
        fallback_url = f"{API_URL}?q={urllib.parse.quote(fallback_query)}"
        fallback = curl_json(fallback_url)
        payload = json.loads(fallback.stdout)
        data = payload.get("data", [])
    return data[0] if data else None


def normalize_lookup_name(name):
    return {
        "Basic {F} Energy": "Basic Fighting Energy",
    }.get(name, name)


def curl_json(url):
    last_error = None
    for attempt in range(1, 4):
        result = subprocess.run(
            ["curl", "-s", "--max-time", "20", url],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result
        last_error = subprocess.CalledProcessError(
            result.returncode,
            result.args,
            output=result.stdout,
            stderr=result.stderr,
        )
        time.sleep(attempt)
    raise last_error


def summarize_card(entry, card):
    attacks = []
    for attack in card.get("attacks", []):
        attacks.append({
            "name": attack.get("name", ""),
            "cost": attack.get("cost", []),
            "converted_energy_cost": attack.get("convertedEnergyCost", ""),
            "damage": attack.get("damage", ""),
            "text": attack.get("text", ""),
        })
    abilities = []
    for ability in card.get("abilities", []):
        abilities.append({
            "name": ability.get("name", ""),
            "type": ability.get("type", ""),
            "text": ability.get("text", ""),
        })
    summarized = {
        "deck_count": entry["count"],
        "deck_category": entry["category"],
        "requested_name": entry["name"],
        "name": card.get("name", entry["name"]),
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
        "number": card.get("number", entry["number"]),
        "rarity": card.get("rarity", ""),
        "regulation_mark": card.get("regulationMark", ""),
        "legalities": card.get("legalities", {}),
        "images": card.get("images", {}),
    }
    return apply_standard_legality(summarized)


def apply_standard_legality(card):
    regulation_mark = card.get("regulation_mark", "")
    raw_standard = card.get("legalities", {}).get("standard", "")
    is_basic_energy = card.get("supertype") == "Energy" and "Basic" in card.get("subtypes", [])
    card["api_standard_legality"] = raw_standard
    card["standard_legal_by_regulation_mark"] = (
        regulation_mark in STANDARD_REGULATION_MARKS
        or (is_basic_energy and raw_standard == "Legal")
    )
    if regulation_mark:
        basis = f"regulation mark {regulation_mark}"
    elif is_basic_energy:
        basis = "Basic Energy with API Standard legality"
    else:
        basis = "missing regulation mark"
    card["standard_legality_basis"] = basis
    return card


def markdown(details):
    lines = ["# Monkey Deck Card Details", ""]
    for card in details["cards"]:
        display_set = card["set"].get("ptcgo_code") or card["set"].get("id", "").upper()
        heading = f"## {card['deck_count']}x {card['name']} ({display_set} {card['number']})"
        lines.extend([heading, ""])
        meta = []
        if card["supertype"]:
            meta.append(card["supertype"])
        if card["subtypes"]:
            meta.append(", ".join(card["subtypes"]))
        if card["hp"]:
            meta.append(f"HP {card['hp']}")
        if card["types"]:
            meta.append("/".join(card["types"]))
        if meta:
            lines.extend([f"- {' | '.join(meta)}", ""])
        if card["abilities"]:
            lines.append("### Abilities")
            for ability in card["abilities"]:
                ability_type = f" ({ability['type']})" if ability["type"] else ""
                lines.append(f"- **{ability['name']}**{ability_type}: {ability['text']}")
            lines.append("")
        if card["attacks"]:
            lines.append("### Attacks")
            for attack in card["attacks"]:
                cost = ", ".join(attack["cost"]) if attack["cost"] else "None"
                damage = attack["damage"] or "-"
                text = f" {attack['text']}" if attack["text"] else ""
                lines.append(f"- **{attack['name']}** [{cost}] Damage: {damage}.{text}")
            lines.append("")
        if card["rules"]:
            lines.append("### Rules/Text")
            for rule in card["rules"]:
                lines.append(f"- {rule}")
            lines.append("")
        raw_legal = card.get("api_standard_legality", card.get("legalities", {}).get("standard", ""))
        derived_legal = "Legal" if card.get("standard_legal_by_regulation_mark") else "Not Legal"
        lines.append(f"- Standard by regulation mark: {derived_legal}")
        if raw_legal:
            lines.append(f"- API Standard value: {raw_legal}")
        if card.get("standard_legality_basis"):
            lines.append(f"- Standard basis: {card['standard_legality_basis']}")
        if card["regulation_mark"]:
            lines.append(f"- Regulation mark: {card['regulation_mark']}")
        if card["images"].get("large"):
            lines.append(f"- Image: {card['images']['large']}")
        lines.append("")
    if details["missing"]:
        lines.extend(["## Missing Lookups", ""])
        for missing in details["missing"]:
            lines.append(f"- {missing['count']}x {missing['name']} ({missing['set']} {missing['number']})")
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--deck", default="decks/annihilape/v01.json")
    parser.add_argument("--output-json", default="decks/annihilape/card_details.json")
    parser.add_argument("--output-md", default="decks/annihilape/card_details.md")
    args = parser.parse_args()

    deck = json.loads(Path(args.deck).read_text(encoding="utf-8"))
    existing_by_key = {}
    output_json_path = Path(args.output_json)
    if output_json_path.exists():
        existing = json.loads(output_json_path.read_text(encoding="utf-8"))
        existing_by_name_number = {}
        for card in existing.get("cards", []):
            key = (card.get("requested_name", card.get("name", "")), card.get("set", {}).get("ptcgo_code", ""), card.get("number", ""))
            existing_by_key[key] = card
            existing_by_name_number[(card.get("requested_name", card.get("name", "")), card.get("number", ""))] = card
    details = {
        "source": "https://api.pokemontcg.io/v2/cards",
        "deck": deck["name"],
        "cards": [],
        "missing": [],
    }
    for entry in deck["cards"]:
        existing_key = (entry["name"], entry["set"], entry["number"])
        if existing_key in existing_by_key:
            details["cards"].append(apply_standard_legality(existing_by_key[existing_key]))
            print(f"Using cached {entry['name']} {entry['set']} {entry['number']}.", flush=True)
            continue
        existing_name_number = (entry["name"], entry["number"])
        if existing_name_number in existing_by_name_number:
            details["cards"].append(apply_standard_legality(existing_by_name_number[existing_name_number]))
            print(f"Using cached {entry['name']} {entry['number']}.", flush=True)
            continue
        print(f"Fetching {entry['name']} {entry['set']} {entry['number']}...", flush=True)
        card = fetch_card(entry["set"], entry["number"], entry["name"])
        if not card:
            details["missing"].append(entry)
            continue
        details["cards"].append(summarize_card(entry, card))

    Path(args.output_json).write_text(json.dumps(details, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    Path(args.output_md).write_text(markdown(details), encoding="utf-8")
    print(json.dumps({
        "cards_found": len(details["cards"]),
        "missing": len(details["missing"]),
        "output_json": str(Path(args.output_json).resolve()),
        "output_md": str(Path(args.output_md).resolve()),
    }, indent=2))
    if details["missing"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
