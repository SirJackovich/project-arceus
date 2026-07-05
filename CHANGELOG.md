# Changelog

## v0.3.0

- Added a one-command post-game flow with `scripts/post_game.py`.
- Made the default coach report concise with Coach Grade, Biggest Strength, Biggest Weakness, and Today's Focus.
- Made workbook generation opt-in with `scripts/run_analysis.py --with-workbook`.
- Added timestamped coaching session snapshots under `data/coaching_sessions/`.
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
