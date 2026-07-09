from src.ai_coaching import extract_json_summary, terminal_report


def test_extract_json_summary_handles_nested_deck_coach_shape() -> None:
    text = """
## Next Experiment

```json
{
  "experiment_finished": "yes",
  "what_we_learned": "The test answered the rebuild question.",
  "deck_change": {
    "remove": [{"card": "Energy Switch", "count": 1}],
    "add": [{"card": "Lana's Aid", "count": 1}],
    "explanation": "Lana tests the rebuild slot more directly."
  },
  "confidence": "Medium",
  "next_experiment": {
    "hypothesis": "Lana improves post-KO rebuilds.",
    "remove": [{"card": "Energy Switch", "count": 1}],
    "add": [{"card": "Lana's Aid", "count": 1}],
    "success_criteria": ["Creates a better post-KO line than Energy Switch."],
    "games_to_test": 10,
    "priority_reason": "Rebuild quality is the highest-priority weakness."
  }
}
```
"""

    summary = extract_json_summary(text)

    assert summary["deck_change"]["add"] == [{"card": "Lana's Aid", "count": 1}]
    assert summary["next_experiment"]["games_to_test"] == 10


def test_terminal_report_uses_game_coach_contract_without_verdict() -> None:
    rendered = terminal_report(
        "",
        {
            "win_loss": "Jacob won because the early prize plan bought enough time.",
            "biggest_lesson": "Tempo can matter more than first Annihilape timing.",
            "experiment_status": "Neutral",
            "biggest_mistake": "No significant mistakes detected.",
            "next_game_focus": "Track whether the early attacker creates a real prize lead.",
        },
        "Game Coach",
        [
            ("Win/Loss", "win_loss"),
            ("Biggest Lesson", "biggest_lesson"),
            ("Experiment Status", "experiment_status"),
            ("Biggest Mistake", "biggest_mistake"),
            ("Next Game Focus", "next_game_focus"),
        ],
    )

    assert "## Win/Loss" in rendered
    assert "## Next Game Focus" in rendered
