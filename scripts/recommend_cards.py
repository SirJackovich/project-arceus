#!/usr/bin/env python3
"""Recommend Standard card candidates for the current Project Arceus deck problem."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ai_coaching import read_json, write_json
from src.card_recommender import load_card_database, search_candidates


def main() -> int:
    parser = argparse.ArgumentParser(description="Search the local Standard card DB for deck experiment candidates.")
    parser.add_argument("--evidence-json", default="data/analysis/deterministic_analysis.json")
    parser.add_argument("--deck", default="decks/annihilape/v01.json")
    parser.add_argument("--card-db", default="data/cards/standard_cards.json")
    parser.add_argument("--output-json", default="data/analysis/card_recommendations.json")
    parser.add_argument("--max-cards", type=int, default=5)
    args = parser.parse_args()

    evidence = read_json(args.evidence_json, {}) or {}
    deck = read_json(args.deck, {}) or {}
    cards = load_card_database(args.card_db)
    recommendations = search_candidates(evidence, deck, cards, args.max_cards)
    recommendations["card_database"] = args.card_db
    write_json(args.output_json, recommendations)
    print(json.dumps(recommendations, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
