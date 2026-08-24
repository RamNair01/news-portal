"""Chat backend — streaming OpenAI responses with today's headlines as context."""

import os
import logging
from typing import Generator

from openai import OpenAI
from openai import APIError

from db.store import get_today_headlines

MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.6-terra")
MAX_CONTEXT_CHARS = 60_000
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a helpful news assistant. The user is reading their personal news dashboard. \
Use the provided news headlines as your primary context when answering questions.

Response principles:
- Be concise and direct. No preamble, no filler, no sign-off phrases.
- Cut hedging stacks and transitional summaries that repeat what was just said.
- When explaining concepts or events, lead with intuition and what it means before \
getting into details. Use clear analogies. One precise sentence beats three vague ones.
- If the user presents their own understanding of a news story, critically evaluate it: \
confirm what's right, correct what's wrong, and note what's missing — don't just agree.
- Tailor depth to the question. Short factual questions get short answers. \
Requests to explain something get a proper breakdown.

Today's news headlines:
{context}
"""


def _build_context() -> str:
    items = get_today_headlines()
    sections: dict[str, list[str]] = {}
    for item in items:
        cat = item["category"].upper()
        sections.setdefault(cat, []).append(f"[{item['source']}] {item['title']}")

    parts = []
    for cat, lines in sections.items():
        parts.append(f"--- {cat} ---")
        parts.extend(lines)

    context = "\n".join(parts)
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS] + "\n...[truncated]"
    return context


def stream_chat(messages: list[dict]) -> Generator[str, None, None]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        yield "Error: OPENAI_API_KEY is not configured."
        return

    client = OpenAI(api_key=api_key)
    context = _build_context()
    system = SYSTEM_PROMPT.format(context=context or "No news items available yet.")

    try:
        with client.responses.stream(
            model=MODEL,
            instructions=system,
            input=messages,
        ) as stream:
            for event in stream:
                if event.type == "response.output_text.delta":
                    yield event.delta
    except APIError as exc:
        logger.warning("News assistant request failed: %s", exc)
        if "quota" in str(exc).lower():
            yield "The news assistant needs OpenAI API billing or credits before it can reply."
        else:
            yield "The news assistant is temporarily unavailable. Please try again shortly."
