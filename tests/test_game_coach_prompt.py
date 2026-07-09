from pathlib import Path


def test_game_coach_prompt_prioritizes_major_mistakes_over_chip_damage() -> None:
    prompt = Path("prompts/game_coach.md").read_text(encoding="utf-8")

    assert "Do not label a small early attack as the Biggest Mistake unless it clearly caused the loss." in prompt
    assert "missed evolution or rebuild sequence" in prompt
    assert "low-impact chip damage" in prompt
    assert "big SSP Annihilape Destined Fight trade" in prompt
    assert "## Secondary Note" in prompt
    assert "Neutral: Lana's Aid was not played and did not affect the rebuild turn." in prompt
