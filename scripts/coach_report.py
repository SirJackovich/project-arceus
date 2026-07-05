#!/usr/bin/env python3
import argparse
import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


MY_PLAYER = "SirJackovich"

USAGE_TYPES = {
    "play_card", "bench_pokemon", "active_pokemon", "stadium_play", "evolve",
    "manual_attach", "attack", "use_ability", "activation", "retreat",
}

CARD_TRACKING_TYPES = {
    "drawn": {"turn_draw_known", "known_drawn_card", "opening_hand"},
    "played": {"play_card", "bench_pokemon", "active_pokemon", "stadium_play", "manual_attach", "evolve"},
    "activated_triggered": {"activation", "use_ability", "attack"},
    "searched_fetched": set(),
    "discarded": {"discarded_card", "discard_effect", "knockout_received"},
    "shuffled_back": {"shuffle_into_deck"},
}

SEARCH_FETCH_CARDS = {
    "Buddy-Buddy Poffin",
    "Fighting Gong",
    "Pokegear 3.0",
    "Pokégear 3.0",
    "Poke Pad",
    "Poké Pad",
    "Colress's Tenacity",
    "Tarragon",
    "Hilda",
    "Night Stretcher",
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


def verbose_output_path(path):
    path = Path(path)
    return path.with_name(f"{path.stem}_verbose{path.suffix}")


def report_payload(payload, report_type):
    output = deterministic_payload(payload)
    output["report_type"] = report_type
    return output


def deterministic_payload(payload):
    evidence = dict(payload)
    evidence.pop("coach_snapshot", None)
    evidence.pop("recommendations", None)
    evidence.pop("game_narrative", None)
    evidence["layer"] = "deterministic_analyzer"
    evidence["purpose"] = "Structured evidence for the AI coach. Do not treat this as final coaching advice."
    return evidence


def write_report_outputs(args, concise_rendered, verbose_rendered, payload):
    write_text(args.output_md, concise_rendered)
    write_json(args.output_json, report_payload(payload, "concise"))
    write_json(Path(args.analysis_dir) / "deterministic_analysis.json", deterministic_payload(payload))
    write_text(verbose_output_path(args.output_md), verbose_rendered)
    write_json(verbose_output_path(args.output_json), report_payload(payload, "verbose"))
    if args.no_snapshot:
        return
    snapshot_dir = Path(args.snapshot_dir)
    prefix = snapshot_prefix(payload)
    write_text(snapshot_dir / f"{prefix}_coach_report.md", concise_rendered)
    write_json(snapshot_dir / f"{prefix}_coach_report.json", report_payload(payload, "concise"))
    write_text(snapshot_dir / f"{prefix}_coach_report_verbose.md", verbose_rendered)
    write_json(snapshot_dir / f"{prefix}_coach_report_verbose.json", report_payload(payload, "verbose"))


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


def adjusted_attack_damage(event):
    damage = as_int(event.get("amount"))
    raw_line = event.get("raw_line", "")
    match = re.search(r"took (-?\d+) (more|less) damage", raw_line)
    if not match:
        return damage
    delta = as_int(match.group(1))
    if match.group(2) == "less" and delta > 0:
        delta = -delta
    return damage + delta


def attack_has_lose_cool(game_events, attack):
    if not attack:
        return False
    details = related_effect_details(game_events, attack)
    text = " ".join(
        f"{event.get('raw_line', '')} {event.get('value', '')}"
        for event in [attack] + details
    )
    return "Lose Cool" in text


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


def group_events_by_game(events, selected_ids):
    grouped = defaultdict(list)
    for event in events:
        if event.get("game_id") in selected_ids:
            grouped[event.get("game_id")].append(event)
    return grouped


def hand_seen_cards(game_events):
    cards = set()
    for event in game_events:
        if event.get("event_player") != MY_PLAYER:
            continue
        if event.get("event_type") in {"opening_hand", "turn_draw_known", "known_drawn_card"} and event.get("card_name"):
            cards.add(canonical_name(event.get("card_name")))
    return cards


def card_tracking_summary(events, selected_ids, deck_cards):
    selected = [row for row in events if row.get("game_id") in selected_ids]
    mine = [row for row in selected if row.get("event_player") == MY_PLAYER]
    tracking = defaultdict(lambda: Counter({
        "drawn": 0,
        "played": 0,
        "activated_triggered": 0,
        "searched_fetched": 0,
        "discarded": 0,
        "shuffled_back": 0,
        "stuck_in_hand_unused": 0,
    }))

    for event in mine:
        card = event.get("card_name")
        source = event.get("source_card")
        event_type = event.get("event_type")
        if card:
            for metric, event_types in CARD_TRACKING_TYPES.items():
                if event_type in event_types:
                    tracking[card][metric] += 1
        if card and event_type == "known_drawn_card" and source in SEARCH_FETCH_CARDS:
            tracking[card]["searched_fetched"] += 1
        if source and source != card and event_type == "known_drawn_card" and source in SEARCH_FETCH_CARDS:
            tracking[source]["searched_fetched"] += 1

    grouped = group_events_by_game(events, selected_ids)
    for game_events in grouped.values():
        seen = hand_seen_cards(game_events)
        played = {
            canonical_name(event.get("card_name")) for event in game_events
            if event.get("event_player") == MY_PLAYER
            and event.get("card_name")
            and event.get("event_type") in CARD_TRACKING_TYPES["played"] | CARD_TRACKING_TYPES["activated_triggered"]
        }
        for card in deck_cards:
            if canonical_name(card) in seen and canonical_name(card) not in played:
                tracking[card]["stuck_in_hand_unused"] += 1

    rows = []
    for card, counts in tracking.items():
        rows.append({"card_name": card, **dict(counts)})
    rows.sort(key=lambda row: (-row["played"], -row["activated_triggered"], -row["drawn"], row["card_name"]))
    return rows


def related_effect_details(game_events, source_event):
    line_no = as_int(source_event.get("line_no"))
    source_card = source_event.get("card_name")
    turn = source_event.get("turn_number")
    details = []
    for event in game_events:
        if event.get("turn_number") != turn:
            continue
        if as_int(event.get("line_no")) <= line_no:
            continue
        if event.get("event_type") == "attack":
            break
        if event.get("source_card") == source_card or event.get("event_type") in {"effect_detail", "knockout_received", "prize_taken"}:
            details.append(event)
    return details


def annihilape_attack_quality(events, selected_games):
    selected_ids = {game["game_id"] for game in selected_games}
    grouped = group_events_by_game(events, selected_ids)
    rows = []
    for game in selected_games:
        game_id = game["game_id"]
        game_events = grouped[game_id]
        mapping = my_turn_map(game_events)
        attacks = [
            event for event in game_events
            if event.get("event_player") == MY_PLAYER
            and event.get("event_type") == "attack"
            and event.get("card_name") == "Annihilape"
        ]
        first = attacks[0] if attacks else None
        details = related_effect_details(game_events, first) if first else []
        lose_cool_active = attack_has_lose_cool(game_events, first) if first else False
        ko_taken = any(
            event.get("event_type") == "knockout_received"
            and event.get("source_card") == "Annihilape"
            and event.get("event_player") != MY_PLAYER
            for event in details
        ) if first else False
        damage = as_int(first.get("amount")) if first else 0
        final_damage = adjusted_attack_damage(first) if first else 0
        attack_name = first.get("value", "") if first else ""
        rows.append({
            "game": game_label(game_id),
            "game_id": game_id,
            "opponent": game.get("opponent", ""),
            "first_attack_turn": my_turn_index(first, mapping) if first else "none",
            "attack_name": attack_name or "none",
            "damage_dealt": damage if first else "",
            "final_damage_after_weakness_resistance": final_damage if first else "",
            "lose_cool_active": "yes" if lose_cool_active else "no" if first else "unknown",
            "ko_taken": "yes" if ko_taken else "no" if first else "unknown",
            "full_power_impact_blow": "yes" if attack_name == "Impact Blow" and lose_cool_active else "no" if first else "unknown",
        })
    return rows


def attack_decision_quality(events, selected_games):
    selected_ids = {game["game_id"] for game in selected_games}
    grouped = group_events_by_game(events, selected_ids)
    rows = []
    for game in selected_games:
        game_id = game["game_id"]
        game_events = grouped[game_id]
        mapping = my_turn_map(game_events)
        attacks = [
            event for event in game_events
            if event.get("event_player") == MY_PLAYER
            and event.get("event_type") == "attack"
            and event.get("card_name") in {"Annihilape", "Primeape"}
        ]
        for attack in attacks:
            details = related_effect_details(game_events, attack)
            line_no = as_int(attack.get("line_no"))
            turn_number = as_int(attack.get("turn_number"))
            attacker = attack.get("card_name", "")
            ko_taken = any(
                detail.get("event_type") == "knockout_received"
                and detail.get("source_card") == attacker
                and detail.get("event_player") != MY_PLAYER
                for detail in details
            )
            prize_value = sum(
                as_int(detail.get("amount"))
                for detail in details
                if detail.get("event_type") == "prize_taken" and detail.get("event_player") == MY_PLAYER
            )
            opponent_next_turns = sorted({
                as_int(event.get("turn_number")) for event in game_events
                if event.get("turn_player") and event.get("turn_player") != MY_PLAYER
                and as_int(event.get("turn_number")) > turn_number
            })
            next_opp_turn = opponent_next_turns[0] if opponent_next_turns else 0
            immediate_ko = any(
                event.get("event_type") == "knockout_received"
                and event.get("event_player") == MY_PLAYER
                and event.get("card_name") == attacker
                and as_int(event.get("turn_number")) == next_opp_turn
                and as_int(event.get("line_no")) > line_no
                for event in game_events
            )
            rows.append({
                "game": game_label(game_id),
                "game_id": game_id,
                "turn": my_turn_index(attack, mapping) or "unknown",
                "attacker": attacker,
                "attack": attack.get("value", ""),
                "target": attack.get("target_card", ""),
                "damage": as_int(attack.get("amount")),
                "final_damage_after_weakness_resistance": adjusted_attack_damage(attack),
                "ko": "yes" if ko_taken else "no",
                "prize_value": prize_value,
                "opponent_immediately_ko_attacker": "yes" if immediate_ko else "no" if next_opp_turn else "unknown",
                "evidence": attack.get("raw_line", ""),
            })
    return rows


def experiment_card_metrics(events, selected_games):
    selected_ids = {game["game_id"] for game in selected_games}
    grouped = group_events_by_game(events, selected_ids)
    waitress_played = 0
    waitress_attached = 0
    waitress_whiffs = 0
    waitress_games = set()
    ssp_attack_count = 0
    ssp_games = set()
    ssp_wins = 0
    ssp_losses = 0
    evidence = []
    ssp_attack_rows = []
    for game in selected_games:
        game_id = game["game_id"]
        game_events = grouped[game_id]
        my_waitress = [
            event for event in game_events
            if event.get("event_player") == MY_PLAYER
            and event.get("event_type") == "play_card"
            and event.get("card_name") == "Waitress"
        ]
        for play in my_waitress:
            waitress_played += 1
            waitress_games.add(game_id)
            line_no = as_int(play.get("line_no"))
            turn = play.get("turn_number")
            attached = any(
                event.get("event_player") == MY_PLAYER
                and event.get("source_card") == "Waitress"
                and event.get("event_type") == "effect_attach"
                and as_int(event.get("line_no")) > line_no
                and event.get("turn_number") == turn
                for event in game_events
            )
            if attached:
                waitress_attached += 1
            else:
                waitress_whiffs += 1
            evidence.append({
                "game": game_label(game_id),
                "card": "Waitress",
                "result": "attached energy" if attached else "whiff/no visible attach",
                "evidence": play.get("raw_line", ""),
            })
        ssp_attacks = [
            event for event in game_events
            if event.get("event_player") == MY_PLAYER
            and event.get("event_type") == "attack"
            and event.get("card_name") == "Annihilape"
            and event.get("value") in {"Tantrum", "Destined Fight"}
        ]
        if ssp_attacks:
            ssp_games.add(game_id)
            ssp_attack_count += len(ssp_attacks)
            if game.get("result") == "win":
                ssp_wins += 1
            elif game.get("result") == "loss":
                ssp_losses += 1
            for attack in ssp_attacks:
                details = related_effect_details(game_events, attack)
                line_no = as_int(attack.get("line_no"))
                turn_number = as_int(attack.get("turn_number"))
                next_my_turns = sorted({
                    as_int(event.get("turn_number")) for event in game_events
                    if event.get("turn_player") == MY_PLAYER and as_int(event.get("turn_number")) > turn_number
                })
                next_my_turn = next_my_turns[0] if next_my_turns else 0
                my_prizes = sum(
                    as_int(event.get("amount"))
                    for event in details
                    if event.get("event_type") == "prize_taken" and event.get("event_player") == MY_PLAYER
                )
                opponent_prizes = sum(
                    as_int(event.get("amount"))
                    for event in game_events
                    if event.get("event_type") == "prize_taken"
                    and event.get("event_player") not in {"", MY_PLAYER}
                    and as_int(event.get("line_no")) > line_no
                    and (not next_my_turn or as_int(event.get("turn_number")) < next_my_turn)
                )
                if my_prizes > opponent_prizes:
                    outcome = "positive"
                elif opponent_prizes > my_prizes:
                    outcome = "negative"
                else:
                    outcome = "neutral"
                ssp_row = {
                    "game": game_label(game_id),
                    "game_number": game_number(game_id),
                    "card": "Annihilape SSP 100",
                    "attack_used": attack.get("value", ""),
                    "target": attack.get("target_card", ""),
                    "prizes_gained": my_prizes,
                    "opponent_prizes_gained": opponent_prizes,
                    "outcome": outcome,
                    "result": attack.get("value", ""),
                    "evidence": attack.get("raw_line", ""),
                }
                evidence.append(ssp_row)
                ssp_attack_rows.append(ssp_row)
    return {
        "current_experiment": {
            "changed_cards": ["1 Annihilape SSP 100", "2 Waitress ASC 215"],
            "target_question": "Do SSP Annihilape and Waitress improve rebuilds, tempo, or awkward evolution/energy games?",
        },
        "waitress_played_count": waitress_played,
        "waitress_attached_energy_count": waitress_attached,
        "waitress_whiff_count": waitress_whiffs,
        "waitress_games": [game_label(game_id) for game_id in sorted(waitress_games, key=game_number)],
        "ssp_annihilape_attack_count": ssp_attack_count,
        "ssp_annihilape_games": [game_label(game_id) for game_id in sorted(ssp_games, key=game_number)],
        "ssp_attacks": ssp_attack_rows,
        "ssp_outcome": {
            "wins_when_ssp_attacked": ssp_wins,
            "losses_when_ssp_attacked": ssp_losses,
            "neutral_no_ssp_attack_games": len(selected_games) - len(ssp_games),
            "classification": "neutral" if ssp_attack_count == 0 or ssp_wins == ssp_losses else "won" if ssp_wins > ssp_losses else "lost",
            "inference_note": "SSP Annihilape is inferred from unique attacks Tantrum and Destined Fight because logs omit set IDs.",
        },
        "evidence": evidence[:12],
    }


def candidate_strengths(goals, stadium, evolution_line, line_rebuild):
    rows = []
    total = len(stadium)
    risky_by_t2 = sum(1 for row in stadium if row.get("risky_ruins_played_by_turn") not in {"none", ""} and as_int(row.get("risky_ruins_played_by_turn")) <= 2)
    if total:
        rows.append({"strength": "Risky Ruins access", "metric": f"{risky_by_t2}/{total} by Turn 2", "confidence": "high" if risky_by_t2 / total >= 0.7 else "medium"})
    stage1_goal = next((goal for goal in goals if goal.get("goal_id") == "evolve_primeape_by_turn3"), None)
    if stage1_goal and stage1_goal.get("games"):
        met = as_int(stage1_goal.get("met"))
        games = as_int(stage1_goal.get("games"))
        rows.append({"strength": "Stage 1 setup", "metric": f"{met}/{games} Primeape by Turn 3", "confidence": "high" if games and met / games >= 0.7 else "medium"})
    basic_goal = next((goal for goal in goals if goal.get("goal_id") == "setup_mankey_by_turn2"), None)
    if basic_goal and basic_goal.get("games"):
        met = as_int(basic_goal.get("met"))
        games = as_int(basic_goal.get("games"))
        rows.append({"strength": "early Basic setup", "metric": f"{met}/{games} Mankey by Turn 2", "confidence": "high" if games and met / games >= 0.7 else "medium"})
    rebuild_counts = Counter(row.get("state") for row in line_rebuild)
    rebuild_success = rebuild_counts.get("rebuilt complete line", 0) + rebuild_counts.get("partial rebuild", 0)
    tested = len(line_rebuild) - rebuild_counts.get("not tested", 0)
    if tested:
        rows.append({"strength": "recovery/rebuild", "metric": f"{rebuild_success}/{tested} visible rebuilds after line break", "confidence": "medium"})
    return rows


def visible_hand_events(game_events):
    return [
        event for event in game_events
        if event.get("event_player") == MY_PLAYER
        and event.get("card_name")
        and event.get("event_type") in {"opening_hand", "turn_draw_known", "known_drawn_card"}
    ]


def first_event(events, predicate):
    matches = [event for event in events if predicate(event)]
    matches.sort(key=lambda event: as_int(event.get("line_no")))
    return matches[0] if matches else None


def evolution_line_analysis(events, selected_games):
    selected_ids = {game["game_id"] for game in selected_games}
    grouped = group_events_by_game(events, selected_ids)
    rows = []
    bottlenecks = Counter({
        "missing Mankey": 0,
        "missing Primeape": 0,
        "missing Annihilape": 0,
        "completed by Turn 4": 0,
        "unknown/no visible Mankey": 0,
    })
    hand_gaps = Counter({
        "Annihilape in hand, no Primeape": 0,
        "Primeape in hand/play, no Annihilape": 0,
    })

    for game in selected_games:
        game_id = game["game_id"]
        game_events = grouped[game_id]
        mapping = my_turn_map(game_events)
        mine = [event for event in game_events if event.get("event_player") == MY_PLAYER]
        hand_events = visible_hand_events(game_events)

        first_mankey = first_event(
            mine,
            lambda event: event.get("card_name") == "Mankey" and event.get("event_type") in {"active_pokemon", "bench_pokemon"},
        )
        first_primeape = first_event(
            mine,
            lambda event: event.get("card_name") == "Primeape" and event.get("event_type") in {"evolve", "active_pokemon", "bench_pokemon"},
        )
        first_annihilape_completion = first_event(
            mine,
            lambda event: event.get("card_name") == "Annihilape" and event.get("event_type") == "evolve",
        )
        first_annihilape_seen = first_event(hand_events, lambda event: event.get("card_name") == "Annihilape")
        first_primeape_seen = first_event(
            mine + hand_events,
            lambda event: event.get("card_name") == "Primeape"
            and event.get("event_type") in {"opening_hand", "turn_draw_known", "known_drawn_card", "evolve", "active_pokemon", "bench_pokemon"},
        )

        completion_turn = my_turn_index(first_annihilape_completion, mapping) if first_annihilape_completion else 0
        hidden_or_mulligan = (
            as_int(game.get("my_mulligans")) > 0
            or game.get("my_opening_hand_visibility") in {"hidden", "hidden_after_mulligan"}
        )
        mankey_turn = my_turn_index(first_mankey, mapping) if first_mankey else 0
        primeape_turn = my_turn_index(first_primeape, mapping) if first_primeape else 0

        if completion_turn and completion_turn <= 4:
            bottleneck = "completed by Turn 4"
        elif not first_mankey:
            bottleneck = "unknown/no visible Mankey" if hidden_or_mulligan else "missing Mankey"
        elif not first_primeape:
            bottleneck = "missing Primeape"
        else:
            bottleneck = "missing Annihilape"
        bottlenecks[bottleneck] += 1

        annihilape_without_primeape = bool(
            first_annihilape_seen
            and (not first_primeape or as_int(first_annihilape_seen.get("line_no")) < as_int(first_primeape.get("line_no")))
        )
        primeape_without_annihilape = bool(
            first_primeape_seen
            and not first_annihilape_completion
            and not first_annihilape_seen
        )
        if annihilape_without_primeape:
            hand_gaps["Annihilape in hand, no Primeape"] += 1
        if primeape_without_annihilape:
            hand_gaps["Primeape in hand/play, no Annihilape"] += 1

        rows.append({
            "game": game_label(game_id),
            "game_id": game_id,
            "first_completion_turn": completion_turn or "none",
            "completed_by_turn4": "yes" if completion_turn and completion_turn <= 4 else "no",
            "bottleneck": bottleneck,
            "mankey_turn": mankey_turn or "none",
            "primeape_turn": primeape_turn or "none",
            "annihilape_seen_turn": my_turn_index(first_annihilape_seen, mapping) if first_annihilape_seen else "none",
            "annihilape_in_hand_no_primeape": "yes" if annihilape_without_primeape else "no",
            "primeape_no_annihilape": "yes" if primeape_without_annihilape else "no",
        })

    miss_total = sum(count for label, count in bottlenecks.items() if label != "completed by Turn 4")
    return {
        "rows": rows,
        "bottlenecks": dict(bottlenecks),
        "hand_gaps": dict(hand_gaps),
        "miss_total": miss_total,
    }


def rebuild_after_line_break(events, selected_games):
    selected_ids = {game["game_id"] for game in selected_games}
    grouped = group_events_by_game(events, selected_ids)
    rows = []
    for game in selected_games:
        game_id = game["game_id"]
        game_events = grouped[game_id]
        mine = [event for event in game_events if event.get("event_player") == MY_PLAYER]
        break_event = first_event(
            mine,
            lambda event: event.get("event_type") == "knockout_received"
            and event.get("card_name") in {"Mankey", "Primeape", "Annihilape"}
            and event.get("source_player") != MY_PLAYER,
        )
        if not break_event:
            rows.append({"game": game_label(game_id), "game_id": game_id, "state": "not tested", "evidence": "No visible KO of the Mankey line."})
            continue

        break_line = as_int(break_event.get("line_no"))
        after = [event for event in mine if as_int(event.get("line_no")) > break_line]
        rebuilt_annihilape = first_event(after, lambda event: event.get("event_type") == "evolve" and event.get("card_name") == "Annihilape")
        partial = first_event(
            after,
            lambda event: event.get("card_name") in {"Mankey", "Primeape", "Annihilape"}
            and event.get("event_type") in {"active_pokemon", "bench_pokemon", "evolve", "turn_draw_known", "known_drawn_card"},
        )
        if rebuilt_annihilape:
            state = "rebuilt complete line"
            evidence = rebuilt_annihilape.get("raw_line", "")
        elif partial:
            state = "partial rebuild"
            evidence = partial.get("raw_line", "")
        else:
            state = "no visible rebuild"
            evidence = break_event.get("raw_line", "")
        rows.append({"game": game_label(game_id), "game_id": game_id, "state": state, "evidence": evidence})
    return rows


def backup_attacker_summary(events, selected_games):
    selected_ids = {game["game_id"] for game in selected_games}
    grouped = group_events_by_game(events, selected_ids)
    rows = []
    for game in selected_games:
        game_id = game["game_id"]
        game_events = grouped[game_id]
        mapping = my_turn_map(game_events)
        ko_events = [
            event for event in game_events
            if event.get("event_player") == MY_PLAYER
            and event.get("event_type") == "knockout_received"
            and event.get("card_name") == "Annihilape"
            and event.get("source_player") != MY_PLAYER
        ]
        if not ko_events:
            rows.append({"game": game_label(game_id), "game_id": game_id, "state": "not tested", "evidence": "No opposing KO of first Annihilape."})
            continue
        ko = ko_events[0]
        ko_turn = as_int(ko.get("turn_number"))
        next_my_turns = sorted({
            as_int(event.get("turn_number")) for event in game_events
            if event.get("turn_player") == MY_PLAYER and as_int(event.get("turn_number")) > ko_turn
        })
        next_turn = next_my_turns[0] if next_my_turns else 0
        next_turn_events = [event for event in game_events if as_int(event.get("turn_number")) == next_turn]
        next_attack = next((
            event for event in next_turn_events
            if event.get("event_player") == MY_PLAYER
            and event.get("event_type") == "attack"
            and event.get("card_name") in {"Annihilape", "Primeape", "Hawlucha"}
        ), None)
        setup_events = [
            event for event in next_turn_events
            if event.get("event_player") == MY_PLAYER
            and event.get("event_type") in {"bench_pokemon", "evolve", "manual_attach", "effect_attach"}
            and (event.get("card_name") in {"Mankey", "Primeape", "Annihilape", "Hawlucha", "Basic Fighting Energy"}
                 or event.get("target_card") in {"Primeape", "Annihilape", "Hawlucha"})
        ]
        board_after = any(
            event.get("event_player") == MY_PLAYER
            and event.get("card_name") in {"Mankey", "Primeape", "Annihilape", "Hawlucha"}
            and as_int(event.get("turn_number")) >= ko_turn
            for event in game_events
        )
        if next_attack and not setup_events:
            state = "ready now"
        elif next_attack:
            state = "reachable next turn"
        elif board_after:
            state = "not reachable"
        else:
            state = "no board"
        evidence = next_attack.get("raw_line", "") if next_attack else (setup_events[0].get("raw_line", "") if setup_events else ko.get("raw_line", ""))
        rows.append({"game": game_label(game_id), "game_id": game_id, "state": state, "evidence": evidence})
    return rows


def stadium_quality(events, selected_games):
    selected_ids = {game["game_id"] for game in selected_games}
    grouped = group_events_by_game(events, selected_ids)
    rows = []
    for game in selected_games:
        game_id = game["game_id"]
        game_events = grouped[game_id]
        mapping = my_turn_map(game_events)
        my_risky = [
            event for event in game_events
            if event.get("event_player") == MY_PLAYER
            and event.get("event_type") == "stadium_play"
            and event.get("card_name") == "Risky Ruins"
        ]
        first_risky_turn = my_turn_index(my_risky[0], mapping) if my_risky else "none"
        first_mankey = next((
            event for event in game_events
            if event.get("event_player") == MY_PLAYER
            and event.get("event_type") in {"bench_pokemon", "active_pokemon"}
            and event.get("card_name") == "Mankey"
        ), None)
        before_mankey = bool(my_risky and first_mankey and as_int(my_risky[0].get("line_no")) < as_int(first_mankey.get("line_no")))
        replaced = sum(
            1 for event in game_events
            if event.get("event_player") != MY_PLAYER
            and event.get("event_type") == "stadium_play"
            and event.get("card_name") != "Risky Ruins"
        )
        first_full = next((
            event for event in game_events
            if event.get("event_player") == MY_PLAYER
            and event.get("event_type") == "attack"
            and event.get("card_name") == "Annihilape"
            and event.get("value") == "Impact Blow"
            and as_int(event.get("amount")) >= 280
        ), None)
        depended = "unknown"
        if first_full:
            risky_before = any(
                event.get("event_player") == MY_PLAYER
                and event.get("source_card") == "Risky Ruins"
                and event.get("event_type") == "damage_counters"
                and as_int(event.get("line_no")) < as_int(first_full.get("line_no"))
                for event in game_events
            )
            depended = "yes" if risky_before else "no"
        rows.append({
            "game": game_label(game_id),
            "game_id": game_id,
            "risky_ruins_played_by_turn": first_risky_turn,
            "in_play_before_mankey_benched": "yes" if before_mankey else "no" if my_risky and first_mankey else "unknown",
            "opponent_replaced_it": replaced,
            "first_full_power_depended_on_it": depended,
        })
    return rows


def mulligan_warnings(selected_games):
    rows = []
    for game in selected_games:
        my_mulligans = as_int(game.get("my_mulligans"))
        visibility = game.get("my_opening_hand_visibility", "")
        if my_mulligans or visibility == "hidden_after_mulligan":
            rows.append({
                "game": game_label(game.get("game_id", "")),
                "game_id": game.get("game_id", ""),
                "my_mulligans": my_mulligans,
                "opening_hand_visibility": visibility or "unknown",
                "warning": "Opening hand after mulligan was hidden; hand-based conclusions are lower confidence.",
            })
    return rows


def mulligan_rate_summary(selected_games):
    rows = []
    total_mulligans = 0
    games_with_mulligan = 0
    losses_with_mulligan = 0
    for game in selected_games:
        count = as_int(game.get("my_mulligans"))
        total_mulligans += count
        if count:
            games_with_mulligan += 1
            if game.get("result") == "loss":
                losses_with_mulligan += 1
        rows.append({
            "game": game_label(game.get("game_id", "")),
            "game_id": game.get("game_id", ""),
            "mulligans": count,
            "result": game.get("result", ""),
            "lost_after_mulligan": "yes" if count and game.get("result") == "loss" else "no" if count else "not_applicable",
        })
    return {
        "mulligans_per_game": rows,
        "games": len(selected_games),
        "games_with_1_plus_mulligan": games_with_mulligan,
        "total_mulligans": total_mulligans,
        "average_mulligans": round(total_mulligans / len(selected_games), 2) if selected_games else 0,
        "losses_after_mulligan": losses_with_mulligan,
        "note": "This deck has low Basic count; mulligans may be expected.",
    }


def format_reason(reason):
    if isinstance(reason, dict):
        return f"{reason.get('reason', 'unknown')} [{reason.get('confidence', 'low')}]"
    return str(reason)


def annihilape_miss_reasons(events, selected_games, success_rows):
    selected_ids = {game["game_id"] for game in selected_games}
    game_by_id = {game["game_id"]: game for game in selected_games}
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
        "no Mankey": 0,
        "unknown/no visible Mankey": 0,
        "no Primeape/evolution": 0,
        "no Annihilape": 0,
        "no energy": 0,
        "no damage counters / Lose Cool inactive": 0,
        "KO/disruption": 0,
        "unknown": 0,
    })
    details = []

    for game_id in sorted(missed_ids, key=game_number):
        game_events = grouped[game_id]
        mapping = my_turn_map(game_events)
        mine = [event for event in game_events if event.get("event_player") == MY_PLAYER]
        early = [event for event in mine if my_turn_index(event, mapping) <= 4]
        early_board = [event for event in mine if my_turn_index(event, mapping) <= 3]
        game = game_by_id.get(game_id, {})
        hidden_or_mulligan = (
            as_int(game.get("my_mulligans")) > 0
            or game.get("my_opening_hand_visibility") in {"hidden", "hidden_after_mulligan"}
        )

        mankey_ready = any(
            event.get("event_type") in {"active_pokemon", "bench_pokemon"}
            and event.get("card_name") == "Mankey"
            for event in early_board
        )

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

        def add_reason(label, confidence):
            reasons.append({"reason": label, "confidence": confidence})

        if not mankey_ready:
            if hidden_or_mulligan:
                add_reason("unknown/no visible Mankey", "low")
            else:
                add_reason("no Mankey", "medium")
        if mankey_ready and not primeape_ready:
            add_reason("no Primeape/evolution", "low" if hidden_or_mulligan else "medium")
        if primeape_ready and not rare_candy_seen and not annihilape_ready:
            add_reason("no Annihilape", "low" if hidden_or_mulligan else "medium")
        if annihilape_ready and not energy_on_annihilape:
            add_reason("no energy", "low" if hidden_or_mulligan else "medium")
        if annihilape_ready and energy_on_annihilape and not damage_setup:
            add_reason("no damage counters / Lose Cool inactive", "low" if hidden_or_mulligan else "medium")
        if disrupted:
            add_reason("KO/disruption", "high")
        if not reasons:
            add_reason("unknown", "low" if hidden_or_mulligan else "medium")

        for reason in reasons:
            counts[reason["reason"]] += 1
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


def dominant_evolution_recommendation(evolution_analysis):
    miss_total = evolution_analysis.get("miss_total", 0)
    if not miss_total:
        return None
    bottlenecks = evolution_analysis.get("bottlenecks", {})
    candidates = [
        ("missing Annihilape", "Stage 2 access", "Improve Annihilape access before touching Rare Candy or Energy counts.", "For the next 10 games, record whether Primeape was online before Annihilape was found."),
        ("missing Primeape", "Stage 1 access", "Improve Primeape access or evolution sequencing before changing attack support cards.", "For the next 10 games, record whether Mankey survived long enough to become Primeape."),
        ("missing Mankey", "Basic setup", "Improve early Mankey setup before tuning the late-game package.", "For the next 10 games, track whether two Mankey are in play by your Turn 3."),
        ("unknown/no visible Mankey", "hidden Basic setup", "Treat the Basic setup miss as low-confidence because the hand was hidden; verify whether Mankey was actually unavailable or just not visible in the log.", "For the next 10 games, note whether opening hand had Mankey after mulligans."),
    ]
    dominant = max(candidates, key=lambda item: bottlenecks.get(item[0], 0))
    label, theme, recommendation, experiment = dominant
    count = bottlenecks.get(label, 0)
    if count == 0:
        return None
    share = count / miss_total
    evidence = [row["game"] for row in evolution_analysis.get("rows", []) if row.get("bottleneck") == label][:5]
    confidence = "high" if share > 0.5 and count >= 3 else "medium" if count >= 2 else "low"
    return {
        "observation": f"Evolution bottleneck: {theme} appears in {count}/{miss_total} incomplete-line games ({pct(count, miss_total)}%).",
        "evidence": evidence,
        "recommendation": recommendation,
        "confidence": confidence,
        "next_experiment": experiment,
    }


def possible_loss_factors_from_evidence(evolution_analysis, line_rebuild, goals, mulligans):
    factors = []
    miss_total = evolution_analysis.get("miss_total", 0)
    bottlenecks = evolution_analysis.get("bottlenecks", {})
    if miss_total:
        for label in ["missing Annihilape", "missing Primeape", "missing Mankey", "unknown/no visible Mankey"]:
            count = bottlenecks.get(label, 0)
            if not count:
                continue
            evidence = [row["game"] for row in evolution_analysis.get("rows", []) if row.get("bottleneck") == label][:5]
            confidence = "high" if count / miss_total > 0.5 and count >= 3 else "medium" if count >= 2 else "low"
            factors.append({
                "factor": label,
                "category": "evolution bottleneck",
                "count": count,
                "sample": miss_total,
                "evidence": evidence,
                "confidence": "low" if label.startswith("unknown") else confidence,
            })
    rebuild_counts = Counter(row["state"] for row in line_rebuild)
    if rebuild_counts.get("no visible rebuild", 0):
        factors.append({
            "factor": "no visible rebuild after line break",
            "category": "rebuild",
            "count": rebuild_counts["no visible rebuild"],
            "sample": len(line_rebuild),
            "evidence": [row["game"] for row in line_rebuild if row["state"] == "no visible rebuild"][:5],
            "confidence": "medium",
        })
    for goal in goals:
        if goal.get("missed", 0) and goal.get("confidence") != "low":
            factors.append({
                "factor": goal.get("condition", ""),
                "category": goal.get("goal_group", ""),
                "count": goal.get("missed", 0),
                "sample": goal.get("games", 0),
                "evidence": goal.get("missed_games", [])[:5],
                "confidence": goal.get("confidence", "medium"),
            })
    if mulligans:
        factors.append({
            "factor": "hidden hand after mulligan",
            "category": "confidence warning",
            "count": len(mulligans),
            "sample": len(mulligans),
            "evidence": [row["game"] for row in mulligans[:5]],
            "confidence": "low",
        })
    return factors[:12]


def game_narrative(evolution, line_rebuild):
    bottlenecks = evolution.get("bottlenecks", {})
    rows = evolution.get("rows", [])
    miss_total = evolution.get("miss_total", 0)
    if not rows:
        return "Not enough visible game data to describe the pattern yet."
    completed = bottlenecks.get("completed by Turn 4", 0)
    dominant_label = ""
    if miss_total:
        dominant_label = max(
            (label for label in bottlenecks if label != "completed by Turn 4"),
            key=lambda label: bottlenecks.get(label, 0),
            default="",
        )
    rebuild_counts = Counter(row["state"] for row in line_rebuild)
    if dominant_label == "missing Annihilape":
        return "The deck often established the lower evolution line, but stalled before finding Annihilape and lost pressure."
    if dominant_label == "missing Primeape":
        return "The deck found Basic setup often enough, but the line frequently stalled before Primeape came online."
    if dominant_label in {"missing Mankey", "unknown/no visible Mankey"}:
        return "The deck's losses most often start with an unstable Mankey setup, making the rest of the evolution plan late or invisible."
    if rebuild_counts.get("no visible rebuild", 0):
        return "The first evolution line usually appears, but rebuilds after a KO are not consistently visible."
    if completed:
        return "The deck usually assembles Annihilape, so the next gains are more likely in damage math and rebuild planning."
    return "The current sample does not show one dominant evolution-line failure pattern yet."


def friendly_condition(condition):
    replacements = {
        "Attack with at least one full-power 280+ damage Impact Blow.": "Full-power Impact Blow",
        "Attack with at least one Lose Cool/full-power Impact Blow.": "Full-power Impact Blow",
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
    if recommendations and recommendations[0].get("observation", "").startswith("Evolution bottleneck:"):
        weakness = recommendations[0]["observation"].split("Evolution bottleneck:", 1)[1].split(" appears", 1)[0].strip()

    if miss_goals and miss_goals[0]["goal_id"] == "full_power_impact_blow":
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
    card_tracking = card_tracking_summary(events, selected_ids, deck_cards)
    attack_quality = annihilape_attack_quality(events, selected_games)
    attack_decisions = attack_decision_quality(events, selected_games)
    evolution_line = evolution_line_analysis(events, selected_games)
    line_rebuild = rebuild_after_line_break(events, selected_games)
    backup_attackers = backup_attacker_summary(events, selected_games)
    stadium = stadium_quality(events, selected_games)
    miss_reasons = annihilape_miss_reasons(events, selected_games, success_rows)
    mulligans = mulligan_warnings(selected_games)
    mulligan_rates = mulligan_rate_summary(selected_games)
    possible_loss_factors = possible_loss_factors_from_evidence(evolution_line, line_rebuild, goals, mulligans)
    experiment_metrics = experiment_card_metrics(events, selected_games)
    strengths = candidate_strengths(goals, stadium, evolution_line, line_rebuild)

    recommendations = []
    evolution_rec = dominant_evolution_recommendation(evolution_line)
    if evolution_rec:
        recommendations.append(evolution_rec)
    recommendations.extend(
        recommendation_for_goal(goal)
        for goal in goals
        if goal["missed"] > 0 and goal.get("confidence") != "low"
        and goal.get("goal_id") != "annihilape_attack_by_turn4"
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
        "card_tracking": card_tracking,
        "annihilape_attack_quality": attack_quality,
        "attack_decision_quality": attack_decisions,
        "evolution_line": evolution_line,
        "line_rebuild": line_rebuild,
        "backup_attacker": backup_attackers,
        "stadium_quality": stadium,
        "annihilape_attack_miss_reasons": miss_reasons,
        "mulligan_warnings": mulligans,
        "mulligan_rate": mulligan_rates,
        "possible_loss_factors": possible_loss_factors,
        "experiment_metrics": experiment_metrics,
        "candidate_strengths": strengths,
        "game_narrative": game_narrative(evolution_line, line_rebuild),
        "coach_snapshot": snapshot,
        "recommendations": recommendations,
    }
    return payload


def render_report(payload):
    summary = payload["summary"]
    lines = []
    lines.append("# Project Arceus Deterministic Evidence Report")
    lines.append("")
    lines.append(f"Scope: {payload['scope']}")
    lines.append(f"Record: {summary['wins']}-{summary['losses']} ({summary['win_rate']}% win rate)")
    lines.append(
        f"Went first: {summary['went_first_wins']}/{summary['went_first']} wins; "
        f"went second: {summary['went_second_wins']}/{summary['went_second']} wins"
    )
    lines.append("")

    lines.append("## Recent Games")
    for game in payload["games"]:
        first = "first" if game["went_first"] == "yes" else "second" if game["went_first"] == "no" else "unknown"
        lines.append(f"- {game['game']}: {game['result']} vs {game['opponent']} going {first}")
    lines.append("")

    if payload.get("mulligan_warnings"):
        lines.append("## Mulligan Warning")
        lines.append("Opening hand after mulligan was hidden; hand-based conclusions are lower confidence.")
        evidence = ", ".join(row["game"] for row in payload["mulligan_warnings"][:6])
        lines.append(f"Evidence: {evidence}")
        lines.append("")

    lines.append("## Biggest Misses")
    misses = [goal for goal in payload["success_conditions"] if goal["missed"] > 0]
    for goal in misses[:6]:
        lines.append(
            f"- {goal['goal_group']} ({goal['confidence']} confidence): "
            f"missed {goal['missed']}/{goal['games']} - {goal['condition']}"
        )
        if goal["missed_games"]:
            lines.append(f"  Evidence: {', '.join(goal['missed_games'])}")
    if not misses:
        lines.append("- No success-condition misses in this sample.")
    lines.append("")

    lines.append("## Card And Attack Signals")
    played_cards = [row for row in payload["card_tracking"] if row.get("played", 0) > 0][:6]
    if played_cards:
        lines.append("Top played cards: " + ", ".join(f"{row['card_name']} ({row['played']})" for row in played_cards))
    triggered_cards = sorted(payload["card_tracking"], key=lambda row: -row.get("activated_triggered", 0))[:4]
    triggered_cards = [row for row in triggered_cards if row.get("activated_triggered", 0) > 0]
    if triggered_cards:
        lines.append("Top activated/attack cards: " + ", ".join(f"{row['card_name']} ({row['activated_triggered']})" for row in triggered_cards))
    top_attacks = payload["events"]["top_attacks"][:4]
    for attack in top_attacks:
        lines.append(
            f"- {attack['attack']}: {attack['uses']} uses, {attack['avg_damage']} avg damage"
        )
    unused = payload["events"].get("unused_deck_cards", [])[:6]
    if unused:
        lines.append("Recently unused deck cards: " + ", ".join(unused))
    lines.append("")

    lines.append("## Card Flow")
    for row in payload["card_tracking"][:10]:
        lines.append(
            f"- {row['card_name']}: drawn {row['drawn']}, played {row['played']}, "
            f"activated/triggered {row['activated_triggered']}, searched/fetched {row['searched_fetched']}, "
            f"discarded {row['discarded']}, shuffled back {row['shuffled_back']}, "
            f"stuck/unused {row['stuck_in_hand_unused']}"
        )
    lines.append("")

    lines.append("## Evolution Line Assembly")
    evolution = payload["evolution_line"]
    rows = evolution.get("rows", [])
    completed_by_t4 = sum(1 for row in rows if row.get("completed_by_turn4") == "yes")
    lines.append(f"- First complete Annihilape line by Turn 4: {completed_by_t4}/{len(rows)}")
    for label in ["missing Mankey", "missing Primeape", "missing Annihilape", "unknown/no visible Mankey"]:
        count = evolution.get("bottlenecks", {}).get(label, 0)
        if count:
            evidence = [row["game"] for row in rows if row.get("bottleneck") == label][:5]
            lines.append(f"- {label}: {count} ({', '.join(evidence)})")
    hand_gaps = evolution.get("hand_gaps", {})
    lines.append(f"- Annihilape in hand, no Primeape: {hand_gaps.get('Annihilape in hand, no Primeape', 0)}")
    lines.append(f"- Primeape in hand/play, no Annihilape: {hand_gaps.get('Primeape in hand/play, no Annihilape', 0)}")
    lines.append("")

    lines.append("## Rebuild After Line Break")
    rebuild_counts = Counter(row["state"] for row in payload["line_rebuild"])
    for state in ["rebuilt complete line", "partial rebuild", "no visible rebuild", "not tested"]:
        if rebuild_counts[state]:
            evidence = [row["game"] for row in payload["line_rebuild"] if row["state"] == state][:5]
            lines.append(f"- {state}: {rebuild_counts[state]} ({', '.join(evidence)})")
    lines.append("")

    lines.append("## Annihilape Attack Quality")
    for row in payload["annihilape_attack_quality"][-6:]:
        if row["first_attack_turn"] == "none":
            lines.append(f"- {row['game']}: no Annihilape attack")
        else:
            lines.append(
                f"- {row['game']}: T{row['first_attack_turn']} {row['attack_name']} "
                f"for {row['damage_dealt']} damage; Lose Cool {row['lose_cool_active']}; "
                f"KO {row['ko_taken']}; full-power Impact Blow {row['full_power_impact_blow']}"
            )
    lines.append("")

    lines.append("## Backup Attacker After First Annihilape KO")
    backup_counts = Counter(row["state"] for row in payload["backup_attacker"])
    for state in ["ready now", "reachable next turn", "not reachable", "no board", "not tested"]:
        if backup_counts[state]:
            evidence = [row["game"] for row in payload["backup_attacker"] if row["state"] == state][:5]
            lines.append(f"- {state}: {backup_counts[state]} ({', '.join(evidence)})")
    lines.append("")

    lines.append("## Stadium Quality")
    risky_by_t2 = [row for row in payload["stadium_quality"] if row["risky_ruins_played_by_turn"] not in {"none", ""} and as_int(row["risky_ruins_played_by_turn"]) <= 2]
    before_mankey = [row for row in payload["stadium_quality"] if row["in_play_before_mankey_benched"] == "yes"]
    replaced = sum(as_int(row["opponent_replaced_it"]) for row in payload["stadium_quality"])
    depended = [row for row in payload["stadium_quality"] if row["first_full_power_depended_on_it"] == "yes"]
    lines.append(f"- Risky Ruins by Turn 2: {len(risky_by_t2)}/{len(payload['stadium_quality'])}")
    lines.append(f"- In play before Mankey benched: {len(before_mankey)}/{len(payload['stadium_quality'])}")
    lines.append(f"- Opponent replacements seen: {replaced}")
    lines.append(f"- First full-power Annihilape depended on it: {len(depended)} game(s)")
    lines.append("")

    lines.append("## Legacy First Attack Miss Reason")
    reason_counts = payload["annihilape_attack_miss_reasons"]["counts"]
    for label in [
        "no Mankey",
        "unknown/no visible Mankey",
        "no Primeape/evolution",
        "no Annihilape",
        "no energy",
        "no damage counters / Lose Cool inactive",
        "KO/disruption",
        "unknown",
    ]:
        lines.append(f"- {label}: {reason_counts.get(label, 0)}")
    reason_details = payload["annihilape_attack_miss_reasons"].get("details", [])
    if reason_details:
        detail_text = "; ".join(
            f"{row['game']} ({', '.join(format_reason(reason) for reason in row['reasons'])})" for row in reason_details[:6]
        )
        lines.append(f"Evidence: {detail_text}")
    lines.append("Note: these are log-derived heuristics; hidden hand/prize state can make the true reason ambiguous.")
    lines.append("")

    lines.append("## Possible Loss Factors")
    for factor in payload.get("possible_loss_factors", [])[:8]:
        evidence = ", ".join(factor.get("evidence", [])) or "none"
        lines.append(
            f"- {factor.get('factor', '')}: {factor.get('count', 0)}/{factor.get('sample', 0)} "
            f"({factor.get('confidence', 'medium')} confidence; {evidence})"
        )
    lines.append("")

    lines.append("## Current Experiment Evidence")
    experiment = payload.get("experiment_metrics", {})
    lines.append(f"- Waitress played: {experiment.get('waitress_played_count', 0)}")
    lines.append(f"- Waitress attached energy: {experiment.get('waitress_attached_energy_count', 0)}")
    lines.append(f"- Waitress whiff/no visible attach: {experiment.get('waitress_whiff_count', 0)}")
    lines.append(f"- SSP Annihilape attacks: {experiment.get('ssp_annihilape_attack_count', 0)}")
    lines.append(f"- SSP outcome: {experiment.get('ssp_outcome', {}).get('classification', 'neutral')}")
    lines.append("")

    lines.append("## Candidate Strengths")
    for row in payload.get("candidate_strengths", [])[:4]:
        lines.append(f"- {row.get('strength')}: {row.get('metric')} ({row.get('confidence')} confidence)")
    return "\n".join(lines) + "\n"


def render_concise_report(payload):
    summary = payload["summary"]
    lines = []
    lines.append("# Project Arceus Deterministic Evidence Report")
    lines.append("")
    lines.append("## Quick Stats")
    lines.append(f"- Scope: {payload['scope']}")
    lines.append(f"- Record: {summary['wins']}-{summary['losses']} ({summary['win_rate']}% win rate)")
    lines.append(f"- Going first: {summary['went_first_wins']}/{summary['went_first']} wins")
    lines.append(f"- Going second: {summary['went_second_wins']}/{summary['went_second']} wins")
    lines.append("")

    if payload.get("mulligan_warnings"):
        lines.append("## Mulligan Warning")
        lines.append("Opening hand after mulligan was hidden; hand-based conclusions are lower confidence.")
        lines.append("Evidence: " + ", ".join(row["game"] for row in payload["mulligan_warnings"][:5]))
        lines.append("")

    misses = [goal for goal in payload["success_conditions"] if goal["missed"] > 0 and goal["confidence"] != "low"]
    lines.append("## Why")
    for goal in misses[:3]:
        lines.append(
            f"- {friendly_condition(goal['condition'])}: missed {goal['missed']}/{goal['games']} "
            f"({', '.join(goal['missed_games'])})"
        )
    if not misses:
        lines.append("- No major success-condition misses in this sample.")
    lines.append("")

    played_cards = [row for row in payload["card_tracking"] if row.get("played", 0) > 0][:4]
    if played_cards:
        lines.append("## Card Flow Snapshot")
        for row in played_cards:
            lines.append(
                f"- {row['card_name']}: drawn {row['drawn']}, played {row['played']}, "
                f"activated/triggered {row['activated_triggered']}, stuck/unused {row['stuck_in_hand_unused']}"
            )
        lines.append("")

    lines.append("## Evolution Bottleneck")
    evolution = payload["evolution_line"]
    rows = evolution.get("rows", [])
    completed_by_t4 = sum(1 for row in rows if row.get("completed_by_turn4") == "yes")
    lines.append(f"- Complete line by Turn 4: {completed_by_t4}/{len(rows)}")
    for label in ["missing Mankey", "missing Primeape", "missing Annihilape", "unknown/no visible Mankey"]:
        count = evolution.get("bottlenecks", {}).get(label, 0)
        if count:
            evidence = [row["game"] for row in rows if row.get("bottleneck") == label][:4]
            lines.append(f"- {label}: {count} ({', '.join(evidence)})")
    hand_gaps = evolution.get("hand_gaps", {})
    for label in ["Annihilape in hand, no Primeape", "Primeape in hand/play, no Annihilape"]:
        if hand_gaps.get(label, 0):
            lines.append(f"- {label}: {hand_gaps[label]}")
    lines.append("")

    attack_rows = payload["annihilape_attack_quality"][-3:]
    if attack_rows:
        lines.append("## Recent Annihilape Attacks")
        for row in attack_rows:
            if row["first_attack_turn"] == "none":
                lines.append(f"- {row['game']}: no Annihilape attack")
            else:
                lines.append(
                    f"- {row['game']}: T{row['first_attack_turn']} {row['attack_name']}, "
                    f"{row['damage_dealt']} damage, full-power {row['full_power_impact_blow']}"
                )
    backup_bad = [row for row in payload["backup_attacker"] if row["state"] in {"not reachable", "no board"}]
    if backup_bad:
        lines.append("Backup issue evidence: " + ", ".join(row["game"] for row in backup_bad[:5]))
    lines.append("")

    backup_counts = Counter(row["state"] for row in payload["backup_attacker"])
    stadium_rows = payload["stadium_quality"]
    risky_by_t2 = [row for row in stadium_rows if row["risky_ruins_played_by_turn"] not in {"none", ""} and as_int(row["risky_ruins_played_by_turn"]) <= 2]
    lines.append("## Board Plan Snapshot")
    lines.append(
        f"- Backup after first Annihilape KO: ready {backup_counts['ready now']}, "
        f"reachable {backup_counts['reachable next turn']}, not reachable {backup_counts['not reachable']}, no board {backup_counts['no board']}"
    )
    lines.append(f"- Risky Ruins by Turn 2: {len(risky_by_t2)}/{len(stadium_rows)}")
    lines.append("")

    factors = payload.get("possible_loss_factors", [])[:5]
    if factors:
        lines.append("## Possible Loss Factors")
        for factor in factors:
            evidence = ", ".join(factor.get("evidence", [])[:4]) or "none"
            lines.append(
                f"- {factor.get('factor', '')}: {factor.get('count', 0)}/{factor.get('sample', 0)} "
                f"({factor.get('confidence', 'medium')} confidence; {evidence})"
            )
        lines.append("")

    experiment = payload.get("experiment_metrics", {})
    lines.append("## Current Experiment Evidence")
    lines.append(
        f"- Waitress: played {experiment.get('waitress_played_count', 0)}, "
        f"attached {experiment.get('waitress_attached_energy_count', 0)}, "
        f"whiff/no attach {experiment.get('waitress_whiff_count', 0)}"
    )
    lines.append(
        f"- SSP Annihilape: {experiment.get('ssp_annihilape_attack_count', 0)} attacks; "
        f"outcome {experiment.get('ssp_outcome', {}).get('classification', 'neutral')}"
    )
    lines.append("")

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
    concise_rendered = render_concise_report(payload)
    verbose_rendered = render_report(payload)
    rendered = verbose_rendered if args.verbose else concise_rendered
    print(rendered, end="")
    if not args.no_write:
        write_report_outputs(args, concise_rendered, verbose_rendered, payload)


if __name__ == "__main__":
    main()
