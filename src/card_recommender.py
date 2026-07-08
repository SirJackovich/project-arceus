"""Standard card candidate search for Project Arceus deck reviews."""

import json
import re
import unicodedata
from pathlib import Path
from typing import Iterable, Optional


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

DEFAULT_REVIEW_PROBLEMS = ["rebuild after KO", "missing evolution access", "missing Basic setup"]
LOCKED_CORE_CARDS = {
    "Mankey",
    "Primeape",
    "Annihilape",
    "Risky Ruins",
    "Fighting Gong",
    "Buddy-Buddy Poffin",
    "Basic {F} Energy",
    "Basic Fighting Energy",
}
QUESTIONED_CARDS = {"Energy Switch", "Poke Pad", "Tarragon", "Colress's Tenacity"}
DEFAULT_REJECTED_CARDS = {"Salvatore"}


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


def rejected_cards(experiment: Optional[dict]) -> set[str]:
    rejected = set(DEFAULT_REJECTED_CARDS)
    if experiment:
        rejected.update(str(card) for card in experiment.get("rejected_cards", []) if card)
        reconsiderable = {str(card) for card in experiment.get("reconsiderable_cards", []) if card}
        rejected -= reconsiderable
    return rejected


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


def problem_evidence_score(problem: str, evidence: dict) -> tuple[int, list[dict]]:
    score = 0
    rows = []
    for factor in evidence.get("possible_loss_factors", []):
        text = f"{factor.get('factor', '')} {factor.get('category', '')}".lower()
        for needle, mapped_problem in FACTOR_PROBLEM_MAP:
            if mapped_problem == problem and needle in text:
                count = int(factor.get("count", 0) or 0)
                score += count or 1
                rows.append(factor)
                break
    for goal in evidence.get("success_conditions", []):
        text = f"{goal.get('goal_id', '')} {goal.get('goal_group', '')} {goal.get('condition', '')}".lower()
        for needle, mapped_problem in FACTOR_PROBLEM_MAP:
            if mapped_problem == problem and needle in text:
                missed = int(goal.get("missed", 0) or 0)
                score += missed or 1
                rows.append(goal)
                break
    return score, rows[:5]


def infer_top_problems(evidence: dict, limit: int = 3) -> list[dict]:
    problems = []
    for problem in DEFAULT_REVIEW_PROBLEMS:
        score, rows = problem_evidence_score(problem, evidence)
        problems.append({
            "problem": problem,
            "score": score,
            "source": "detected" if score else "review_default",
            "evidence": rows,
        })
    problems.sort(key=lambda row: (-row["score"], DEFAULT_REVIEW_PROBLEMS.index(row["problem"])))
    return problems[:limit]


def text_sources(card: dict) -> list[str]:
    sources = list(card.get("rules", []))
    for ability in card.get("abilities", []):
        sources.append(f"{ability.get('name', '')}: {ability.get('text', '')}".strip(": "))
    for attack in card.get("attacks", []):
        sources.append(f"{attack.get('name', '')}: {attack.get('text', '')}".strip(": "))
    return [source for source in sources if source]


def matched_text(card: dict, keywords: Iterable[str]) -> list[str]:
    matches = []
    normalized_keywords = [keyword.lower() for keyword in keywords]
    for source in text_sources(card):
        normalized_source = unicodedata.normalize("NFKD", source.lower())
        normalized_source = "".join(char for char in normalized_source if not unicodedata.combining(char))
        if any(keyword in normalized_source for keyword in normalized_keywords):
            matches.append(source)
    return matches[:3]


def score_card(card: dict, problem: str, current_deck: list[dict]) -> tuple[int, list[str], list[str]]:
    if problem in {"missing evolution access", "rebuild after KO"} and card.get("supertype") == "Pokémon":
        return 0, ["Pokemon support would add setup cost for this problem"], []
    query = PROBLEM_QUERIES[problem]
    text = card_text(card)
    if not any(anchor in text for anchor in query.get("anchors", [])):
        return 0, ["does not match problem anchor"], []
    if problem == "missing evolution access" and "mega evolution" in text:
        return 0, ["Mega Evolution search does not fit current Annihilape line"], []
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
    return score, reasons[:5], matched_text(card, query["keywords"])


def card_tracking_by_name(evidence: dict) -> dict:
    return {row.get("card_name"): row for row in evidence.get("card_tracking", []) if row.get("card_name")}


def role_for_deck_entry(entry: dict) -> str:
    name = entry.get("name", "")
    category = entry.get("category", "")
    if category == "Energy":
        return "energy"
    if category == "Pokemon":
        return "pokemon"
    if name in {"Lillie's Determination", "Hilda", "Colress's Tenacity", "Waitress", "Tarragon"}:
        return "supporter"
    if name in {"Energy Switch", "Dawn", "Waitress"}:
        return "energy tempo"
    if name in {"Pokegear 3.0", "Poke Pad", "Hilda", "Colress's Tenacity"}:
        return "search/consistency"
    if name in {"Night Stretcher"}:
        return "recovery"
    if name in {"Air Balloon"}:
        return "mobility"
    return category.lower() or "unknown"


def scored_cuts(evidence: dict, current_deck: list[dict]) -> list[dict]:
    tracking = card_tracking_by_name(evidence)
    role_counts = {}
    for entry in current_deck:
        role = role_for_deck_entry(entry)
        role_counts[role] = role_counts.get(role, 0) + int(entry.get("count", 0) or 0)

    cuts = []
    for entry in current_deck:
        name = entry.get("name", "")
        count = int(entry.get("count", 0) or 0)
        if count <= 0 or name in LOCKED_CORE_CARDS:
            continue
        stats = tracking.get(name, {})
        played = int(stats.get("played", 0) or 0)
        activated = int(stats.get("activated_triggered", 0) or 0)
        searched = int(stats.get("searched_fetched", 0) or 0)
        stuck = int(stats.get("stuck_in_hand_unused", 0) or 0)
        role = role_for_deck_entry(entry)
        score = 0
        reasons = []
        if played <= count * 2:
            score += 3
            reasons.append("low visible usage")
        if activated + searched == 0:
            score += 2
            reasons.append("low visible impact")
        if role_counts.get(role, 0) > count:
            score += 1
            reasons.append(f"redundant {role} role")
        if name in QUESTIONED_CARDS:
            score += 2
            reasons.append("already questioned card")
        if stuck:
            score += 1
            reasons.append("sometimes stuck/unused")
        if count > 1:
            score += 1
            reasons.append("can trim without removing all copies")
        if not reasons:
            reasons.append("non-core flex slot; verify with Deck Coach")
        cuts.append({
            "name": name,
            "count": 1 if count == 1 else 1,
            "score": score,
            "slot": entry.get("category", ""),
            "role": role,
            "reasons": reasons[:4],
        })
    cuts.sort(key=lambda row: (-row["score"], row["name"]))
    return cuts[:8]


def search_candidates(evidence: dict, deck: dict, card_db: list[dict], max_cards: int = 12, experiment: Optional[dict] = None) -> dict:
    problems = infer_top_problems(evidence, limit=3)
    top_problem = {"problem": problems[0]["problem"], "source": problems[0]["source"], "evidence": problems[0]["evidence"]}
    current_deck = deck_cards(deck)
    rejected = rejected_cards(experiment)
    excluded = []
    grouped = []
    flat_rows = []
    per_problem_limit = max(3, min(5, max_cards // max(1, len(problems)) + 1))
    for problem in problems:
        scored = []
        for card in card_db:
            if card.get("name", "") in rejected:
                if card.get("name", "") not in excluded:
                    excluded.append(card.get("name", ""))
                continue
            score, reasons, matches = score_card(card, problem["problem"], current_deck)
            if score <= 0:
                continue
            scored.append({
                "card": card,
                "score": score + problem.get("score", 0),
                "why_candidate": reasons,
                "matched_text": matches,
                "problem_solved": problem["problem"],
                "standard_legality": "legal" if is_standard_legal(card) else "not legal",
                "fit_notes": fit_notes(card),
            })
        scored.sort(key=lambda row: (-row["score"], row["card"].get("name", ""), row["card"].get("number", "")))
        unique = unique_card_rows(scored, per_problem_limit)
        grouped.append({
            "problem": problem["problem"],
            "problem_score": problem["score"],
            "evidence": problem["evidence"],
            "candidates": [candidate_summary(row) for row in unique],
        })
        flat_rows.extend(unique)

    flat_rows = include_authoritative_candidate(flat_rows, card_db, current_deck, experiment)
    candidates = [candidate_summary(row) for row in unique_card_rows(flat_rows, max_cards)]
    return {
        "top_problem": top_problem,
        "top_problems": problems,
        "problem_count": len(problems),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "candidate_groups": grouped,
        "suggested_cuts": scored_cuts(evidence, current_deck),
        "excluded_cards": [{"name": name, "reason": "previously rejected; not reconsiderable in experiment memory"} for name in sorted(excluded)],
        "change_size_rule": "Prefer 1-2 card changes. If no candidate clearly improves the problem, recommend no change.",
    }


def unique_card_rows(rows: list[dict], limit: int) -> list[dict]:
    unique = []
    seen_names = set()
    for row in rows:
        name = row["card"].get("name", "")
        if name in seen_names:
            continue
        seen_names.add(name)
        unique.append(row)
        if len(unique) >= limit:
            break
    return unique


def include_authoritative_candidate(rows: list[dict], card_db: list[dict], current_deck: list[dict], experiment: Optional[dict]) -> list[dict]:
    text = (experiment or {}).get("next_experiment", "").lower()
    if "lana" not in text:
        return rows
    for row in rows:
        if row["card"].get("name") == "Lana's Aid":
            row["score"] += 100
            if "included by current experiment next_experiment sanity rule" not in row["why_candidate"]:
                row["why_candidate"].append("included by current experiment next_experiment sanity rule")
            rows.sort(key=lambda item: (-item["score"], item["card"].get("name", ""), item["card"].get("number", "")))
            return rows
    for card in card_db:
        if card.get("name") != "Lana's Aid":
            continue
        score, reasons, matches = score_card(card, "rebuild after KO", current_deck)
        rows.append({
            "card": card,
            "score": max(score, 1) + 100,
            "why_candidate": reasons + ["included by current experiment next_experiment sanity rule"],
            "matched_text": matches,
            "problem_solved": "rebuild after KO",
            "standard_legality": "legal" if is_standard_legal(card) else "not legal",
            "fit_notes": fit_notes(card),
        })
        break
    rows.sort(key=lambda row: (-row["score"], row["card"].get("name", ""), row["card"].get("number", "")))
    return rows


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


def may_not_fit_notes(card: dict) -> list[str]:
    text = card_text(card)
    notes = []
    if card_type(card) == "Supporter":
        notes.append("uses the once-per-turn Supporter slot")
    if card_type(card) == "Stadium":
        notes.append("competes with Risky Ruins for the Stadium in play")
    if card.get("supertype") == "Pokémon":
        notes.append("adds a Bench/setup obligation")
    if "discard" in text and "from your discard" not in text:
        notes.append("may require discarding resources")
    return notes or ["no obvious Annihilape-specific conflict from text"]


def risky_ruins_conflict(card: dict) -> str:
    text = card_text(card)
    if card_type(card) == "Stadium":
        return "yes - Stadium slot competes with Risky Ruins"
    if "remove" in text and "damage counter" in text:
        return "possible - may undo damage-counter math"
    return "no obvious conflict"


def why_solves_problem(card: dict, problem: str) -> str:
    if problem == "rebuild after KO":
        return "recovers Pokemon and/or Energy resources after an attacker is KO'd."
    if problem == "missing evolution access":
        return "improves access to evolution pieces or evolution-search lines."
    if problem == "missing Basic setup":
        return "improves early Basic Pokemon setup or Bench development."
    return f"matches text associated with {problem}."


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
        "slot_cost": card_type(card),
        "problem_solved": row["problem_solved"],
        "exact_matched_text": row.get("matched_text", []),
        "why_it_solves_problem": why_solves_problem(card, row["problem_solved"]),
        "why_it_may_not_fit_annihilape": may_not_fit_notes(card),
        "risky_ruins_conflict": risky_ruins_conflict(card),
        "why_candidate": row["why_candidate"],
        "fit_notes": row["fit_notes"],
        "rules": card.get("rules", []),
        "abilities": card.get("abilities", []),
        "attacks": card.get("attacks", []),
    }
