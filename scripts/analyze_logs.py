#!/usr/bin/env python3
import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


MY_PLAYER = "SirJackovich"
NOTE_RE = re.compile(r"^\s*Notes?:", re.IGNORECASE)
TURN_RE = re.compile(r"^(.+)'s Turn$")
WIN_RE = re.compile(r"([^\s.]+) wins\.$")


@dataclass
class ActionContext:
    player: str
    source_card: str
    source_action: str
    turn_number: int


def natural_key(path):
    parts = re.split(r"(\d+)", path.stem)
    return [int(p) if p.isdigit() else p.lower() for p in parts]


def clean_card(name):
    if not name:
        return ""
    name = name.strip()
    name = re.sub(r"^(?:a|an)\s+", "", name, flags=re.IGNORECASE)
    return name.strip(" .")


def parse_count(text):
    if text == "a":
        return 1
    try:
        return int(text)
    except ValueError:
        return ""


def csv_write(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def load_lines(path):
    raw = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    kept = []
    for line in raw:
        if NOTE_RE.match(line):
            break
        kept.append(line.rstrip())
    return kept


def infer_game_number(path):
    match = re.match(r"game_(\d+)$", path.stem)
    if match:
        return int(match.group(1))
    match = re.match(r"(\d+)_", path.stem)
    if match:
        return int(match.group(1))
    return ""


def player_from_line(line):
    if line.startswith("- ") or line.startswith("•"):
        return ""
    match = re.match(r"^([^-].*?) (?:chose|won|decided|drew|played|attached|retreated|evolved|took|put|shuffled|moved|flipped|ended)\b", line)
    if match:
        return match.group(1)
    match = re.match(r"^(.+?)'s .+? (?:used|was|is|took)", line)
    if match:
        return match.group(1)
    match = re.match(r"^- (.+?) (?:drew|shuffled|discarded|moved|attached|put|evolved|flipped)", line)
    if match:
        return match.group(1)
    return ""


def add_event(events, file_name, game_id, line_no, turn_number, turn_player, line, event_type,
              player="", card_name="", target_card="", amount="", source_card="", source_player="",
              source_action="", value=""):
    event_player = player or player_from_line(line)
    events.append({
        "game_id": game_id,
        "file": file_name,
        "line_no": line_no,
        "turn_number": turn_number,
        "turn_player": turn_player,
        "event_player": event_player,
        "is_user": "yes" if event_player == MY_PLAYER else "no",
        "event_type": event_type,
        "card_name": clean_card(card_name),
        "target_card": clean_card(target_card),
        "amount": amount,
        "source_card": clean_card(source_card),
        "source_player": source_player,
        "source_action": source_action,
        "value": value,
        "raw_line": line,
    })


def parse_log(path):
    lines = load_lines(path)
    game_id = path.stem
    game_number = infer_game_number(path)
    events = []
    players = set()
    turn_player = ""
    turn_number = 0
    opening_player = ""
    first_non_user_player = ""
    winner = ""
    win_reason = ""
    last_context = None
    pending_bullet_context = None
    setup_seen = False

    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue

        turn_match = TURN_RE.match(stripped)
        if turn_match:
            turn_player = turn_match.group(1)
            players.add(turn_player)
            if turn_player != MY_PLAYER and not first_non_user_player:
                first_non_user_player = turn_player
            turn_number += 1
            last_context = None
            pending_bullet_context = None
            add_event(events, path.name, game_id, line_no, turn_number, turn_player, stripped,
                      "turn_start", player=turn_player)
            continue

        if stripped == "Setup":
            setup_seen = True
            add_event(events, path.name, game_id, line_no, turn_number, turn_player, stripped, "setup")
            continue

        win_match = WIN_RE.search(stripped)
        if win_match:
            winner = win_match.group(1)
            win_reason = stripped
            players.add(winner)
            add_event(events, path.name, game_id, line_no, turn_number, turn_player, stripped,
                      "game_end", player=winner, value=win_reason)
            continue

        match = re.match(r"^(.+) decided to go (first|second)\.$", stripped)
        if match:
            opening_player = match.group(1)
            if opening_player != MY_PLAYER and not first_non_user_player:
                first_non_user_player = opening_player
            add_event(events, path.name, game_id, line_no, turn_number, turn_player, stripped,
                      "opening_choice", player=match.group(1), value=match.group(2))
            continue

        match = re.match(r"^(.+) drew 7 cards for the opening hand\.$", stripped)
        if match:
            if match.group(1) != MY_PLAYER and not first_non_user_player:
                first_non_user_player = match.group(1)
            pending_bullet_context = ("opening_hand", match.group(1), "", "", "")
            add_event(events, path.name, game_id, line_no, turn_number, turn_player, stripped,
                      "opening_hand_draw", player=match.group(1), amount=7)
            continue

        if stripped.startswith("- ") or stripped.startswith("•"):
            bullet = stripped[2:].strip() if stripped.startswith("- ") else stripped[1:].strip()
            if bullet.startswith("Damage breakdown"):
                add_event(events, path.name, game_id, line_no, turn_number, turn_player, stripped,
                          "effect_detail",
                          source_card=last_context.source_card if last_context else "",
                          source_player=last_context.player if last_context else "",
                          source_action=last_context.source_action if last_context else "")
                continue
            if pending_bullet_context and stripped.startswith("•"):
                ctx_type, ctx_player, ctx_source, ctx_source_player, ctx_source_action = pending_bullet_context
                for card in [clean_card(x) for x in bullet.split(",") if clean_card(x)]:
                    add_event(events, path.name, game_id, line_no, turn_number, turn_player, stripped,
                              ctx_type, player=ctx_player, card_name=card,
                              source_card=ctx_source, source_player=ctx_source_player,
                              source_action=ctx_source_action)
                continue
            source = last_context.source_card if last_context else ""
            source_player = last_context.player if last_context else ""
            source_action = last_context.source_action if last_context else ""
            match = re.match(r"^(.+) drew (a|\d+) cards?\.$", bullet)
            if match:
                pending_bullet_context = ("known_drawn_card", match.group(1), source, source_player, source_action)
                add_event(events, path.name, game_id, line_no, turn_number, turn_player, stripped,
                          "draw_effect", player=match.group(1), amount=parse_count(match.group(2)),
                          source_card=source, source_player=source_player, source_action=source_action)
                continue
            match = re.match(r"^(.+) drew (\d+) cards? and played them to the Bench\.$", bullet)
            if match:
                add_event(events, path.name, game_id, line_no, turn_number, turn_player, stripped,
                          "draw_and_bench_unknown", player=match.group(1), amount=match.group(2),
                          source_card=source, source_player=source_player, source_action=source_action)
                continue
            match = re.match(r"^(.+) drew (.+)\.$", bullet)
            if match:
                player, card = match.groups()
                add_event(events, path.name, game_id, line_no, turn_number, turn_player, stripped,
                          "known_drawn_card", player=player, card_name=card,
                          source_card=source, source_player=source_player, source_action=source_action)
                continue
            match = re.match(r"^(.+) shuffled (a|\d+) cards? into their deck\.$", bullet)
            if match:
                add_event(events, path.name, game_id, line_no, turn_number, turn_player, stripped,
                          "shuffle_into_deck", player=match.group(1), amount=parse_count(match.group(2)),
                          source_card=source, source_player=source_player, source_action=source_action)
                continue
            match = re.match(r"^(.+) shuffled their deck\.$", bullet)
            if match:
                add_event(events, path.name, game_id, line_no, turn_number, turn_player, stripped,
                          "shuffle_deck", player=match.group(1), source_card=source,
                          source_player=source_player, source_action=source_action)
                continue
            match = re.match(r"^(.+) discarded (a|\d+) cards?\.$", bullet)
            if match:
                pending_bullet_context = ("discarded_card", match.group(1), source, source_player, source_action)
                add_event(events, path.name, game_id, line_no, turn_number, turn_player, stripped,
                          "discard_effect", player=match.group(1), amount=parse_count(match.group(2)),
                          source_card=source, source_player=source_player, source_action=source_action)
                continue
            match = re.match(r"^(.+?) attached (.+?) to (.+?)(?: in the Active Spot| on the Bench)?\.$", bullet)
            if match:
                player, card, target = match.groups()
                add_event(events, path.name, game_id, line_no, turn_number, turn_player, stripped,
                          "effect_attach", player=player, card_name=card, target_card=target,
                          source_card=source, source_player=source_player, source_action=source_action)
                continue
            match = re.match(r"^(.+?) put (\d+) damage counters on (.+?)'s (.+?)\.$", bullet)
            if match:
                player, amount, target_player, target = match.groups()
                add_event(events, path.name, game_id, line_no, turn_number, turn_player, stripped,
                          "damage_counters", player=player, target_card=target, amount=amount,
                          source_card=source, source_player=source_player, source_action=source_action)
                continue
            match = re.match(r"^(.+) flipped a coin and it landed on (heads|tails)\.$", bullet)
            if match:
                add_event(events, path.name, game_id, line_no, turn_number, turn_player, stripped,
                          "coin_flip", player=match.group(1), source_card=source,
                          source_player=source_player, source_action=source_action, value=match.group(2))
                continue
            add_event(events, path.name, game_id, line_no, turn_number, turn_player, stripped,
                      "effect_detail", source_card=source, source_player=source_player,
                      source_action=source_action, value=bullet)
            continue

        p = player_from_line(stripped)
        if p:
            players.add(p)

        match = re.match(r"^(.+) drew (\d+) more cards? because .+ took at least 1 mulligan\.$", stripped)
        if match:
            add_event(events, path.name, game_id, line_no, turn_number, turn_player, stripped,
                      "mulligan_bonus_draw", player=match.group(1), amount=match.group(2))
            last_context = None
            pending_bullet_context = None
            continue

        match = re.match(r"^(.+) drew (\d+) cards? and played them to the Bench\.$", stripped)
        if match:
            add_event(events, path.name, game_id, line_no, turn_number, turn_player, stripped,
                      "draw_and_bench_unknown", player=match.group(1), amount=match.group(2))
            last_context = None
            pending_bullet_context = None
            continue

        match = re.match(r"^(.+) drew (.+)\.$", stripped)
        if match:
            player, card = match.groups()
            event_type = "turn_draw_unknown" if card == "a card" else "turn_draw_known"
            add_event(events, path.name, game_id, line_no, turn_number, turn_player, stripped,
                      event_type, player=player, card_name="" if card == "a card" else card)
            last_context = None
            pending_bullet_context = None
            continue

        match = re.match(r"^(.+) played (.+?)(?: to the (Active Spot|Bench|Stadium spot))?\.$", stripped)
        if match:
            player, card, zone = match.groups()
            event_type = "play_card"
            if zone == "Bench":
                event_type = "bench_pokemon"
            elif zone == "Active Spot":
                event_type = "active_pokemon"
            elif zone == "Stadium spot":
                event_type = "stadium_play"
            add_event(events, path.name, game_id, line_no, turn_number, turn_player, stripped,
                      event_type, player=player, card_name=card, value=zone or "")
            last_context = ActionContext(player, card, event_type, turn_number)
            pending_bullet_context = None
            continue

        match = re.match(r"^(.+) evolved (.+?) to (.+?)(?: in the Active Spot| on the Bench)?\.$", stripped)
        if match:
            player, from_card, to_card = match.groups()
            add_event(events, path.name, game_id, line_no, turn_number, turn_player, stripped,
                      "evolve", player=player, card_name=to_card, target_card=from_card)
            last_context = ActionContext(player, to_card, "evolve", turn_number)
            pending_bullet_context = None
            continue

        match = re.match(r"^(.+) attached (.+?) to (.+?)(?: in the Active Spot| on the Bench)?\.$", stripped)
        if match:
            player, card, target = match.groups()
            add_event(events, path.name, game_id, line_no, turn_number, turn_player, stripped,
                      "manual_attach", player=player, card_name=card, target_card=target)
            last_context = ActionContext(player, card, "manual_attach", turn_number)
            pending_bullet_context = None
            continue

        match = re.match(r"^(.+)'s (.+?) used (.+?) on .+?[’']s (.+?) for (-?\d+) damage(?:\..*)?$", stripped)
        if match:
            player, attacker, attack, target, damage = match.groups()
            add_event(events, path.name, game_id, line_no, turn_number, turn_player, stripped,
                      "attack", player=player, card_name=attacker, target_card=target, amount=damage, value=attack)
            last_context = ActionContext(player, attacker, "attack", turn_number)
            pending_bullet_context = None
            continue

        match = re.match(r"^(.+)'s (.+?) used (.+?)\.$", stripped)
        if match:
            player, card, ability = match.groups()
            known_attacks = {
                "Drag Off", "Wild Kick", "Impact Blow", "Vengeful Kick", "Tantrum", "Destined Fight"
            }
            if player == MY_PLAYER and ability in known_attacks:
                add_event(events, path.name, game_id, line_no, turn_number, turn_player, stripped,
                          "attack", player=player, card_name=card, value=ability)
                last_context = ActionContext(player, card, "attack", turn_number)
                pending_bullet_context = None
                continue
            add_event(events, path.name, game_id, line_no, turn_number, turn_player, stripped,
                      "use_ability", player=player, card_name=card, value=ability)
            last_context = ActionContext(player, card, "use_ability", turn_number)
            pending_bullet_context = None
            continue

        match = re.match(r"^(.+)'s (.+?) was Knocked Out!$", stripped)
        if match:
            player, card = match.groups()
            add_event(events, path.name, game_id, line_no, turn_number, turn_player, stripped,
                      "knockout_received", player=player, card_name=card,
                      source_card=last_context.source_card if last_context else "",
                      source_player=last_context.player if last_context else "",
                      source_action=last_context.source_action if last_context else "")
            pending_bullet_context = None
            continue

        match = re.match(r"^(.+) took (a|\d+) Prize cards?\.$", stripped)
        if match:
            add_event(events, path.name, game_id, line_no, turn_number, turn_player, stripped,
                      "prize_taken", player=match.group(1), amount=parse_count(match.group(2)),
                      source_card=last_context.source_card if last_context else "",
                      source_player=last_context.player if last_context else "",
                      source_action=last_context.source_action if last_context else "")
            continue

        match = re.match(r"^(.+) retreated (.+?) to the Bench\.$", stripped)
        if match:
            add_event(events, path.name, game_id, line_no, turn_number, turn_player, stripped,
                      "retreat", player=match.group(1), card_name=match.group(2))
            last_context = ActionContext(match.group(1), match.group(2), "retreat", turn_number)
            pending_bullet_context = None
            continue

        match = re.match(r"^(.+?) was discarded from .+?'s (.+?)\.$", stripped)
        if match:
            card, target = match.groups()
            add_event(events, path.name, game_id, line_no, turn_number, turn_player, stripped,
                      "discarded_card", player=p, card_name=card, target_card=target)
            continue

        match = re.match(r"^(.+) was activated\.$", stripped)
        if match:
            card = match.group(1)
            add_event(events, path.name, game_id, line_no, turn_number, turn_player, stripped,
                      "activation", player=turn_player, card_name=card)
            last_context = ActionContext(turn_player, card, "activation", turn_number)
            pending_bullet_context = None
            continue

        add_event(events, path.name, game_id, line_no, turn_number, turn_player, stripped,
                  "unclassified", player=p)

    opponents = sorted(player for player in players if player and player != MY_PLAYER)
    opponent = first_non_user_player or (opponents[0] if opponents else "")
    result = "win" if winner == MY_PLAYER else "loss" if winner else "unknown"
    my_turns = len({event["turn_number"] for event in events if event["turn_player"] == MY_PLAYER})
    opp_turns = len({event["turn_number"] for event in events if event["turn_player"] and event["turn_player"] != MY_PLAYER})

    game = {
        "game_id": game_id,
        "game_number": game_number,
        "file": path.name,
        "opponent": opponent,
        "winner": winner,
        "result": result,
        "win_reason": win_reason,
        "opening_player": opening_player,
        "my_went_first": "yes" if opening_player == MY_PLAYER else "no" if opening_player else "",
        "turns_total": turn_number,
        "my_turns": my_turns,
        "opponent_turns": opp_turns,
        "events_total": len(events),
        "parsed_lines": len([line for line in lines if line.strip()]),
        "has_game_log": "yes" if setup_seen and winner else "partial",
    }
    return game, events


def summarize(games, events):
    game_by_id = {game["game_id"]: game for game in games}
    my_events = [event for event in events if event["event_player"] == MY_PLAYER]
    card_games = defaultdict(set)
    card_turns = defaultdict(list)
    counts = defaultdict(Counter)
    source_counts = defaultdict(Counter)

    usage_types = {
        "play_card", "bench_pokemon", "active_pokemon", "stadium_play", "evolve",
        "manual_attach", "attack", "use_ability", "activation"
    }
    value_types = {
        "draw_effect", "known_drawn_card", "effect_attach", "damage_counters",
        "coin_flip", "prize_taken", "knockout_received"
    }

    for event in my_events:
        card = event["card_name"]
        source = event["source_card"]
        event_type = event["event_type"]
        if card:
            counts[card][event_type] += 1
            if event_type in usage_types:
                card_games[card].add(event["game_id"])
                if event["turn_number"]:
                    card_turns[card].append(int(event["turn_number"]))
        if source and event.get("source_player") == MY_PLAYER:
            source_counts[source][event_type] += 1

    rows = []
    all_cards = sorted(set(counts) | set(source_counts))
    for card in all_cards:
        games_used = sorted(card_games.get(card, set()))
        wins = sum(1 for game_id in games_used if game_by_id[game_id]["result"] == "win")
        losses = sum(1 for game_id in games_used if game_by_id[game_id]["result"] == "loss")
        turns = card_turns.get(card, [])
        direct_value = sum(source_counts[card][t] for t in value_types)
        played_like = sum(counts[card][t] for t in usage_types)
        discarded = counts[card]["discarded_card"]
        ko_received = counts[card]["knockout_received"]
        if not any([played_like, direct_value, discarded, ko_received]):
            continue
        attacks = counts[card]["attack"]
        damage = sum(int(event["amount"]) for event in my_events
                     if event["card_name"] == card and event["event_type"] == "attack" and str(event["amount"]).isdigit())
        rows.append({
            "card_name": card,
            "games_used": len(games_used),
            "wins_when_used": wins,
            "losses_when_used": losses,
            "win_rate_when_used": round(wins / len(games_used), 3) if games_used else "",
            "played_or_used_count": played_like,
            "played_from_hand_count": counts[card]["play_card"] + counts[card]["bench_pokemon"] + counts[card]["active_pokemon"] + counts[card]["stadium_play"],
            "evolved_into_count": counts[card]["evolve"],
            "attached_count": counts[card]["manual_attach"],
            "attack_count": attacks,
            "ability_count": counts[card]["use_ability"] + counts[card]["activation"],
            "total_attack_damage": damage,
            "avg_attack_damage": round(damage / attacks, 1) if attacks else "",
            "effect_draw_events_attributed": source_counts[card]["draw_effect"] + source_counts[card]["known_drawn_card"],
            "effect_attach_events_attributed": source_counts[card]["effect_attach"],
            "damage_counter_events_attributed": source_counts[card]["damage_counters"],
            "knockouts_attributed": source_counts[card]["knockout_received"],
            "prize_events_attributed": source_counts[card]["prize_taken"],
            "direct_value_events_attributed": direct_value,
            "discarded_count": discarded,
            "knocked_out_count": ko_received,
            "avg_first_usage_turn": round(sum(turns) / len(turns), 1) if turns else "",
        })
    rows.sort(key=lambda r: (-int(r["games_used"] or 0), r["card_name"]))
    return rows


def summarize_attacks(games, events):
    game_by_id = {game["game_id"]: game for game in games}
    grouped = {}
    for event in events:
        if event["event_player"] != MY_PLAYER or event["event_type"] != "attack":
            continue
        key = (event["card_name"], event["value"])
        row = grouped.setdefault(key, {
            "card_name": event["card_name"],
            "attack_name": event["value"],
            "uses": 0,
            "games_used": set(),
            "total_damage": 0,
            "min_damage": None,
            "max_damage": None,
            "knockouts_attributed": 0,
            "prizes_attributed": 0,
        })
        row["uses"] += 1
        row["games_used"].add(event["game_id"])
        if str(event["amount"]).isdigit():
            damage = int(event["amount"])
            row["total_damage"] += damage
            row["min_damage"] = damage if row["min_damage"] is None else min(row["min_damage"], damage)
            row["max_damage"] = damage if row["max_damage"] is None else max(row["max_damage"], damage)

    for event in events:
        if event.get("source_player") != MY_PLAYER or event.get("source_action") != "attack" or not event["source_card"]:
            continue
        if event["event_type"] not in {"knockout_received", "prize_taken"}:
            continue
        matching_keys = [key for key in grouped if key[0] == event["source_card"]]
        if len(matching_keys) != 1:
            continue
        row = grouped[matching_keys[0]]
        if event["event_type"] == "knockout_received":
            row["knockouts_attributed"] += 1
        elif event["event_type"] == "prize_taken" and str(event["amount"]).isdigit():
            row["prizes_attributed"] += int(event["amount"])

    rows = []
    for row in grouped.values():
        games_used = sorted(row["games_used"])
        wins = sum(1 for game_id in games_used if game_by_id[game_id]["result"] == "win")
        losses = sum(1 for game_id in games_used if game_by_id[game_id]["result"] == "loss")
        rows.append({
            "card_name": row["card_name"],
            "attack_name": row["attack_name"],
            "uses": row["uses"],
            "games_used": len(games_used),
            "wins_when_used": wins,
            "losses_when_used": losses,
            "win_rate_when_used": round(wins / len(games_used), 3) if games_used else "",
            "total_damage": row["total_damage"],
            "avg_damage": round(row["total_damage"] / row["uses"], 1) if row["uses"] else "",
            "min_damage": row["min_damage"] if row["min_damage"] is not None else "",
            "max_damage": row["max_damage"] if row["max_damage"] is not None else "",
            "knockouts_attributed": row["knockouts_attributed"],
            "prizes_attributed": row["prizes_attributed"],
        })
    rows.sort(key=lambda r: (-r["uses"], r["card_name"], r["attack_name"]))
    return rows


def summarize_going_first(games):
    buckets = {
        "went_first": [game for game in games if game["has_game_log"] == "yes" and game["my_went_first"] == "yes"],
        "went_second": [game for game in games if game["has_game_log"] == "yes" and game["my_went_first"] == "no"],
        "unknown": [game for game in games if game["has_game_log"] == "yes" and game["my_went_first"] == ""],
    }
    rows = []
    for label, bucket in buckets.items():
        wins = sum(1 for game in bucket if game["result"] == "win")
        losses = sum(1 for game in bucket if game["result"] == "loss")
        games_count = len(bucket)
        rows.append({
            "bucket": label,
            "games": games_count,
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / games_count, 3) if games_count else "",
            "avg_my_turns": round(sum(int(game["my_turns"] or 0) for game in bucket) / games_count, 1) if games_count else "",
            "avg_total_turns": round(sum(int(game["turns_total"] or 0) for game in bucket) / games_count, 1) if games_count else "",
        })
    return rows


def infer_role(row):
    card = row["card_name"]
    if "Energy" in card:
        return "Energy"
    if int(row.get("attack_count", 0) or 0):
        return "Attacker"
    if int(row.get("evolved_into_count", 0) or 0):
        return "Evolution line"
    if int(row.get("effect_draw_events_attributed", 0) or 0) or card in {
        "Dawn", "Lillie's Determination", "Hilda", "Pokégear 3.0", "Fighting Gong", "Poké Pad"
    }:
        return "Draw/search"
    if int(row.get("effect_attach_events_attributed", 0) or 0) or card in {"Energy Switch", "Waitress"}:
        return "Energy support"
    if int(row.get("damage_counter_events_attributed", 0) or 0) or card in {"Risky Ruins", "Prism Tower", "Lumiose City"}:
        return "Stadium/damage"
    if int(row.get("ability_count", 0) or 0):
        return "Engine/ability"
    if int(row.get("attached_count", 0) or 0):
        return "Tool"
    return "Support"


def summarize_effectiveness(card_rows, games):
    complete = [game for game in games if game["has_game_log"] == "yes"]
    base_wins = sum(1 for game in complete if game["result"] == "win")
    baseline = base_wins / len(complete) if complete else 0
    rows = []
    for row in card_rows:
        games_used = int(row["games_used"] or 0)
        uses = int(row["played_or_used_count"] or 0)
        if games_used == 0 and uses == 0:
            continue
        win_rate = row["win_rate_when_used"]
        win_rate_value = float(win_rate) if win_rate != "" else 0
        value_events = int(row["direct_value_events_attributed"] or 0)
        attacks = int(row["attack_count"] or 0)
        kos = int(row.get("knockouts_attributed", 0) or 0)
        prizes = int(row.get("prize_events_attributed", 0) or 0)
        damage = int(row["total_attack_damage"] or 0)
        knocked_out = int(row["knocked_out_count"] or 0)
        observable_score = round(
            value_events + attacks * 1.5 + kos * 4 + prizes * 2 + damage / 100 - knocked_out * 0.5,
            1,
        )
        value_per_use = round(observable_score / uses, 2) if uses else ""
        win_delta = round(win_rate_value - baseline, 3) if games_used else ""
        if games_used < 5:
            signal = "low sample"
        elif win_delta != "" and win_delta >= 0.08:
            signal = "positive"
        elif win_delta != "" and win_delta <= -0.08:
            signal = "watch"
        elif value_per_use != "" and value_per_use >= 1:
            signal = "productive"
        else:
            signal = "neutral"
        rows.append({
            "card_name": row["card_name"],
            "role": infer_role(row),
            "games_used": games_used,
            "uses": uses,
            "win_rate_when_used": win_rate,
            "win_rate_delta_vs_deck": win_delta,
            "observable_score": observable_score,
            "observable_score_per_use": value_per_use,
            "value_events": value_events,
            "attack_count": attacks,
            "knockouts_attributed": kos,
            "prizes_attributed": prizes,
            "knocked_out_count": knocked_out,
            "avg_first_usage_turn": row["avg_first_usage_turn"],
            "signal": signal,
        })
    rows.sort(key=lambda r: (-float(r["observable_score"] or 0), -int(r["games_used"] or 0), r["card_name"]))
    return rows


def opening_summary(events):
    cards = defaultdict(Counter)
    game_cards = defaultdict(set)
    for event in events:
        if event["event_player"] == MY_PLAYER and event["event_type"] == "opening_hand" and event["card_name"]:
            cards[event["card_name"]]["opening_copies"] += 1
            game_cards[event["card_name"]].add(event["game_id"])
    rows = []
    for card in sorted(cards):
        rows.append({
            "card_name": card,
            "opening_copies_seen": cards[card]["opening_copies"],
            "games_in_opening_hand": len(game_cards[card]),
        })
    rows.sort(key=lambda r: (-r["games_in_opening_hand"], r["card_name"]))
    return rows


def main():
    parser = argparse.ArgumentParser(description="Parse Pokemon TCG Live text logs into CSV summaries.")
    parser.add_argument("--input-dir", default="data/logs", help="Directory containing .txt logs")
    parser.add_argument("--output-dir", default="data/analysis", help="Directory for CSV/JSON outputs")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    paths = sorted(input_dir.glob("*.txt"), key=natural_key)

    games = []
    events = []
    for path in paths:
        game, game_events = parse_log(path)
        games.append(game)
        events.extend(game_events)

    card_rows = summarize(games, events)
    opening_rows = opening_summary(events)
    attack_rows = summarize_attacks(games, events)
    going_first_rows = summarize_going_first(games)
    effectiveness_rows = summarize_effectiveness(card_rows, games)

    csv_write(output_dir / "games.csv", games, [
        "game_id", "game_number", "file", "opponent", "winner", "result", "win_reason",
        "opening_player", "my_went_first", "turns_total", "my_turns", "opponent_turns",
        "events_total", "parsed_lines", "has_game_log"
    ])
    csv_write(output_dir / "raw_events.csv", events, [
        "game_id", "file", "line_no", "turn_number", "turn_player", "event_player", "is_user",
        "event_type", "card_name", "target_card", "amount", "source_card", "source_player",
        "source_action", "value", "raw_line"
    ])
    csv_write(output_dir / "card_usage.csv", card_rows, [
        "card_name", "games_used", "wins_when_used", "losses_when_used", "win_rate_when_used",
        "played_or_used_count", "played_from_hand_count", "evolved_into_count", "attached_count",
        "attack_count", "ability_count", "total_attack_damage", "avg_attack_damage",
        "effect_draw_events_attributed", "effect_attach_events_attributed",
        "damage_counter_events_attributed", "knockouts_attributed", "prize_events_attributed",
        "direct_value_events_attributed", "discarded_count", "knocked_out_count",
        "avg_first_usage_turn"
    ])
    csv_write(output_dir / "opening_hands.csv", opening_rows, [
        "card_name", "opening_copies_seen", "games_in_opening_hand"
    ])
    csv_write(output_dir / "attack_usage.csv", attack_rows, [
        "card_name", "attack_name", "uses", "games_used", "wins_when_used", "losses_when_used",
        "win_rate_when_used", "total_damage", "avg_damage", "min_damage", "max_damage",
        "knockouts_attributed", "prizes_attributed"
    ])
    csv_write(output_dir / "going_first_summary.csv", going_first_rows, [
        "bucket", "games", "wins", "losses", "win_rate", "avg_my_turns", "avg_total_turns"
    ])
    csv_write(output_dir / "card_effectiveness.csv", effectiveness_rows, [
        "card_name", "role", "games_used", "uses", "win_rate_when_used", "win_rate_delta_vs_deck",
        "observable_score", "observable_score_per_use", "value_events", "attack_count",
        "knockouts_attributed", "prizes_attributed", "knocked_out_count", "avg_first_usage_turn",
        "signal"
    ])

    summary = {
        "input_dir": str(input_dir.resolve()),
        "output_dir": str(output_dir.resolve()),
        "files_seen": len(paths),
        "games_with_complete_log": sum(1 for game in games if game["has_game_log"] == "yes"),
        "games_partial": sum(1 for game in games if game["has_game_log"] != "yes"),
        "wins": sum(1 for game in games if game["result"] == "win"),
        "losses": sum(1 for game in games if game["result"] == "loss"),
        "raw_events": len(events),
        "cards_summarized": len(card_rows),
        "attacks_summarized": len(attack_rows),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
