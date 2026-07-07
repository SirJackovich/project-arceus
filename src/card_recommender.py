"""Standard card candidate search for Project Arceus deck reviews."""

import json
import re
import unicodedata
from pathlib import Path
from typing import Iterable


STANDARD_REGULATION_MARKS = {"H", "I", "J"}

PROBLEM_QUERIES = {
    "rebuild after KO": {
        "keywords": ["from your discard", "put into your hand", "evolution", "evolve", "pokemon from your discard", "basic energy from your discard", "shuffle"],
        "anchors": ["from your discard", "pokemon from your discard", "basic energy from your discard"],
        "prefer": ["Supporter", "Item", "Pokémon Tool"],
    },
    "missing Basic setup": {
        "keywords": ["basic pokemon", "bench", "put it onto your bench", "search your deck for a basic", "70 hp or less"],
        "anchors": ["basic pokemon", "put it onto your bench", "70 hp or less"],
        "prefer": ["Item", "Supporter"],
    },
    "missing evolution access": {
        "keywords": ["evolution pokemon", "evolves from", "rare candy", "search your deck for", "put it into your hand", "into your hand", "from your discard", "pokemon that don't have a rule box", "evolve"],
        "anchors": ["evolution pokemon", "evolves from", "rare candy", "from your discard", "pokemon that don't have a rule box", "evolve"],
        "prefer": ["Item", "Supporter"],
    },
    "energy tempo": {
        "keywords": ["attach", "energy", "basic energy", "from your discard", "to 1 of your pokemon", "switch energy"],
        "anchors": ["attach", "energy", "basic energy"],
        "prefer": ["Item", "Supporter", "Energy"],
    },
    "stadium access": {
        "keywords": ["stadium", "search your deck for a stadium", "discard a stadium", "put it into your hand"],
        "anchors": ["stadium"],
        "prefer": ["Item", "Supporter"],
    },
    "bench damage/counters": {
        "keywords": ["damage counter", "put damage counters", "benched pokemon", "each of your opponent", "spread"],
        "anchors": ["damage counter", "put damage counters", "benched pokemon"],
        "prefer": ["Pokémon", "Item", "Stadium"],
    },
    "bad active/retreat issue": {
        "keywords": ["retreat", "switch", "active pokemon", "free retreat", "move", "bench"],
        "anchors": ["retreat", "switch", "active pokemon"],
        "prefer": ["Item", "Pokémon Tool", "Supporter"],
    },
}

FACTOR_PROBLEM_MAP = [
    ("no visible rebuild", "rebuild after KO"),
    ("rebuild", "rebuild after KO"),
    ("unknown/no visible mankey", "missing Basic setup"),
    ("open with mankey", "missing Basic setup"),
    ("missing mankey", "missing Basic setup"),
    ("missing annihilape", "missing evolution access"),
    ("missing primeape", "missing evolution access"),
    ("evolution", "missing evolution access"),
    ("energy", "energy tempo"),
    ("risky ruins", "stadium access"),
    ("stadium", "stadium access"),
    ("damage counter", "bench damage/counters"),
    ("retreat", "bad active/retreat issue"),
    ("active", "bad active/retreat issue"),
]


def load_json(path: str, default=None):
    path_obj = Path(path)
    if not path_obj.exists():
        return default
    return json.loads(path_obj.read_text(encoding="utf-8"))


def card_text(card: dict) -> str:
    parts = [card.get("name", ""), card.get("supertype", ""), " ".join(card.get("subtypes", [])), " ".join(card.get("rules", []))]
    for ability in card.get("abilities", []):
        parts.extend([ability.get("name", ""), ability.get("text", "")])
    for attack in card.get("attacks", []):
        parts.extend([attack.get("name", ""), attack.get("text", ""), " ".join(attack.get("cost", []))])
    raw = " ".join(str(part) for part in parts if part).lower()
    normalized = unicodedata.normalize("NFKD", raw)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def card_type(card: dict) -> str:
    subtypes = card.get("subtypes", [])
    if card.get("supertype") == "Trainer" and subtypes:
        return subtypes[0]
    return card.get("supertype", "")


def is_standard_legal(card: dict) -> bool:
    mark = card.get("regulation_mark") or card.get("regulationMark") or ""
    if mark in STANDARD_REGULATION_MARKS:
        return True
    return bool(card.get("standard_legal_by_regulation_mark"))


def normalize_card(raw: dict) -> dict:
    set_data = raw.get("set", {}) or {}
    return {
        "name": raw.get("name", ""),
        "id": raw.get("id", ""),
        "supertype": raw.get("supertype", ""),
        "subtypes": raw.get("subtypes", []),
        "hp": raw.get("hp", ""),
        "types": raw.get("types", []),
        "rules": raw.get("rules", []),
        "abilities": raw.get("abilities", []),
        "attacks": raw.get("attacks", []),
        "retreat_cost": raw.get("retreat_cost", raw.get("retreatCost", [])),
        "converted_retreat_cost": raw.get("converted_retreat_cost", raw.get("convertedRetreatCost", "")),
        "set": {
            "id": set_data.get("id", ""),
            "name": set_data.get("name", ""),
            "ptcgo_code": set_data.get("ptcgo_code", set_data.get("ptcgoCode", "")),
            "release_date": set_data.get("release_date", set_data.get("releaseDate", "")),
        },
        "number": raw.get("number", ""),
        "rarity": raw.get("rarity", ""),
        "regulation_mark": raw.get("regulation_mark", raw.get("regulationMark", "")),
        "standard_legal_by_regulation_mark": is_standard_legal(raw),
    }


def load_card_database(path: str) -> list[dict]:
    payload = load_json(path, {}) or {}
    cards = payload.get("cards", payload if isinstance(payload, list) else [])
    return [normalize_card(card) for card in cards if is_standard_legal(card)]


def deck_cards(deck: dict) -> list[dict]:
    return deck.get("cards", []) if isinstance(deck, dict) else []


def card_key(card: dict) -> tuple[str, str, str]:
    set_data = card.get("set", {}) or {}
    return (card.get("name", ""), set_data.get("ptcgo_code", card.get("set", "")), str(card.get("number", "")))


def deck_key(entry: dict) -> tuple[str, str, str]:
    return (entry.get("name", ""), entry.get("set", ""), str(entry.get("number", "")))


def infer_top_problem(evidence: dict) -> dict:
    factors = evidence.get("possible_loss_factors", [])
    for factor in factors:
        text = f"{factor.get('factor', '')} {factor.get('category', '')}".lower()
        for needle, problem in FACTOR_PROBLEM_MAP:
            if needle in text:
                return {"problem": problem, "source": "possible_loss_factors", "evidence": factor}

    goals = sorted(evidence.get("success_conditions", []), key=lambda row: int(row.get("missed", 0) or 0), reverse=True)
    for goal in goals:
        text = f"{goal.get('goal_id', '')} {goal.get('goal_group', '')} {goal.get('condition', '')}".lower()
        for needle, problem in FACTOR_PROBLEM_MAP:
            if needle in text:
                return {"problem": problem, "source": "success_conditions", "evidence": goal}
    return {"problem": "rebuild after KO", "source": "fallback", "evidence": {}}


def score_card(card: dict, problem: str, current_deck: list[dict]) -> tuple[int, list[str]]:
    if problem in {"missing evolution access", "rebuild after KO"} and card.get("supertype") == "Pokémon":
        return 0, ["Pokemon support would add setup cost for this problem"]
    query = PROBLEM_QUERIES[problem]
    text = card_text(card)
    if not any(anchor in text for anchor in query.get("anchors", [])):
        return 0, ["does not match problem anchor"]
    if problem == "missing evolution access" and "mega evolution" in text:
        return 0, ["Mega Evolution search does not fit current Annihilape line"]
    reasons = []
    score = 0
    for keyword in query["keywords"]:
        if keyword in text:
            score += 4 if len(keyword.split()) > 1 else 2
            reasons.append(f"matches '{keyword}'")
    if card_type(card) in query.get("prefer", []):
        score += 2
        reasons.append(f"preferred type {card_type(card)}")
    if deck_key({"name": card.get("name", ""), "set": card.get("set", {}).get("ptcgo_code", ""), "number": card.get("number", "")}) in {deck_key(entry) for entry in current_deck}:
        score -= 3
        reasons.append("already in deck")
    if card.get("supertype") == "Pokémon" and "Stage 2" in card.get("subtypes", []):
        score -= 2
        reasons.append("higher setup cost")
    return score, reasons[:5]


def suggested_cuts(problem: str, current_deck: list[dict]) -> list[dict]:
    names = ["Energy Switch", "Poke Pad", "Colress's Tenacity", "Tarragon", "Hilda"]
    if problem == "stadium access":
        names = ["Energy Switch", "Poke Pad", "Tarragon"]
    if problem == "bad active/retreat issue":
        names = ["Energy Switch", "Colress's Tenacity", "Tarragon"]
    cuts = []
    for name in names:
        for entry in current_deck:
            if entry.get("name") == name and int(entry.get("count", 0)) > 0:
                cuts.append({"name": name, "count": 1, "reason": "small-change candidate; verify with Deck Coach"})
                break
        if len(cuts) >= 3:
            break
    return cuts


def search_candidates(evidence: dict, deck: dict, card_db: list[dict], max_cards: int = 5) -> dict:
    problem = infer_top_problem(evidence)
    current_deck = deck_cards(deck)
    scored = []
    for card in card_db:
        score, reasons = score_card(card, problem["problem"], current_deck)
        if score <= 0:
            continue
        scored.append({
            "card": card,
            "score": score,
            "why_candidate": reasons,
            "problem_solved": problem["problem"],
            "standard_legality": "legal" if is_standard_legal(card) else "not legal",
            "fit_notes": fit_notes(card),
        })
    scored.sort(key=lambda row: (-row["score"], row["card"].get("name", ""), row["card"].get("number", "")))
    unique = []
    seen_names = set()
    for row in scored:
        name = row["card"].get("name", "")
        if name in seen_names:
            continue
        seen_names.add(name)
        unique.append(row)
        if len(unique) >= max_cards:
            break
    candidates = [candidate_summary(row) for row in unique]
    return {
        "top_problem": problem,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "suggested_cuts": suggested_cuts(problem["problem"], current_deck),
        "change_size_rule": "Prefer 1-2 card changes. If no candidate clearly improves the problem, recommend no change.",
    }


def fit_notes(card: dict) -> list[str]:
    text = card_text(card)
    notes = []
    if "damage counter" in text:
        notes.append("may interact with Annihilape damage math")
    if "from your discard" in text:
        notes.append("rebuild/discard recovery angle")
    if "stadium" in text:
        notes.append("check conflict with Risky Ruins")
    if "switch" in text or "retreat" in text:
        notes.append("active/retreat utility")
    return notes


def candidate_summary(row: dict) -> dict:
    card = row["card"]
    set_data = card.get("set", {})
    return {
        "name": card.get("name", ""),
        "set": set_data.get("ptcgo_code") or set_data.get("id", ""),
        "number": card.get("number", ""),
        "type": card_type(card),
        "regulation_mark": card.get("regulation_mark", ""),
        "standard_legality": row["standard_legality"],
        "score": row["score"],
        "why_candidate": row["why_candidate"],
        "fit_notes": row["fit_notes"],
        "rules": card.get("rules", []),
        "abilities": card.get("abilities", []),
        "attacks": card.get("attacks", []),
    }
