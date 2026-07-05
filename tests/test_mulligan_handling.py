#!/usr/bin/env python3
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


GAME_45_MULLIGAN_LOG = """Setup
SirJackovich chose heads for the opening coin flip.
SirJackovich won the coin toss.
SirJackovich decided to go first.
SirJackovich drew 7 cards for the opening hand.
- 7 drawn cards.
   • Risky Ruins, Annihilape, Basic Fighting Energy, Dawn, Fighting Gong, Primeape, Poké Pad
SirJackovich took a mulligan.
- Cards revealed from Mulligan 1
   • Risky Ruins, Annihilape, Basic Fighting Energy, Dawn, Fighting Gong, Primeape, Poké Pad
TestOpponent drew 7 cards for the opening hand.
- 7 drawn cards.
TestOpponent drew 1 more card because SirJackovich took at least 1 mulligan.
- TestOpponent drew a card.
SirJackovich played Hawlucha to the Active Spot.
TestOpponent played Ralts to the Active Spot.

SirJackovich's Turn
SirJackovich drew a card.
SirJackovich played Poké Pad.
SirJackovich ended their turn.

TestOpponent's Turn
TestOpponent's Ralts used Slap on SirJackovich's Hawlucha for 10 damage.

SirJackovich's Turn
SirJackovich drew a card.
SirJackovich ended their turn.

TestOpponent wins.
"""


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class MulliganHandlingTest(unittest.TestCase):
    def test_mulligan_reveal_is_not_playable_opening_hand(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            logs = tmp / "logs"
            analysis = tmp / "analysis"
            logs.mkdir()
            (logs / "game_045_20260705_loss_vs_testopponent_annihilape_v01.txt").write_text(
                GAME_45_MULLIGAN_LOG,
                encoding="utf-8",
            )

            subprocess.run(
                [sys.executable, "scripts/analyze_logs.py", "--input-dir", str(logs), "--output-dir", str(analysis)],
                cwd=ROOT,
                check=True,
            )
            games = read_csv(analysis / "games.csv")
            events = read_csv(analysis / "raw_events.csv")
            opening_hands = read_csv(analysis / "opening_hands.csv")

            self.assertEqual(games[0]["my_mulligans"], "1")
            self.assertEqual(games[0]["my_opening_hand_visibility"], "hidden_after_mulligan")
            self.assertTrue(
                any(
                    event["event_type"] == "mulligan_revealed_card" and event["card_name"] == "Risky Ruins"
                    for event in events
                )
            )
            self.assertFalse(any(row["card_name"] == "Risky Ruins" for row in opening_hands))

            subprocess.run(
                [sys.executable, "scripts/evaluate_success.py", "--analysis-dir", str(analysis)],
                cwd=ROOT,
                check=True,
            )
            report_json = tmp / "coach_report.json"
            subprocess.run(
                [
                    sys.executable,
                    "scripts/coach_report.py",
                    "--analysis-dir",
                    str(analysis),
                    "--last",
                    "1",
                    "--output-md",
                    str(tmp / "coach_report.md"),
                    "--output-json",
                    str(report_json),
                    "--snapshot-dir",
                    str(tmp / "snapshots"),
                    "--no-snapshot",
                ],
                cwd=ROOT,
                check=True,
            )
            payload = json.loads(report_json.read_text(encoding="utf-8"))
            reasons = payload["annihilape_attack_miss_reasons"]["details"][0]["reasons"]
            self.assertIn({"reason": "unknown/no visible Mankey", "confidence": "low"}, reasons)
            self.assertNotIn({"reason": "no Mankey", "confidence": "medium"}, reasons)
            self.assertTrue(payload["mulligan_warnings"])


if __name__ == "__main__":
    unittest.main()
