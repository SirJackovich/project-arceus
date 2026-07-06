# Changelog

Each Codex change should add a new entry that says what changed, why it changed, and how to test it.

## v0.8.0

- What changed: Split AI coaching into `scripts/game_coach.py` for the current game and `scripts/deck_coach.py` for last-N-game deck review trends.
- What changed: Added separate `prompts/game_coach.md` and `prompts/deck_coach.md`, with the old `scripts/ai_coach_report.py` kept as a Deck Coach compatibility wrapper.
- What changed: Updated `scripts/post_game.py` so Game Coach runs after every imported game, while Deck Coach runs with `--deck-review` or when the active experiment reaches its target game count.
- What changed: Added Game Coach and Deck Coach dry runs to `scripts/check_project.py`.
- Why: Per-game coaching and deck-review coaching answer different questions and should not mix current-game advice with trend analysis.
- How to test: Run `python3 scripts/check_project.py`, then use `python3 scripts/post_game.py --ai-dry-run` or `python3 scripts/post_game.py --deck-review --ai-dry-run`.

## v0.7.0

- What changed: Added pytest guardrail coverage with fixture logs for mulligans, hidden final hands, Risky Ruins timing, Waitress attach/whiff tracking, SSP Annihilape attack outcomes, win/loss detection, partial logs, and golden-output facts.
- What changed: Added `scripts/check_project.py` to run syntax checks, pytest, sample fixture analysis, and expected-output-file verification.
- What changed: Added a tracked `.githooks/pre-commit` hook that runs `python3 scripts/check_project.py`, plus light parser type hints and main-script docstrings.
- Why: Future parser and coach changes need a fast local safety net before they touch real match data or coaching recommendations.
- How to test: Run `python3 scripts/check_project.py`; commits will run the same command through the configured pre-commit hook.

## v0.6.3

- Updated rank import handling so starting rank defaults to the previous game's ending rank while remaining editable.

## v0.6.2

- Made `scripts/post_game.py` the quiet default one-command workflow with AI on by default, plus `--no-ai`, `--verbose`, and `--last` flags.
- Made `scripts/run_analysis.py` concise by default and moved full command/report output behind `--verbose`.
- Changed full-power Impact Blow logic to count Lose Cool activation separately from final weakness/resistance-adjusted damage.
- Added per-SSP attack prize swing/outcome details and mulligan-rate evidence.
- Removed normal-output command/help text from concise reports.

## v0.6.1

- Tightened the AI coach prompt to avoid default 280-damage waiting advice and require game evidence for card-specific criticism.
- Added current experiment evidence for 1 SSP Annihilape and 2 Waitress, including Waitress attaches/whiffs and SSP attack outcome.
- Added candidate strength evidence to avoid unsupported Hand Quality claims.
- Added attack decision quality evidence for Annihilape and Primeape attacks.
- Limited AI coach terminal output to six concise coaching sections while saving the full Markdown report.

## v0.6.0

- Added a two-layer coaching flow with deterministic analyzer evidence and an AI-written coach report.
- Added `data/analysis/deterministic_analysis.json` as the structured evidence handoff for the AI coach.
- Added `scripts/ai_coach_report.py` to generate Markdown and JSON coaching reports from analyzer evidence, decklist, and experiment state.
- Added `prompts/coach_report.md` with concise Pokemon TCG coaching instructions.
- Added `scripts/experiment_tracker.py` for tracking current card experiments and evidence over a 10-game sample.
- Added AI coach flags to `scripts/run_analysis.py` and `scripts/post_game.py`.

## v0.5.0

- Added evolution-line assembly analysis for first complete Annihilape line timing.
- Added evolution bottleneck metrics for missing Mankey, Primeape, and Annihilape.
- Added visible hand-gap tracking for Annihilape-without-Primeape and Primeape-without-Annihilape scenarios.
- Added rebuild analysis after the Mankey evolution line is broken by a KO.
- Replaced the generic first-attack recommendation with a bottleneck-driven coach recommendation.
- Added a one-sentence Game Narrative section to coach reports.

## v0.4.1

- Fixed mulligan-hand handling so revealed mulligan cards are tracked separately from playable opening-hand cards.
- Added mulligan counts and opening-hand visibility fields to parsed game output.
- Lowered confidence for hand-based miss reasons when the post-mulligan hand is hidden.
- Added coach report warnings for games with hidden post-mulligan hands.
- Added a Game 45-style regression test for mulligan Risky Ruins availability and missed-setup diagnosis.

## v0.4.0

- Improved coach report metrics for card flow, Annihilape attack quality, backup attacker readiness, Stadium quality, and missed-goal causes.

## v0.3.0

- Added a one-command post-game flow with `scripts/post_game.py`.
- Made the default coach report concise with Coach Grade, Biggest Strength, Biggest Weakness, and Today's Focus.
- Made workbook generation opt-in with `scripts/run_analysis.py --with-workbook`.
- Added timestamped coaching session snapshots under `data/coaching_sessions/`.
- Saved concise and verbose coach reports side by side for both latest outputs and coaching session snapshots.
- Added a CLI coaching report for the last N games.
- Added single-game coach report support with `--game latest`.
- Added a one-command local analysis pipeline with `scripts/run_analysis.py`.
- Added a first-Annihilape-attack miss reason breakdown using log-derived heuristics.
- Added deterministic coaching recommendations with observation, evidence, recommendation, confidence, and next experiment fields.
- Added Markdown and JSON coach report outputs under `data/analysis/`.
- Updated the README workflow to include the coach report step.

## v0.2.0

- Added an interactive terminal log importer for pasted Pokemon TCG Live battle logs.
- Added automatic inference for opponent, result, went-first status, and concession status.
- Added normalized log filenames using `game_<number>_<yyyymmdd>_<result>_vs_<opponent>_<deck>.txt`.
- Added `data/manifest.json` alongside `data/manifest.csv` for more readable game metadata.
- Added a one-time log normalization script for renaming existing logs and rebuilding manifests.

## v0.1.0

- Reorganized the workspace into Project Arceus.
- Added `data/logs/`, `data/analysis/`, `decks/annihilape/`, `sample_data/`, `prompts/`, `experiments/`, and `src/`.
- Updated script defaults to the new project layout.
- Preserved the current log parser, success-condition evaluator, card detail fetcher, and workbook report builder.
- Added README, prompt templates, experiment starters, and dependency metadata.
