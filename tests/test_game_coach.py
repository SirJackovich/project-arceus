from scripts.game_coach import annihilape_timing_context


def test_late_annihilape_can_be_early_attacker_bought_time() -> None:
    context = annihilape_timing_context(
        {"game_id": "game_050_test", "result": "win"},
        [{"first_attack_turn": 5}],
        [{"attacker": "Hawlucha", "turn": 2, "prize_value": 1, "evidence": "Hawlucha took a prize."}],
        [],
        [],
    )

    assert context["classification"] == "early attacker successfully bought time"
    assert context["confidence"] == "high"


def test_late_annihilape_can_be_setup_failure() -> None:
    context = annihilape_timing_context(
        {"game_id": "game_051_test", "result": "loss"},
        [{"first_attack_turn": "none"}],
        [],
        [{"bottleneck": "missing Annihilape"}],
        [{"reasons": [{"reason": "no Annihilape", "confidence": "medium"}]}],
    )

    assert context["classification"] == "late Annihilape because setup failed"
    assert context["evolution_bottleneck"] == "missing Annihilape"


def test_late_annihilape_can_be_because_opponent_conceded_or_was_weak() -> None:
    context = annihilape_timing_context(
        {"game_id": "game_052_win_conceded_vs_test", "result": "win"},
        [{"first_attack_turn": "none"}],
        [],
        [],
        [],
    )

    assert context["classification"] == "late Annihilape because opponent conceded/was weak"
    assert context["confidence"] == "medium"
