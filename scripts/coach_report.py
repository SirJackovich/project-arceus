#!/usr/bin/env python3
import argparse
import csv
import json
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


MY_PLAYER = "SirJackovich"

USAGE_TYPES = {
    "play_card", "bench_pokemon", "active_pokemon", "stadium_play", "evolve",
    "manual_attach", "attack", "use_ability", "activation", "retreat",
}


def read_csv(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def snapshot_prefix(payload):
    timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    scope = payload.get("scope", "report").replace(" ", "_")
    games = payload.get("games", [])
    if len(games) == 1:
        scope = games[0].get("game_id", scope)
    return f"{timestamp}_{scope}"


def write_report_outputs(args, rendered, payload):
    write_text(args.output_md, rendered)
    write_json(args.output_json, payload)
    if args.no_snapshot:
        return
    snapshot_dir = Path(args.snapshot_dir)
    prefix = snapshot_prefix(payload)
    write_text(snapshot_dir / f"{prefix}_coach_report.md", rendered)
    write_json(snapshot_dir / f"{prefix}_coach_report.json", payload)


def game_number(game_id):
    if game_id.startswith("game_"):
        digits = ""
        for char in game_id[5:]:
            if not char.isdigit():
                break
            digits += char
        if digits:
            return int(digits)
    return 0


def game_label(game_id):
    number = game_number(game_id)
    return f"Game {number}" if number else game_id


def pct(numerator, denominator):
    return round((numerator / denominator) * 100) if denominator else 0


def as_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def canonical_name(name):
    normalized = unicodedata.normalize("NFKD", name or "")
    ascii_name = "".join(char for char in normalized if not unicodedata.combining(char))
    return ascii_name.lower().replace("é", "e").strip()


def confidence_rank(confidence):
    return {"high": 0, "medium": 1, "low": 2}.get(confidence, 3)


def goal_priority(goal_id):
    priorities = {
        "annihilape_attack_by_turn4": 0,
        "full_power_impact_blow": 1,
        "setup_mankey_by_turn2": 2,
        "setup_backup_mankey_by_turn3": 3,
        "evolve_primeape_by_turn3": 4,
    }
    return priorities.get(goal_id, 10)


def load_deck_cards(path):
    deck_path = Path(path)
    if not deck_path.exists():
        return []
    deck = json.loads(deck_path.read_text(encoding="utf-8"))
    seen = []
    for card in deck.get("cards", []):
        name = card.get("name", "")
        if name and name not in seen:
            seen.append(name)
    return seen


def last_games(games, limit):
    complete = [game for game in games if game.get("has_game_log") == "yes"]
    complete.sort(key=lambda row: game_number(row.get("game_id", "")))
    return complete[-limit:]


def select_games(games, last, game_selector):
    complete = [game for game in games if game.get("has_game_log") == "yes"]
    complete.sort(key=lambda row: game_number(row.get("game_id", "")))
    if not game_selector:
        return complete[-last:]
    if game_selector == "latest":
        return complete[-1:]
    if game_selector.isdigit():
        target = int(game_selector)
        return [game for game in complete if game_number(game.get("game_id", "")) == target]
    return [
        game for game in complete
        if game.get("game_id") == game_selector or game.get("file") == game_selector
    ]


def summarize_games(games):
    wins = sum(1 for game in games if game.get("result") == "win")
    losses = sum(1 for game in games if game.get("result") == "loss")
    went_first = [game for game in games if game.get("my_went_first") == "yes"]
    went_second = [game for game in games if game.get("my_went_first") == "no"]
    return {
        "games": len(games),
        "wins": wins,
        "losses": losses,
        "win_rate": pct(wins, wins + losses),
        "went_first": len(went_first),
        "went_first_wins": sum(1 for game in went_first if game.get("result") == "win"),
        "went_second": len(went_second),
        "went_second_wins": sum(1 for game in went_second if game.get("result") == "win"),
    }


def goal_summary(success_rows, selected_ids):
    rows = [row for row in success_rows if row.get("game_id") in selected_ids]
    grouped = defaultdict(list)
    for row in rows:
        grouped[row.get("goal_id")].append(row)

    summaries = []
    for goal_id, goal_rows in grouped.items():
        counts = Counter(row.get("status") for row in goal_rows)
        sample = goal_rows[0]
        missed_rows = [row for row in goal_rows if row.get("status") == "missed"]
        summaries.append({
            "goal_id": goal_id,
            "goal_group": sample.get("goal_group", ""),
            "condition": sample.get("condition", ""),
            "confidence": sample.get("confidence", ""),
            "games": len(goal_rows),
            "met": counts["met"],
            "missed": counts["missed"],
            "unknown": counts["unknown"],
            "missed_games": [game_label(row.get("game_id", "")) for row in missed_rows],
            "missed_details": [row.get("detail", "") for row in missed_rows[:3]],
        })
    summaries.sort(key=lambda row: (
        confidence_rank(row["confidence"]),
        goal_priority(row["goal_id"]),
        -row["missed"],
        row["goal_group"],
        row["goal_id"],
    ))
    return summaries


def event_summary(events, selected_ids, deck_cards):
    selected = [row for row in events if row.get("game_id") in selected_ids]
    mine = [row for row in selected if row.get("event_player") == MY_PLAYER]

    card_counts = Counter()
    attack_counts = Counter()
    attack_damage = Counter()
    opening_cards = Counter()
    for row in mine:
        event_type = row.get("event_type")
        card = row.get("card_name")
        if card and event_type in USAGE_TYPES:
            card_counts[card] += 1
        if event_type == "attack" and card:
            attack = row.get("value") or "Unknown attack"
            key = f"{card} - {attack}"
            attack_counts[key] += 1
            attack_damage[key] += as_int(row.get("amount"))
        if event_type == "opening_hand" and card:
            opening_cards[card] += 1

    recently_used = {canonical_name(card) for card in card_counts}
    unused = [
        card for card in deck_cards
        if canonical_name(card) not in recently_used and not card.startswith("Basic {")
    ]
    return {
        "top_cards": card_counts.most_common(10),
        "top_attacks": [
            {
                "attack": attack,
                "uses": uses,
                "total_damage": attack_damage[attack],
                "avg_damage": round(attack_damage[attack] / uses, 1) if uses else 0,
            }
            for attack, uses in attack_counts.most_common(8)
        ],
        "opening_cards": opening_cards.most_common(8),
        "unused_deck_cards": unused,
    }


def my_turn_map(game_events):
    mapping = {}
    index = 0
    for event in game_events:
        if event.get("event_type") == "turn_start" and event.get("turn_player") == MY_PLAYER:
            turn = as_int(event.get("turn_number"))
            if turn and turn not in mapping:
                index += 1
                mapping[turn] = index
    return mapping


def my_turn_index(event, mapping):
    turn = as_int(event.get("turn_number"))
    if not turn:
        return 0
    return mapping.get(turn, 0)


def annihilape_miss_reasons(events, selected_ids, success_rows):
    missed_ids = {
        row.get("game_id") for row in success_rows
        if row.get("game_id") in selected_ids
        and row.get("goal_id") == "annihilape_attack_by_turn4"
        and row.get("status") == "missed"
    }
    grouped = defaultdict(list)
    for event in events:
        if event.get("game_id") in selected_ids:
            grouped[event.get("game_id")].append(event)

    counts = Counter({
        "Candy issue": 0,
        "Primeape issue": 0,
        "Energy issue": 0,
        "Damage-counter issue": 0,
        "KO/disruption issue": 0,
        "Unknown/hidden information": 0,
    })
    details = []

    for game_id in sorted(missed_ids, key=game_number):
        game_events = grouped[game_id]
        mapping = my_turn_map(game_events)
        mine = [event for event in game_events if event.get("event_player") == MY_PLAYER]
        early = [event for event in mine if my_turn_index(event, mapping) <= 4]
        early_board = [event for event in mine if my_turn_index(event, mapping) <= 3]

        primeape_ready = any(
            event.get("event_type") == "evolve" and event.get("card_name") == "Primeape"
            for event in early_board
        )
        rare_candy_seen = any(event.get("card_name") == "Rare Candy" for event in early)
        annihilape_ready = any(
            event.get("event_type") == "evolve" and event.get("card_name") == "Annihilape"
            for event in early
        )
        energy_on_annihilape = any(
            event.get("event_type") == "manual_attach"
            and event.get("target_card") == "Annihilape"
            for event in early
        )
        damage_setup = any(
            (
                event.get("event_type") in {"damage_counters", "activation"}
                and event.get("source_card") == "Risky Ruins"
            )
            or event.get("card_name") in {"Risky Ruins", "Hawlucha"}
            for event in early
        )
        disrupted = any(
            event.get("event_type") in {"knockout_received", "retreat", "unclassified"}
            and any(name in event.get("raw_line", "") for name in ["Mankey", "Primeape", "Annihilape", "switched"])
            and event.get("event_player") != MY_PLAYER
            for event in game_events
            if my_turn_index(event, mapping) <= 4 or as_int(event.get("turn_number")) <= 8
        )

        reasons = []
        if not primeape_ready:
            reasons.append("Primeape issue")
        if primeape_ready and not rare_candy_seen and not annihilape_ready:
            reasons.append("Candy issue")
        if annihilape_ready and not energy_on_annihilape:
            reasons.append("Energy issue")
        if annihilape_ready and energy_on_annihilape and not damage_setup:
            reasons.append("Damage-counter issue")
        if disrupted:
            reasons.append("KO/disruption issue")
        if not reasons:
            reasons.append("Unknown/hidden information")

        for reason in reasons:
            counts[reason] += 1
        details.append({"game": game_label(game_id), "game_id": game_id, "reasons": reasons})

    return {"counts": dict(counts), "details": details}


def recommendation_for_goal(goal):
    goal_id = goal["goal_id"]
    missed = goal["missed"]
    games = goal["games"]
    evidence = goal["missed_games"][:5]
    rate = pct(missed, games)

    if goal_id == "risky_ruins_by_turn2":
        recommendation = "Test whether the deck needs more reliable Stadium access, or whether early turns should prioritize Colress's Tenacity for Risky Ruins more often."
        experiment = "Track Risky Ruins by your Turn 2 for the next 10 games."
    elif goal_id == "setup_backup_mankey_by_turn3":
        recommendation = "Prioritize second Mankey setup earlier, even when the first attacker line looks playable."
        experiment = "For 10 games, mark whether you had two Mankey in play by your Turn 3."
    elif goal_id == "annihilape_attack_by_turn4":
        recommendation = "Review whether Rare Candy, Primeape evolution, or energy sequencing is the common bottleneck before changing card counts."
        experiment = "Tag each miss as Candy issue, evolution issue, energy issue, or KO disruption."
    elif goal_id == "full_power_impact_blow":
        recommendation = "Focus on damage-counter setup before your first Impact Blow so Annihilape reaches its intended knockout math."
        experiment = "Record first Impact Blow damage for the next 10 games."
    elif goal_id == "no_more_than_one_dead_turn":
        recommendation = "Review dead turns for whether the hand lacked draw, setup Pokemon, or energy access."
        experiment = "Add a one-word dead-turn cause in the importer notes."
    else:
        recommendation = f"Review missed {goal['goal_group']} checks and decide whether the issue is sequencing, prizes, or deck construction."
        experiment = f"Track '{goal['condition']}' over the next 10 games."

    confidence = "high" if missed >= 4 else "medium" if missed >= 2 else "low"
    if confidence_rank(goal["confidence"]) > confidence_rank(confidence):
        confidence = goal["confidence"]
    return {
        "observation": f"Missed '{goal['condition']}' in {missed}/{games} recent games ({rate}%).",
        "evidence": evidence,
        "recommendation": recommendation,
        "confidence": confidence,
        "next_experiment": experiment,
    }


def card_recommendations(card_effectiveness, event_data):
    recs = []
    watch_cards = [row for row in card_effectiveness if row.get("signal") == "watch"]
    watch_cards.sort(key=lambda row: as_int(row.get("games_used")), reverse=True)
    for row in watch_cards[:2]:
        recs.append({
            "observation": f"{row['card_name']} is flagged as watch: {row.get('games_used')} games used, win-rate delta {row.get('win_rate_delta_vs_deck')}.",
            "evidence": [row["card_name"]],
            "recommendation": "Do not cut it blindly; first review whether it is being played in losing recovery spots or causing the loss itself.",
            "confidence": "medium",
            "next_experiment": f"For the next 10 games, note whether {row['card_name']} was proactive value or late-game desperation.",
        })

    unused = event_data.get("unused_deck_cards", [])[:4]
    if unused:
        recs.append({
            "observation": f"These deck cards were not visibly used in the recent sample: {', '.join(unused)}.",
            "evidence": unused,
            "recommendation": "Treat these as candidate flex spots only after checking whether they were prized, discarded, or matchup-specific.",
            "confidence": "low",
            "next_experiment": "For the next 10 games, mark whether each unused card was dead, unavailable, or intentionally held.",
        })
    return recs


def friendly_condition(condition):
    replacements = {
        "Attack with at least one full-power 280+ damage Impact Blow.": "Full-power Impact Blow",
        "Get your first Annihilape attacking by your Turn 3-4.": "Late first Annihilape attack",
        "Open with Mankey or have one on the Bench by your Turn 2.": "Early Mankey setup",
        "Evolve into Primeape by your Turn 2-3.": "Primeape evolution timing",
        "Have at least one backup Mankey in play by your Turn 3.": "Backup Mankey setup",
        "Get Risky Ruins into play by your Turn 1-2.": "Early Risky Ruins",
        "Take first 2-Prize KO or stay even until first Annihilape is online.": "Prize race before Annihilape",
    }
    return replacements.get(condition, condition.rstrip("."))


def report_grade(summary, goals):
    score = 60 + summary["win_rate"] * 0.35
    for goal in goals:
        if goal["games"] and goal["confidence"] in {"high", "medium"}:
            score -= (goal["missed"] / goal["games"]) * (3 if goal["confidence"] == "high" else 1.5)
    if score >= 88:
        return "A"
    if score >= 78:
        return "B"
    if score >= 68:
        return "C"
    if score >= 58:
        return "D"
    return "F"


def coach_snapshot(summary, goals, recommendations):
    group_labels = {
        "Setup": "Early setup",
        "Evolution": "Evolution sequencing",
        "Damage Engine": "Damage engine",
        "Risky Ruins": "Risky Ruins timing",
        "Hand Quality": "Hand quality",
        "Prize Race": "Prize race",
    }
    group_rows = defaultdict(list)
    for goal in goals:
        if goal["games"] and goal["confidence"] != "low":
            group_rows[goal["goal_group"]].append(goal)
    group_scores = []
    for group, rows in group_rows.items():
        met = sum(row["met"] for row in rows)
        total = sum(row["met"] + row["missed"] for row in rows)
        if total:
            group_scores.append((met / total, group))
    group_scores.sort(reverse=True)

    miss_goals = [goal for goal in goals if goal["missed"] > 0 and goal["confidence"] != "low"]
    miss_goals.sort(key=lambda row: (
        confidence_rank(row["confidence"]),
        goal_priority(row["goal_id"]),
        -(row["missed"] / row["games"]),
        -row["missed"],
    ))

    strength = group_labels.get(group_scores[0][1], group_scores[0][1]) if group_scores else "No clear strength yet"
    weakness = friendly_condition(miss_goals[0]["condition"]) if miss_goals else "No clear weakness in this sample"
    focus = recommendations[0]["next_experiment"] if recommendations else "Keep collecting clean logs."

    if any(goal["goal_id"] == "annihilape_attack_by_turn4" for goal in miss_goals[:2]):
        focus = "Get Annihilape attacking by Turn 4."
    elif miss_goals and miss_goals[0]["goal_id"] == "full_power_impact_blow":
        focus = "Set up enough damage counters before the first Impact Blow."

    return {
        "grade": report_grade(summary, goals),
        "biggest_strength": strength,
        "biggest_weakness": weakness,
        "todays_focus": focus,
    }


def build_report(args):
    analysis_dir = Path(args.analysis_dir)
    games = read_csv(analysis_dir / "games.csv")
    success_rows = read_csv(analysis_dir / "success_condition_details.csv")
    events = read_csv(analysis_dir / "raw_events.csv")
    card_effectiveness = read_csv(analysis_dir / "card_effectiveness.csv")
    deck_cards = load_deck_cards(args.deck)

    selected_games = select_games(games, args.last, args.game)
    if not selected_games:
        raise SystemExit("No matching complete games found for report scope.")
    selected_ids = {game["game_id"] for game in selected_games}
    summary = summarize_games(selected_games)
    goals = goal_summary(success_rows, selected_ids)
    event_data = event_summary(events, selected_ids, deck_cards)
    miss_reasons = annihilape_miss_reasons(events, selected_ids, success_rows)

    recommendations = []
    recommendations.extend(
        recommendation_for_goal(goal)
        for goal in goals
        if goal["missed"] > 0 and goal.get("confidence") != "low"
    )
    recommendations.extend(card_recommendations(card_effectiveness, event_data))
    recommendations = recommendations[:args.max_recommendations]
    snapshot = coach_snapshot(summary, goals, recommendations)

    payload = {
        "scope": f"last {len(selected_games)} games",
        "games": [
            {
                "game": game_label(game["game_id"]),
                "game_id": game["game_id"],
                "opponent": game.get("opponent", ""),
                "result": game.get("result", ""),
                "went_first": game.get("my_went_first", ""),
                "turns": game.get("turns_total", ""),
            }
            for game in selected_games
        ],
        "summary": summary,
        "success_conditions": goals,
        "events": event_data,
        "annihilape_attack_miss_reasons": miss_reasons,
        "coach_snapshot": snapshot,
        "recommendations": recommendations,
    }
    return payload


def render_report(payload):
    summary = payload["summary"]
    lines = []
    lines.append("# Project Arceus Coach Report")
    lines.append("")
    lines.append(f"Scope: {payload['scope']}")
    lines.append(f"Record: {summary['wins']}-{summary['losses']} ({summary['win_rate']}% win rate)")
    lines.append(
        f"Went first: {summary['went_first_wins']}/{summary['went_first']} wins; "
        f"went second: {summary['went_second_wins']}/{summary['went_second']} wins"
    )
    if payload["recommendations"]:
        lines.append(f"Next experiment: {payload['recommendations'][0]['next_experiment']}")
    lines.append("")

    lines.append("## Recent Games")
    for game in payload["games"]:
        first = "first" if game["went_first"] == "yes" else "second" if game["went_first"] == "no" else "unknown"
        lines.append(f"- {game['game']}: {game['result']} vs {game['opponent']} going {first}")
    lines.append("")

    lines.append("## Biggest Misses")
    misses = [goal for goal in payload["success_conditions"] if goal["missed"] > 0]
    for goal in misses[:6]:
        lines.append(
            f"- {goal['goal_group']} ({goal['confidence']} confidence): "
            f"missed {goal['missed']}/{goal['games']} - {goal['condition']}"
        )
        if goal["missed_games"]:
            lines.append(f"  Evidence: {', '.join(goal['missed_games'][:5])}")
    if not misses:
        lines.append("- No success-condition misses in this sample.")
    lines.append("")

    lines.append("## Card And Attack Signals")
    top_cards = payload["events"]["top_cards"][:6]
    if top_cards:
        lines.append("Top visible card usage: " + ", ".join(f"{card} ({count})" for card, count in top_cards))
    top_attacks = payload["events"]["top_attacks"][:4]
    for attack in top_attacks:
        lines.append(
            f"- {attack['attack']}: {attack['uses']} uses, {attack['avg_damage']} avg damage"
        )
    unused = payload["events"].get("unused_deck_cards", [])[:6]
    if unused:
        lines.append("Recently unused deck cards: " + ", ".join(unused))
    lines.append("")

    lines.append("## First Annihilape Attack Miss Reason")
    reason_counts = payload["annihilape_attack_miss_reasons"]["counts"]
    for label in [
        "Candy issue",
        "Primeape issue",
        "Energy issue",
        "Damage-counter issue",
        "KO/disruption issue",
        "Unknown/hidden information",
    ]:
        lines.append(f"- {label}: {reason_counts.get(label, 0)}")
    reason_details = payload["annihilape_attack_miss_reasons"].get("details", [])
    if reason_details:
        detail_text = "; ".join(
            f"{row['game']} ({', '.join(row['reasons'])})" for row in reason_details[:6]
        )
        lines.append(f"Evidence: {detail_text}")
    lines.append("Note: these are log-derived heuristics; hidden hand/prize state can make the true reason ambiguous.")
    lines.append("")

    lines.append("## Recommendations")
    for rec in payload["recommendations"]:
        lines.append(f"- Observation: {rec['observation']}")
        lines.append(f"  Evidence: {', '.join(rec['evidence']) if rec['evidence'] else 'none'}")
        lines.append(f"  Recommendation: {rec['recommendation']}")
        lines.append(f"  Confidence: {rec['confidence']}")
        lines.append(f"  Next experiment: {rec['next_experiment']}")
    return "\n".join(lines) + "\n"


def render_concise_report(payload):
    summary = payload["summary"]
    snapshot = payload["coach_snapshot"]
    lines = []
    lines.append("# Project Arceus Coach Report")
    lines.append("")
    lines.append("## Coach Grade")
    lines.append(snapshot["grade"])
    lines.append("")
    lines.append("## Biggest Strength")
    lines.append(snapshot["biggest_strength"])
    lines.append("")
    lines.append("## Biggest Weakness")
    lines.append(snapshot["biggest_weakness"])
    lines.append("")
    lines.append("## Today's Focus")
    lines.append(snapshot["todays_focus"])
    lines.append("")
    lines.append("## Quick Stats")
    lines.append(f"- Scope: {payload['scope']}")
    lines.append(f"- Record: {summary['wins']}-{summary['losses']} ({summary['win_rate']}% win rate)")
    lines.append(f"- Going first: {summary['went_first_wins']}/{summary['went_first']} wins")
    lines.append(f"- Going second: {summary['went_second_wins']}/{summary['went_second']} wins")
    lines.append("")

    misses = [goal for goal in payload["success_conditions"] if goal["missed"] > 0 and goal["confidence"] != "low"]
    lines.append("## Why")
    for goal in misses[:3]:
        lines.append(
            f"- {friendly_condition(goal['condition'])}: missed {goal['missed']}/{goal['games']} "
            f"({', '.join(goal['missed_games'][:4])})"
        )
    if not misses:
        lines.append("- No major success-condition misses in this sample.")
    lines.append("")

    lines.append("## First Annihilape Attack Miss Reason")
    reason_counts = payload["annihilape_attack_miss_reasons"]["counts"]
    for label in ["Candy issue", "Primeape issue", "Energy issue", "Damage-counter issue", "KO/disruption issue"]:
        lines.append(f"- {label}: {reason_counts.get(label, 0)}")
    unknown = reason_counts.get("Unknown/hidden information", 0)
    if unknown:
        lines.append(f"- Unknown/hidden information: {unknown}")
    lines.append("")

    if payload["recommendations"]:
        rec = payload["recommendations"][0]
        lines.append("## Coach Note")
        lines.append(rec["recommendation"])
        lines.append(f"Evidence: {', '.join(rec['evidence']) if rec['evidence'] else 'none'}")
        lines.append(f"Confidence: {rec['confidence']}")
        lines.append("")

    lines.append("## Commands")
    lines.append("- New match: `python3 scripts/post_game.py`")
    lines.append("- Detailed report: `python3 scripts/coach_report.py --last 10 --verbose`")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Generate a fast Project Arceus coaching report.")
    parser.add_argument("--analysis-dir", default="data/analysis")
    parser.add_argument("--deck", default="decks/annihilape/v01.json")
    parser.add_argument("--last", type=int, default=10)
    parser.add_argument("--game", help="Report one game by number, game_id, filename, or 'latest'.")
    parser.add_argument("--max-recommendations", type=int, default=5)
    parser.add_argument("--output-md", default="data/analysis/coach_report.md")
    parser.add_argument("--output-json", default="data/analysis/coach_report.json")
    parser.add_argument("--snapshot-dir", default="data/coaching_sessions")
    parser.add_argument("--no-snapshot", action="store_true", help="Only write latest report outputs.")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--verbose", action="store_true", help="Render the longer detailed report.")
    args = parser.parse_args()

    payload = build_report(args)
    rendered = render_report(payload) if args.verbose else render_concise_report(payload)
    print(rendered, end="")
    if not args.no_write:
        write_report_outputs(args, rendered, payload)


if __name__ == "__main__":
    main()
