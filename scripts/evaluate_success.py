#!/usr/bin/env python3
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


MY_PLAYER = "SirJackovich"


GOALS = [
    {
        "id": "setup_mankey_by_turn2",
        "group": "Setup",
        "condition": "Open with Mankey or have one on the Bench by your Turn 2.",
        "confidence": "high",
    },
    {
        "id": "setup_backup_mankey_by_turn3",
        "group": "Setup",
        "condition": "Have at least one backup Mankey in play by your Turn 3.",
        "confidence": "medium",
    },
    {
        "id": "evolve_primeape_by_turn3",
        "group": "Evolution",
        "condition": "Evolve into Primeape by your Turn 2-3.",
        "confidence": "high",
    },
    {
        "id": "annihilape_attack_by_turn4",
        "group": "Evolution",
        "condition": "Get your first Annihilape attacking by your Turn 3-4.",
        "confidence": "high",
    },
    {
        "id": "damage_engine_before_impact",
        "group": "Damage Engine",
        "condition": "Have visible damage-engine setup before your first Impact Blow.",
        "confidence": "medium",
    },
    {
        "id": "full_power_impact_blow",
        "group": "Damage Engine",
        "condition": "Attack with at least one full-power 280+ damage Impact Blow.",
        "confidence": "high",
    },
    {
        "id": "risky_ruins_by_turn2",
        "group": "Risky Ruins",
        "condition": "Get Risky Ruins into play by your Turn 1-2.",
        "confidence": "high",
    },
    {
        "id": "avoid_easy_prize_from_damage",
        "group": "Risky Ruins",
        "condition": "Avoid giving up an easy prize from self-damage setup.",
        "confidence": "low",
    },
    {
        "id": "no_more_than_one_dead_turn",
        "group": "Hand Quality",
        "condition": "Never spend more than one turn with no productive play.",
        "confidence": "medium",
    },
    {
        "id": "next_attacker_path_after_ko",
        "group": "Hand Quality",
        "condition": "Have a visible path to your next attacker after one gets Knocked Out.",
        "confidence": "low",
    },
    {
        "id": "first_two_prize_or_even_until_online",
        "group": "Prize Race",
        "condition": "Take first 2-Prize KO or stay even until first Annihilape is online.",
        "confidence": "medium",
    },
]


PRODUCTIVE_TYPES = {
    "play_card", "bench_pokemon", "active_pokemon", "stadium_play", "evolve",
    "manual_attach", "attack", "use_ability", "activation", "draw_effect",
    "effect_attach", "damage_counters", "prize_taken", "retreat"
}


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def my_turn_map(events):
    turn_numbers = []
    seen = set()
    for event in events:
        if event["event_type"] == "turn_start" and event["turn_player"] == MY_PLAYER:
            turn = int(event["turn_number"])
            if turn not in seen:
                seen.add(turn)
                turn_numbers.append(turn)
    return {turn: i + 1 for i, turn in enumerate(turn_numbers)}


def my_turn_index(event, mapping):
    turn = event.get("turn_number")
    if not turn:
        return 0
    turn = int(turn)
    if turn == 0:
        return 0
    return mapping.get(turn, 0)


def met(status, detail):
    return status, detail


def evaluate_game(game, events):
    mapping = my_turn_map(events)
    my_events = [e for e in events if e["event_player"] == MY_PLAYER]
    my_turn_events = [e for e in my_events if my_turn_index(e, mapping) > 0]

    mankey_play_events = [
        e for e in my_events
        if e["card_name"] == "Mankey" and e["event_type"] in {"opening_hand", "active_pokemon", "bench_pokemon"}
    ]
    mankey_by_t2 = [
        e for e in mankey_play_events
        if e["event_type"] == "opening_hand" or my_turn_index(e, mapping) <= 2
    ]
    mankey_in_play_by_t3 = [
        e for e in my_events
        if e["card_name"] == "Mankey"
        and e["event_type"] in {"active_pokemon", "bench_pokemon"}
        and my_turn_index(e, mapping) <= 3
    ]
    primeape_by_t3 = [
        e for e in my_events
        if e["event_type"] == "evolve" and e["card_name"] == "Primeape" and my_turn_index(e, mapping) <= 3
    ]
    annihilape_attacks = [
        e for e in my_events
        if e["event_type"] == "attack" and e["card_name"] == "Annihilape"
    ]
    first_annihilape_attack_turn = min(
        [my_turn_index(e, mapping) for e in annihilape_attacks if my_turn_index(e, mapping) > 0],
        default=0,
    )
    impact_blows = [e for e in annihilape_attacks if e["value"] == "Impact Blow"]
    first_impact_turn = min([my_turn_index(e, mapping) for e in impact_blows if my_turn_index(e, mapping) > 0], default=0)
    full_impacts = [
        e for e in impact_blows
        if str(e["amount"]).lstrip("-").isdigit() and int(e["amount"]) >= 280
    ]
    risk_by_t2 = [
        e for e in my_events
        if e["card_name"] == "Risky Ruins"
        and e["event_type"] in {"stadium_play", "activation"}
        and my_turn_index(e, mapping) <= 2
    ]
    damage_engine_before_impact = [
        e for e in my_events
        if e["event_type"] in {"damage_counters", "attack", "activation"}
        and e["card_name"] in {"Risky Ruins", "Hawlucha"}
        and (not first_impact_turn or my_turn_index(e, mapping) <= first_impact_turn)
    ]

    dead_turns = []
    for turn_idx in sorted(set(my_turn_index(e, mapping) for e in my_turn_events)):
        if not any(e["event_type"] in PRODUCTIVE_TYPES for e in my_turn_events if my_turn_index(e, mapping) == turn_idx):
            dead_turns.append(turn_idx)

    my_prizes = []
    opp_prizes = []
    for e in events:
        if e["event_type"] != "prize_taken" or not str(e["amount"]).isdigit():
            continue
        turn_idx = my_turn_index(e, mapping)
        row = (turn_idx, int(e["amount"]))
        if e["event_player"] == MY_PLAYER:
            my_prizes.append(row)
        elif e["event_player"]:
            opp_prizes.append(row)
    first_two_prize = bool(my_prizes and my_prizes[0][1] >= 2)
    opp_prizes_before_online = sum(amount for turn, amount in opp_prizes if not first_annihilape_attack_turn or turn <= first_annihilape_attack_turn)
    my_prizes_before_online = sum(amount for turn, amount in my_prizes if not first_annihilape_attack_turn or turn <= first_annihilape_attack_turn)

    my_kos = [
        e for e in my_events
        if e["event_type"] == "knockout_received"
        and e["card_name"] in {"Primeape", "Annihilape", "Hawlucha", "Mankey"}
    ]
    next_attacker_visible = True
    if my_kos:
        for ko in my_kos:
            ko_turn = my_turn_index(ko, mapping)
            later_attack = any(
                e["event_type"] == "attack"
                and e["card_name"] in {"Primeape", "Annihilape", "Hawlucha"}
                and my_turn_index(e, mapping) >= ko_turn
                for e in my_events
            )
            later_evolve_or_bench = any(
                e["event_type"] in {"evolve", "bench_pokemon", "active_pokemon"}
                and e["card_name"] in {"Mankey", "Primeape", "Annihilape", "Hawlucha"}
                and my_turn_index(e, mapping) >= ko_turn
                for e in my_events
            )
            if not later_attack and not later_evolve_or_bench:
                next_attacker_visible = False
                break

    easy_prize_missed = any(
        e["event_type"] == "knockout_received"
        and e["card_name"] in {"Mankey", "Hawlucha", "Primeape"}
        and e.get("source_player") != MY_PLAYER
        for e in my_events
    )

    results = {
        "setup_mankey_by_turn2": met("met" if mankey_by_t2 else "missed",
                                    f"{len(mankey_by_t2)} Mankey/opening evidence by T2"),
        "setup_backup_mankey_by_turn3": met("met" if len(mankey_in_play_by_t3) >= 2 else "missed",
                                           f"{len(mankey_in_play_by_t3)} Mankey put into play by T3"),
        "evolve_primeape_by_turn3": met("met" if primeape_by_t3 else "missed",
                                       f"{len(primeape_by_t3)} Primeape evolution(s) by T3"),
        "annihilape_attack_by_turn4": met("met" if first_annihilape_attack_turn and first_annihilape_attack_turn <= 4 else "missed",
                                         f"first Annihilape attack on T{first_annihilape_attack_turn or 'none'}"),
        "damage_engine_before_impact": met("met" if damage_engine_before_impact else ("unknown" if not impact_blows else "missed"),
                                          f"{len(damage_engine_before_impact)} visible engine event(s) before first Impact Blow"),
        "full_power_impact_blow": met("met" if full_impacts else "missed",
                                     f"{len(full_impacts)} Impact Blow(s) at 280+ damage"),
        "risky_ruins_by_turn2": met("met" if risk_by_t2 else "missed",
                                   f"{len(risk_by_t2)} Risky Ruins play/activation event(s) by T2"),
        "avoid_easy_prize_from_damage": met("unknown" if not easy_prize_missed else "missed",
                                           "log cannot prove whether self-damage caused the prize"),
        "no_more_than_one_dead_turn": met("met" if len(dead_turns) <= 1 else "missed",
                                         f"dead turns: {dead_turns}"),
        "next_attacker_path_after_ko": met("met" if next_attacker_visible else "missed",
                                          "visible follow-up attacker path after KOs" if my_kos else "no attacker KO stress test"),
        "first_two_prize_or_even_until_online": met(
            "met" if first_two_prize or my_prizes_before_online >= opp_prizes_before_online else "missed",
            f"first 2-prize={first_two_prize}; prizes before online {my_prizes_before_online}-{opp_prizes_before_online}"
        ),
    }
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis-dir", default="data/analysis")
    parser.add_argument("--deck", default="decks/annihilape/v01.json")
    args = parser.parse_args()

    analysis_dir = Path(args.analysis_dir)
    deck = json.loads(Path(args.deck).read_text(encoding="utf-8"))
    games = read_csv(analysis_dir / "games.csv")
    events = read_csv(analysis_dir / "raw_events.csv")
    events_by_game = defaultdict(list)
    for event in events:
        events_by_game[event["game_id"]].append(event)

    detail_rows = []
    goal_meta = {goal["id"]: goal for goal in GOALS}
    for game in games:
        if game["has_game_log"] != "yes":
            continue
        results = evaluate_game(game, events_by_game[game["game_id"]])
        for goal_id, (status, detail) in results.items():
            meta = goal_meta[goal_id]
            detail_rows.append({
                "game_id": game["game_id"],
                "file": game["file"],
                "result": game["result"],
                "opponent": game["opponent"],
                "goal_id": goal_id,
                "goal_group": meta["group"],
                "condition": meta["condition"],
                "status": status,
                "confidence": meta["confidence"],
                "detail": detail,
            })

    summary_rows = []
    for goal in GOALS:
        rows = [row for row in detail_rows if row["goal_id"] == goal["id"]]
        counts = Counter(row["status"] for row in rows)
        known = counts["met"] + counts["missed"]
        summary_rows.append({
            "goal_id": goal["id"],
            "goal_group": goal["group"],
            "condition": goal["condition"],
            "confidence": goal["confidence"],
            "games": len(rows),
            "met": counts["met"],
            "missed": counts["missed"],
            "unknown": counts["unknown"],
            "met_rate_known": round(counts["met"] / known, 3) if known else "",
            "met_rate_all": round(counts["met"] / len(rows), 3) if rows else "",
        })

    group_rows = []
    groups = sorted(set(goal["group"] for goal in GOALS))
    for group in groups:
        rows = [row for row in detail_rows if row["goal_group"] == group]
        counts = Counter(row["status"] for row in rows)
        known = counts["met"] + counts["missed"]
        group_rows.append({
            "goal_group": group,
            "checks": len(rows),
            "met": counts["met"],
            "missed": counts["missed"],
            "unknown": counts["unknown"],
            "met_rate_known": round(counts["met"] / known, 3) if known else "",
            "met_rate_all": round(counts["met"] / len(rows), 3) if rows else "",
        })

    write_csv(analysis_dir / "success_condition_details.csv", detail_rows, [
        "game_id", "file", "result", "opponent", "goal_id", "goal_group", "condition",
        "status", "confidence", "detail"
    ])
    write_csv(analysis_dir / "success_condition_summary.csv", summary_rows, [
        "goal_id", "goal_group", "condition", "confidence", "games", "met", "missed",
        "unknown", "met_rate_known", "met_rate_all"
    ])
    write_csv(analysis_dir / "success_group_summary.csv", group_rows, [
        "goal_group", "checks", "met", "missed", "unknown", "met_rate_known", "met_rate_all"
    ])

    summary_path = analysis_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["success_conditions"] = len(GOALS)
    summary["success_condition_checks"] = len(detail_rows)
    summary["deck_name"] = deck["name"]
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "deck": deck["name"],
        "goals": len(GOALS),
        "checks": len(detail_rows),
        "output_dir": str(analysis_dir.resolve())
    }, indent=2))


if __name__ == "__main__":
    main()
