# Changelog

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
