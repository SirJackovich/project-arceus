#!/usr/bin/env python3
import argparse
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path


DEFAULT_MODEL = "gpt-5.1"


def read_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def compact_deck(deck):
    cards = deck.get("cards", []) if isinstance(deck, dict) else []
    return {
        "name": deck.get("name", "") if isinstance(deck, dict) else "",
        "version": deck.get("version", "") if isinstance(deck, dict) else "",
        "cards": [
            {
                "count": card.get("count"),
                "name": card.get("name"),
                "set": card.get("set"),
                "number": card.get("number"),
                "category": card.get("category"),
            }
            for card in cards
        ],
    }


def compact_evidence(evidence, last):
    recent_games = evidence.get("games", [])[-last:]
    return {
        "layer": evidence.get("layer", "deterministic_analyzer"),
        "scope": evidence.get("scope", ""),
        "summary": evidence.get("summary", {}),
        "recent_games": recent_games,
        "success_conditions": evidence.get("success_conditions", []),
        "mulligan_warnings": evidence.get("mulligan_warnings", []),
        "card_tracking": evidence.get("card_tracking", [])[:15],
        "annihilape_attack_quality": evidence.get("annihilape_attack_quality", [])[-last:],
        "stadium_quality": evidence.get("stadium_quality", [])[-last:],
        "evolution_line": evidence.get("evolution_line", {}),
        "line_rebuild": evidence.get("line_rebuild", [])[-last:],
        "backup_attacker": evidence.get("backup_attacker", [])[-last:],
        "possible_loss_factors": evidence.get("possible_loss_factors", []),
        "legacy_first_attack_miss_reasons": evidence.get("annihilape_attack_miss_reasons", {}),
    }


def build_context(args):
    evidence = read_json(args.evidence_json)
    if not evidence:
        raise SystemExit(f"Missing deterministic evidence JSON: {args.evidence_json}")
    deck = read_json(args.deck, {})
    experiment = read_json(args.experiment_state, {}) or {"status": "no current experiment"}
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "instructions": "Use deterministic evidence only. Do not parse raw logs.",
        "deck": compact_deck(deck),
        "current_experiment": experiment,
        "deterministic_evidence": compact_evidence(evidence, args.last),
    }


def call_openai(prompt, context, model, api_key):
    body = {
        "model": model,
        "input": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ],
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"OpenAI API request failed: HTTP {exc.code}\n{detail}") from exc


def response_text(response):
    if response.get("output_text"):
        return response["output_text"]
    chunks = []
    for item in response.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                chunks.append(content["text"])
    return "\n".join(chunks).strip()


def extract_json_summary(text):
    blocks = re.findall(r"```json\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    candidates = blocks or re.findall(r"(\{\s*\"coach_grade\".*\})", text, flags=re.DOTALL)
    for candidate in reversed(candidates):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return {"parse_status": "missing_json_summary"}


def main():
    parser = argparse.ArgumentParser(description="Generate the AI-written Project Arceus coach report from deterministic evidence.")
    parser.add_argument("--evidence-json", default="data/analysis/deterministic_analysis.json")
    parser.add_argument("--deck", default="decks/annihilape/v01.json")
    parser.add_argument("--experiment-state", default="data/experiment_tracker.json")
    parser.add_argument("--prompt", default="prompts/coach_report.md")
    parser.add_argument("--last", type=int, default=10)
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", DEFAULT_MODEL))
    parser.add_argument("--output-md", default="data/analysis/ai_coach_report.md")
    parser.add_argument("--output-json", default="data/analysis/ai_coach_report.json")
    parser.add_argument("--prompt-out", default="data/analysis/ai_coach_prompt.json")
    parser.add_argument("--dry-run", action="store_true", help="Write the prompt/context without calling the LLM.")
    args = parser.parse_args()

    prompt = Path(args.prompt).read_text(encoding="utf-8")
    context = build_context(args)
    write_json(args.prompt_out, {"prompt": prompt, "context": context, "model": args.model})

    if args.dry_run:
        rendered = "# Project Arceus AI Coach Report\n\nDry run only. Prompt context written to `data/analysis/ai_coach_prompt.json`.\n"
        summary = {"status": "dry_run", "model": args.model, "prompt_out": args.prompt_out}
    else:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise SystemExit("OPENAI_API_KEY is not set. Use --dry-run to inspect the prompt without calling the API.")
        try:
            response = call_openai(prompt, context, args.model, api_key)
        except SystemExit as exc:
            rendered = (
                "# Project Arceus AI Coach Report\n\n"
                "AI coach request failed. The deterministic evidence was still generated successfully.\n\n"
                f"```text\n{exc}\n```\n"
            )
            summary = {
                "status": "api_error",
                "model": args.model,
                "message": str(exc),
                "prompt_out": args.prompt_out,
            }
            write_text(args.output_md, rendered)
            write_json(args.output_json, summary)
            print(rendered)
            print(f"\nWrote {args.output_md} and {args.output_json}")
            raise
        rendered = response_text(response)
        summary = extract_json_summary(rendered)
        summary["model"] = args.model
        summary["response_id"] = response.get("id", "")

    write_text(args.output_md, rendered)
    write_json(args.output_json, summary)
    print(rendered)
    print(f"\nWrote {args.output_md} and {args.output_json}")


if __name__ == "__main__":
    main()
