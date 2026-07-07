"""Shared helpers for Project Arceus AI coaching scripts."""

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


DEFAULT_MODEL = "gpt-5.1"
DEFAULT_EXPERIMENT = {
    "current_experiment": {
        "name": "SSP Annihilape and Waitress test",
        "changed_cards": ["1 Annihilape SSP 100", "2 Waitress ASC 215"],
        "target_question": "Do SSP Annihilape and Waitress improve rebuilds, tempo, or awkward evolution/energy games?",
        "status": "active",
    }
}


def read_json(path: str, default: Optional[Any] = None) -> Any:
    path_obj = Path(path)
    if not path_obj.exists():
        return default
    return json.loads(path_obj.read_text(encoding="utf-8"))


def write_json(path: str, payload: Any) -> None:
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    path_obj.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: str, text: str) -> None:
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    path_obj.write_text(text, encoding="utf-8")


def compact_deck(deck: dict) -> dict:
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


def generated_at() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def call_openai(prompt: str, context: dict, model: str, api_key: str) -> dict:
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


def response_text(response: dict) -> str:
    if response.get("output_text"):
        return response["output_text"]
    chunks = []
    for item in response.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                chunks.append(content["text"])
    return "\n".join(chunks).strip()


def extract_json_summary(text: str) -> dict:
    blocks = re.findall(r"```json\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    candidates = blocks or re.findall(r"(\{\s*\"(?:verdict|coach_grade)\".*\})", text, flags=re.DOTALL)
    for candidate in reversed(candidates):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return {"parse_status": "missing_json_summary"}


def format_terminal_value(value: Any) -> str:
    if isinstance(value, dict) and {"remove", "add"} & set(value):
        lines = []
        removes = value.get("remove") or []
        adds = value.get("add") or []
        if removes:
            lines.append("Remove:")
            for row in removes:
                lines.append(f"- {row.get('count', 1)} {row.get('card', '')}".rstrip())
        if adds:
            if lines:
                lines.append("")
            lines.append("Add:")
            for row in adds:
                lines.append(f"- {row.get('count', 1)} {row.get('card', '')}".rstrip())
        if value.get("hypothesis"):
            lines.extend(["", "Hypothesis:", str(value["hypothesis"])])
        criteria = value.get("success_criteria") or []
        if criteria:
            lines.extend(["", "Success Criteria:"])
            for criterion in criteria:
                lines.append(f"- {criterion}")
        if value.get("confidence"):
            lines.extend(["", "Confidence:", str(value["confidence"])])
        return "\n".join(lines).strip()
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value).strip()


def terminal_report(markdown: str, summary: dict, title: str, labels: list) -> str:
    if summary and "verdict" in summary:
        lines = [title, ""]
        for heading, key in labels:
            value = format_terminal_value(summary.get(key, "")) or "Not provided"
            lines.extend([f"## {heading}", value, ""])
        return "\n".join(lines).rstrip() + "\n"

    sections = []
    for heading, _ in labels:
        pattern = rf"(^##?\s+{re.escape(heading)}\s*$.*?)(?=^##?\s+|\Z)"
        match = re.search(pattern, markdown, flags=re.MULTILINE | re.DOTALL | re.IGNORECASE)
        if match:
            sections.append(match.group(1).strip())
    if sections:
        return title + "\n\n" + "\n\n".join(sections[: len(labels)]) + "\n"
    return title + "\n\n" + markdown[:1600].rstrip() + "\n"


def run_llm_report(args: Any, prompt: str, context: dict, terminal_title: str, labels: list) -> int:
    write_json(args.prompt_out, {"prompt": prompt, "context": context, "model": args.model})

    if args.dry_run:
        rendered = f"# {terminal_title}\n\nDry run only. Prompt context written to `{args.prompt_out}`.\n"
        summary = {"status": "dry_run", "model": args.model, "prompt_out": args.prompt_out}
    else:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise SystemExit("OPENAI_API_KEY is not set. Use --dry-run to inspect the prompt without calling the API.")
        try:
            response = call_openai(prompt, context, args.model, api_key)
        except SystemExit as exc:
            rendered = (
                f"# {terminal_title}\n\n"
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
            print(rendered if args.verbose else terminal_report(rendered, summary, terminal_title, labels))
            if args.verbose:
                print(f"\nWrote {args.output_md} and {args.output_json}")
            raise
        rendered = response_text(response)
        summary = extract_json_summary(rendered)
        summary["model"] = args.model
        summary["response_id"] = response.get("id", "")

    write_text(args.output_md, rendered)
    write_json(args.output_json, summary)
    print(rendered if args.verbose else terminal_report(rendered, summary, terminal_title, labels))
    if args.verbose:
        print(f"\nWrote {args.output_md} and {args.output_json}")
    return 0
