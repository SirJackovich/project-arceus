# Changelog

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
