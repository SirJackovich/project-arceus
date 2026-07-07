import json
from pathlib import Path

from src.card_recommender import infer_top_problem, load_card_database, search_candidates


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_infers_rebuild_problem_from_loss_factors() -> None:
    evidence = {"possible_loss_factors": [{"factor": "no visible rebuild after line break", "category": "rebuild"}]}

    assert infer_top_problem(evidence)["problem"] == "rebuild after KO"


def test_search_candidates_filters_to_standard_and_caps_results() -> None:
    cards = load_card_database(str(FIXTURES / "standard_cards.json"))
    deck = {"cards": [{"name": "Energy Switch", "set": "MEG", "number": "115", "count": 2}]}
    evidence = {"possible_loss_factors": [{"factor": "no visible rebuild after line break", "category": "rebuild"}]}

    result = search_candidates(evidence, deck, cards, max_cards=5)

    names = [candidate["name"] for candidate in result["candidates"]]
    assert "Lana's Aid" in names
    assert "Ultra Ball" not in names
    assert result["candidate_count"] <= 5
    assert result["suggested_cuts"][0]["name"] == "Energy Switch"


def test_recommendation_payload_is_json_serializable() -> None:
    cards = load_card_database(str(FIXTURES / "standard_cards.json"))
    result = search_candidates({"possible_loss_factors": []}, {"cards": []}, cards, max_cards=5)

    json.dumps(result)
