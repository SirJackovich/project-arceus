# Project Arceus

An AI-powered coaching system that analyzes Pokemon TCG Live matches, recommends improvements, and tests them in real ranked games on the road to Arceus.

## Project Goal

Project Arceus is a CLI-first coaching tool for reviewing Pokemon TCG Live battle logs. The MVP optimizes for speed, simplicity, and useful post-game feedback: import logs, analyze patterns, compare results against the current deck plan, and prepare concise coaching recommendations.

## Current Features

- Parses one or many Pokemon TCG Live battle logs from `data/logs/`.
- Generates CSV/JSON/XLSX analysis outputs in `data/analysis/`.
- Tracks game results, opening choices, card usage, attacks, prize events, and success-condition checks.
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

Parse all logs:

```bash
python3 scripts/analyze_logs.py
```

Evaluate deck success conditions:

```bash
python3 scripts/evaluate_success.py
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
python3 scripts/analyze_logs.py
python3 scripts/evaluate_success.py
node scripts/build_workbook.mjs
```

Analyze only sample logs:

```bash
python3 scripts/analyze_logs.py --input-dir sample_data --output-dir /tmp/project-arceus-sample-analysis
```

## Example Workflow

1. Export a new battle log from Pokemon TCG Live.
2. Save it into `data/logs/`.
3. Run the full local analysis flow.
4. Open `data/analysis/monkey_deck_analysis.xlsx`.
5. Review success-condition misses, attack usage, and card effectiveness.
6. Choose one experiment from `experiments/` or add a new one.

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

