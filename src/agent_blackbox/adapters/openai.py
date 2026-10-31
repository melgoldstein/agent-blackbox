"""Opt-in text-only Responses API adapter. No reasoning items are persisted."""

from typing import Any


def respond(*, model: str, input: str) -> dict[str, Any]:
    from openai import OpenAI

    response = OpenAI().responses.create(model=model, input=input, store=False)
    return {
        "text": response.output_text,
        "model": response.model,
        "usage": {"input_tokens": response.usage.input_tokens,
                  "output_tokens": response.usage.output_tokens} if response.usage else None,
    }
