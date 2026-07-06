# Experiment 004: SSP Annihilape + Waitress

## Question

Do 1 Annihilape SSP 100 and 2 Waitress ASC 215 improve rebuilds, tempo, or awkward evolution/energy games enough to keep them in the deck?

## Test Window

- Current checkpoint: Game 50
- Active memory: `data/experiments/current.json`
- Target: 10 games
- Review command: `python3 scripts/post_game.py --deck-review` or let `post_game.py` trigger Deck Coach automatically when the active experiment reaches 10/10 games.

## Evidence To Watch

- Waitress played count
- Waitress attached energy count
- Waitress whiff/no visible attach count
- SSP Annihilape attack count
- SSP attack outcomes: positive, neutral, negative
- Whether the package improves rebuilds after the first evolution line breaks

## Decision Rule

After each 10-game checkpoint, use Deck Coach to decide one of:

- Keep testing unchanged
- Change counts
- Cut one or both experiment cards
- Extend the experiment if evidence is too thin
