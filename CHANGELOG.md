# Changelog

Each Codex change should add a new entry that says what changed, why it changed, and how to test it.

## v0.10.2

- What changed: Game Coach and Deck Coach now save historical Markdown, JSON, and prompt snapshots in `data/coaching_sessions/`.
- What changed: Snapshot filenames use game-log-style stems, such as `game_052_20260709_loss_vs_omekarawo5005_v02_game_coach.md` for Game Coach and a first-through-last game range for Deck Coach.
- Why: Latest coach files are useful for quick review, but individual coach responses should be preserved for later experiment auditing.
- How to test: Run `python3 scripts/check_project.py` and `python3 -m pytest tests/test_ai_coaching.py`.

## v0.10.1

- What changed: `scripts/post_game.py` now defaults the import deck version to the previous manifest entry instead of always using `decks/annihilape/v01.json`.
- What changed: `post_game.py` passes the imported game's deck into `evaluate_success.py`, `coach_report.py`, `game_coach.py`, and `deck_coach.py` so the whole workflow evaluates the deck actually used.
- What changed: `scripts/import_log.py` now also defaults direct imports to the previous manifest deck, with a guard for accidental `deck/...` paths when the matching `decks/...` file exists.
- Why: Post-game coaching should follow the active deck version, especially after moving from v01 to v02.
- How to test: Run `python3 scripts/check_project.py` and `python3 -m pytest tests/test_post_game.py tests/test_import_log.py`.

## v0.10.0

- What changed: Reframed Game Coach and Deck Coach prompts around coaching judgment instead of deterministic summaries.
- What changed: Game Coach now answers exactly Win/Loss, Biggest Lesson, Experiment Status, Biggest Mistake, and Next Game Focus.
- What changed: Deck Coach now answers exactly Is The Current Experiment Finished, What Did We Actually Learn, What Deck Change Do You Recommend, Confidence, and Next Experiment.
- What changed: Deck Coach is instructed to use Standard-legal card recommendations to choose one next experiment when the current experiment is complete.
- What changed: AI summary parsing now supports nested Deck Coach JSON objects.
- Why: The LLM should act like a personal Pokemon coach that explains lessons and proposes hypotheses, not a report generator repeating deterministic stats.
- How to test: Run `python3 scripts/check_project.py`, `python3 scripts/game_coach.py --game latest --dry-run`, and `python3 scripts/deck_coach.py --experiment current --dry-run`.

## v0.9.4

- What changed: Deck Coach context and output instructions now always include the active experiment's exact Remove/Add deck change.
- What changed: Structured card-change terminal formatting now renders as `Card x count`.
- What changed: Standard card recommendations exclude previously rejected cards such as Salvatore unless experiment memory marks them reconsiderable.
- Why: Deck reviews should keep the current test visible and avoid resurfacing rejected cards without an explicit reason.
- How to test: Run `python3 scripts/check_project.py` and `python3 scripts/deck_coach.py --experiment current --dry-run`.

## v0.9.3

- What changed: Expanded Standard card recommendations across the top three deck problems: rebuild after KO, missing evolution access, and missing Basic setup.
- What changed: Candidate cards now include exact matched text, problem-fit explanation, Annihilape downside notes, slot cost, and Risky Ruins conflict notes.
- What changed: Deck Coach now receives 10-15 grouped candidates by default and scored cut candidates based on usage, impact, redundancy, questioned status, and core-card protection.
- What changed: Added a sanity rule that keeps Lana's Aid in the candidate list when experiment memory says to test it over Energy Switch.
- Why: The LLM should choose the best problem, card, and cut from richer evidence instead of inheriting one narrow keyword result.
- How to test: Run `python3 scripts/check_project.py` and `python3 scripts/recommend_cards.py --max-cards 12`.

## v0.9.2

- What changed: Made completed experiment memory authoritative for Deck Coach by passing a structured next experiment from `data/experiments/current.json`.
- What changed: Added Experiment 004 rollover logic so the completed SSP Annihilape + Waitress experiment archives itself and activates Experiment 005, Lana's Aid Rebuild Consistency.
- What changed: Experiment 005 is defined as Remove Energy Switch x2, Add Lana's Aid x2, with the rebuild-after-KO hypothesis.
- Why: Deck Coach should not keep re-evaluating completed experiments or override a completed experiment's final verdict without strong evidence.
- How to test: Run `python3 scripts/check_project.py` and `python3 scripts/deck_coach.py --experiment current --dry-run`.

## v0.9.1

- What changed: Deck Coach terminal output now includes the exact next experiment card change when the LLM returns one.
- What changed: Added formatting for structured `next_experiment` JSON so Remove/Add/Hypothesis/Success Criteria/Confidence are readable in the short report.
- Why: The full report had the recommendation, but the terminal summary hid the card change.
- How to test: Run `python3 scripts/deck_coach.py --experiment current --dry-run` and `python3 scripts/check_project.py`.

## v0.9.0

- What changed: Added a local Standard card database importer with `scripts/build_standard_card_db.py` for H/I/J regulation-mark cards.
- What changed: Added deterministic card recommendation search with `src/card_recommender.py` and `scripts/recommend_cards.py`.
- What changed: Deck Coach now receives up to 5 Standard-legal candidate cards, suggested small cuts, and the detected top deck problem.
- What changed: Updated Deck Coach prompt to rank candidates by problem solved, Annihilape/Risky Ruins fit, slot cost, downside, legality, and engine conflict, then recommend exactly one 1-2 card experiment or no change.
- Why: Deck experiments should be proposed by Project Arceus from Standard card text and match evidence, not manually invented each time.
- How to test: Run `python3 scripts/check_project.py`, `python3 scripts/recommend_cards.py`, and `python3 scripts/deck_coach.py --experiment current --dry-run`.

## v0.8.3

- What changed: Updated Deck Coach rules so passing experiment cards are not cut unless they clearly caused losses or blocked stronger plays.
- Why: Experiment 004 showed cards can be worth keeping even when the deck's next problem is elsewhere.
- How to test: Run `python3 scripts/check_project.py` and `python3 scripts/deck_coach.py --experiment current --dry-run`.

## v0.8.2

- What changed: Added `data/experiments/current.json` experiment memory with name, deck changes, hypothesis, success criteria, start game, target games, tested cards, progress, completed status, and final verdict fields.
- What changed: Updated `scripts/post_game.py` to sync experiment progress after every imported game and run Deck Coach only when the active experiment is complete or `--deck-review` is passed.
- What changed: Updated `scripts/deck_coach.py --experiment current` so Deck Coach scopes evidence to active experiment games instead of generic last-10 trends.
- What changed: Added richer Game Coach context for turn summary, key turning point, experiment card events, prize swings, and win/loss candidates.
- Why: Game Coach should remain current-game focused, while Deck Coach should make decisions only from the active experiment window.
- How to test: Run `python3 scripts/check_project.py`, then inspect `data/experiments/current.json` and run `python3 scripts/deck_coach.py --experiment current --dry-run`.

## v0.8.1

- What changed: Added Game Coach timing context so late first Annihilape is classified as setup failure, early attacker bought time, opponent conceded/was weak, or on-time instead of always being treated as bad.
- What changed: Included Hawlucha in attack-decision evidence so Hawlucha prize turns can explain delayed Annihilape timing.
- What changed: Changed automatic Deck Coach review cadence to saved game numbers ending in `0`, making Game 50 the SSP Annihilape + Waitress checkpoint.
- What changed: Added `experiments/004-ssp-annihilape-waitress.md` for the current experiment.
- Why: Game Coach needs to reflect the actual match context, and deck reviews should align with clean 10-game checkpoints.
- How to test: Run `python3 scripts/check_project.py` and inspect `python3 scripts/game_coach.py --game latest --dry-run` for `annihilape_timing_context`.

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
