import json
from pathlib import Path

from src.card_recommender import infer_top_problem, infer_top_problems, load_card_database, search_candidates


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


def test_search_candidates_groups_top_three_problem_lanes() -> None:
    cards = load_card_database(str(FIXTURES / "standard_cards.json"))
    deck = {"cards": [{"name": "Energy Switch", "set": "MEG", "number": "115", "count": 2}]}
    evidence = {
        "possible_loss_factors": [
            {"factor": "no visible rebuild after line break", "category": "rebuild", "count": 2},
            {"factor": "missing Annihilape", "category": "evolution bottleneck", "count": 3},
            {"factor": "unknown/no visible Mankey", "category": "evolution bottleneck", "count": 1},
        ]
    }

    result = search_candidates(evidence, deck, cards, max_cards=12)

    assert [problem["problem"] for problem in infer_top_problems(evidence)] == [
        "missing evolution access",
        "rebuild after KO",
        "missing Basic setup",
    ]
    grouped_problems = {group["problem"] for group in result["candidate_groups"]}
    assert {"rebuild after KO", "missing evolution access", "missing Basic setup"} <= grouped_problems
    candidates = result["candidates"]
    assert any(candidate["name"] == "Brock's Scouting" for candidate in candidates)
    lana = next(candidate for candidate in candidates if candidate["name"] == "Lana's Aid")
    assert lana["exact_matched_text"]
    assert lana["slot_cost"] == "Supporter"
    assert lana["risky_ruins_conflict"] == "no obvious conflict"


def test_lana_aid_is_included_when_current_experiment_names_it() -> None:
    cards = load_card_database(str(FIXTURES / "standard_cards.json"))
    deck = {"cards": [{"name": "Energy Switch", "set": "MEG", "number": "115", "count": 2}]}
    evidence = {"possible_loss_factors": [{"factor": "missing Annihilape", "category": "evolution bottleneck", "count": 5}]}
    experiment = {"next_experiment": "Test Lana's Aid replacing Energy Switch."}

    result = search_candidates(evidence, deck, cards, max_cards=1, experiment=experiment)

    assert [candidate["name"] for candidate in result["candidates"]] == ["Lana's Aid"]


def test_rejected_cards_are_excluded_unless_reconsiderable() -> None:
    cards = load_card_database(str(FIXTURES / "standard_cards.json"))
    deck = {"cards": []}
    evidence = {"possible_loss_factors": [{"factor": "missing Annihilape", "category": "evolution bottleneck", "count": 5}]}

    blocked = search_candidates(evidence, deck, cards, max_cards=12, experiment={})
    reconsidered = search_candidates(evidence, deck, cards, max_cards=12, experiment={"reconsiderable_cards": ["Salvatore"]})

    assert "Salvatore" not in [candidate["name"] for candidate in blocked["candidates"]]
    assert blocked["excluded_cards"] == [{"name": "Salvatore", "reason": "previously rejected; not reconsiderable in experiment memory"}]
    assert "Salvatore" in [candidate["name"] for candidate in reconsidered["candidates"]]


def test_recommendation_payload_is_json_serializable() -> None:
    cards = load_card_database(str(FIXTURES / "standard_cards.json"))
    result = search_candidates({"possible_loss_factors": []}, {"cards": []}, cards, max_cards=5)

    json.dumps(result)
