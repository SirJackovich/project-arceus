# Project Arceus

An AI-powered coaching system that analyzes Pokemon TCG Live matches, recommends improvements, and tests them in real ranked games on the road to Arceus.

## Project Goal

Project Arceus is a CLI-first coaching tool for reviewing Pokemon TCG Live battle logs. The MVP optimizes for speed, simplicity, and useful post-game feedback: import logs, analyze patterns, compare results against the current deck plan, and prepare concise coaching recommendations.

Project Arceus uses a two-layer coaching system:

- Layer 1: deterministic Python analyzer. It parses logs and writes structured evidence to `data/analysis/deterministic_analysis.json`.
- Layer 2: AI coach. It sends only the structured evidence, decklist, and experiment state to an LLM, then writes the final coaching report.

## Current Features

- Parses one or many Pokemon TCG Live battle logs from `data/logs/`.
- Generates CSV/JSON/XLSX analysis outputs in `data/analysis/`.
- Tracks game results, opening choices, card usage, attacks, prize events, and success-condition checks.
- Writes deterministic evidence for AI coaching, including mulligans, card flow, Annihilape attack quality, Risky Ruins timing, evolution bottlenecks, backup attacker state, possible loss factors, and confidence notes.
- Generates an optional AI-written coach report from deterministic evidence instead of raw logs.
- Tracks the current deck experiment in `data/experiment_tracker.json`.
- Stores the current Annihilape deck as `decks/annihilape/v01.json` and `v01.md`.
- Stores fetched card details in `decks/annihilape/card_details.json` and `card_details.md`.
- Provides reusable prompt templates for summaries, coaching, and deck recommendations.

## MVP Scope

The MVP is complete when a new match log can be imported, summarized, included in the last-10-games analysis, and turned into actionable next-test recommendations in under 60 seconds.

Intentionally out of scope for now:

- Web app
- Authentication
- Cloud hosting
- Public API
- Mobile app
- Live coaching
- Machine learning
- Video generation
- Automatic deck import

## How To Run

Import the latest pasted battle log and run the coach analysis:

```bash
python3 scripts/post_game.py
```

This is the normal one-command workflow. It imports the pasted log, runs deterministic analysis, then runs the AI coach for the last 10 games.

Useful options:

```bash
python3 scripts/post_game.py --no-ai
python3 scripts/post_game.py --verbose
python3 scripts/post_game.py --last 15
```

Run the project safety checks before committing:

```bash
python3 scripts/check_project.py
```

The repository uses `.githooks/pre-commit` to run that same command before each commit. If hooks are not active after a fresh clone, run:

```bash
git config core.hooksPath .githooks
```

Import a pasted battle log:

```bash
python3 scripts/import_log.py
```

Imported logs use this filename convention:

```text
game_045_20260703_loss_vs_dragapult_annihilape_v01.txt
```

The format is `game_<number>_<yyyymmdd>_<result>_vs_<opponent-or-archetype>_<deck>.txt`.

Normalize existing logs into that convention:

```bash
python3 scripts/normalize_logs.py --dry-run
python3 scripts/normalize_logs.py
```

The normalizer archives old filenames in `data/logs_original/`, rewrites `data/logs/`, and rebuilds both `data/manifest.csv` and the more readable `data/manifest.json`.

Parse all logs:

```bash
python3 scripts/analyze_logs.py
```

Evaluate deck success conditions:

```bash
python3 scripts/evaluate_success.py
```

Generate deterministic evidence only:

```bash
python3 scripts/coach_report.py --last 10
```

The main structured output is:

- `data/analysis/deterministic_analysis.json`

Generate the AI-written coach report:

```bash
export OPENAI_API_KEY="your-api-key"
python3 scripts/ai_coach_report.py --last 10
```

Inspect the AI prompt/context without calling the LLM:

```bash
python3 scripts/ai_coach_report.py --dry-run
```

Run the full local analysis flow plus AI coach:

```bash
python3 scripts/run_analysis.py --ai-coach
```

Without `--ai-coach`, `run_analysis.py` prints only the deterministic evidence path, last-10 record, and one-line top issue.

Each run writes both latest reports side by side:

- `data/analysis/coach_report.md`
- `data/analysis/coach_report.json`
- `data/analysis/coach_report_verbose.md`
- `data/analysis/coach_report_verbose.json`

Each run also saves timestamped copies in `data/coaching_sessions/`.

The AI coach writes:

- `data/analysis/ai_coach_report.md`
- `data/analysis/ai_coach_report.json`
- `data/analysis/ai_coach_prompt.json`

Track a deck experiment:

```bash
python3 scripts/experiment_tracker.py start \
  --name "Hilda vs Colress" \
  --changed-cards "Hilda, Colress's Tenacity" \
  --target-question "Does Hilda improve evolution and energy access?"

python3 scripts/experiment_tracker.py record \
  --game 47 \
  --result win \
  --evidence-for "found Annihilape on time" \
  --evidence-against "no early Risky Ruins"
```

Generate a single-game summary for the newest match:

```bash
python3 scripts/coach_report.py --game latest
```

Refresh card details:

```bash
python3 scripts/fetch_card_details.py
```

Build the workbook report:

```bash
node scripts/build_workbook.mjs
```

Run the full local analysis flow:

```bash
python3 scripts/run_analysis.py
```

Rebuild the workbook too:

```bash
python3 scripts/run_analysis.py --with-workbook
```

Analyze only sample logs:

```bash
python3 scripts/analyze_logs.py --input-dir sample_data --output-dir /tmp/project-arceus-sample-analysis
```

Install test dependencies if `check_project.py` reports that pytest is missing:

```bash
python3 -m pip install -r requirements.txt
```

## Example Workflow

1. Copy the battle log from Pokemon TCG Live.
2. Run `python3 scripts/post_game.py`.
3. Paste the battle log, then type `::END_LOG::` on its own line.
4. Confirm the inferred opponent, result, first-player, and concession values.
5. Answer the remaining metadata prompts for date, deck version, starting rank, ending rank after this game, and notes. Starting rank defaults to the previous manifest entry's ending rank.
6. Let Project Arceus run the analysis pipeline.
7. Review `data/analysis/ai_coach_report.md` if using the AI coach, or `data/analysis/deterministic_analysis.json` for raw evidence.
8. Optionally run `python3 scripts/run_analysis.py --with-workbook` if you want the full workbook.
9. Choose one experiment from `experiments/` or add a new one.

## Coaching Object

AI coaching recommendations should use this shape:

```json
{
  "observation": "...",
  "evidence": ["Game 41", "Game 43", "Game 47"],
  "recommendation": "...",
  "confidence": "medium",
  "next_experiment": "..."
}
```
