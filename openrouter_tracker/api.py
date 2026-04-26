#!/usr/bin/env python3
"""OpenRouter API client for credit/usage data."""
import json
import os
import urllib.error
import urllib.request
from typing import Any

from openrouter_tracker.config import OPENROUTER_BASE_URL


def _get_key() -> str:
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. "
            "Export it in your environment or add it to ~/.profile."
        )
    return key


def _fetch_json(path: str, *, optional: bool = False) -> dict[str, Any] | None:
    req = urllib.request.Request(
        f"{OPENROUTER_BASE_URL}{path}",
        headers={
            "Authorization": f"Bearer {_get_key()}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        if optional and exc.code in {401, 403, 404}:
            return {"error": f"HTTP {exc.code}: {exc.reason}"}
        print(f"HTTP error {exc.code}: {exc.reason}")
    except Exception as exc:
        print(f"Request error: {exc}")
    return None


def fetch_usage() -> dict[str, Any] | None:
    """Fetch current key limits plus account-level credits when available."""
    key_data = _fetch_json("/api/v1/key")
    if key_data is None:
        return None

    credits_data = _fetch_json("/api/v1/credits", optional=True)
    return {
        "key": key_data,
        "credits": credits_data,
    }
