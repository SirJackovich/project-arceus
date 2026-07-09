from types import SimpleNamespace

from src.ai_coaching import extract_json_summary, game_log_like_snapshot_prefix, run_llm_report, terminal_report


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


def test_snapshot_prefix_uses_game_log_stem_for_game_coach() -> None:
    prefix = game_log_like_snapshot_prefix(
        {
            "coach_type": "game_coach",
            "deterministic_evidence": {
                "game": {"game_id": "game_052_20260709_loss_vs_omekarawo5005_v02"}
            },
        },
        "Game Coach",
    )

    assert prefix == "game_052_20260709_loss_vs_omekarawo5005_v02_game_coach"


def test_snapshot_prefix_uses_selected_game_range_for_deck_coach() -> None:
    prefix = game_log_like_snapshot_prefix(
        {
            "coach_type": "deck_coach",
            "deterministic_evidence": {
                "selected_game_ids": [
                    "game_051_20260708_win_vs_royaragon_v2",
                    "game_052_20260709_loss_vs_omekarawo5005_v02",
                ]
            },
        },
        "Deck Coach",
    )

    assert prefix == (
        "game_051_20260708_win_vs_royaragon_v2_through_"
        "game_052_20260709_loss_vs_omekarawo5005_v02_deck_coach"
    )


def test_run_llm_report_writes_game_coach_snapshots(tmp_path) -> None:
    args = SimpleNamespace(
        prompt_out=str(tmp_path / "latest_prompt.json"),
        output_md=str(tmp_path / "latest.md"),
        output_json=str(tmp_path / "latest.json"),
        snapshot_dir=str(tmp_path / "snapshots"),
        no_snapshot=False,
        dry_run=True,
        model="test-model",
        verbose=False,
    )
    context = {
        "coach_type": "game_coach",
        "deterministic_evidence": {
            "game": {"game_id": "game_052_20260709_loss_vs_omekarawo5005_v02"}
        },
    }

    run_llm_report(args, "Prompt", context, "Game Coach", [("Win/Loss", "win_loss")])

    prefix = tmp_path / "snapshots" / "game_052_20260709_loss_vs_omekarawo5005_v02_game_coach"
    assert prefix.with_suffix(".md").exists()
    assert prefix.with_suffix(".json").exists()
    assert (tmp_path / "snapshots" / f"{prefix.name}_prompt.json").exists()
