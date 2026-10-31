"""Redaction of the user's home directory in exported reports.

By default, JSON and Markdown reports replace the current user's home
directory with ``~`` so that reports can be shared without revealing the
user name or directory layout. Redaction is case-insensitive on Windows
and handles both separator styles. The ``--no-redact`` CLI flag disables
it for users who need full paths.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any


def default_home() -> str:
    """Return the current user's home directory as a string."""
    return str(Path.home())


def redact_text(text: str, home: str) -> str:
    """Replace occurrences of *home* in *text* with ``~``.

    Both native-separator and forward-slash spellings of *home* are
    replaced. Matching is case-insensitive on Windows only, and only
    matches path boundaries so ``/home/alice2`` survives when the home
    directory is ``/home/alice``.
    """
    if not home or not text:
        return text
    variants = {home, home.replace("\\", "/")}
    if os.sep != "\\":
        variants.add(home.replace("\\", os.sep))
    flags = re.IGNORECASE if os.name == "nt" else 0
    for variant in sorted(variants, key=len, reverse=True):
        if not variant:
            continue
        pattern = re.compile(re.escape(variant) + r"(?=$|[/\\])", flags)
        text = pattern.sub("~", text)
    return text


def redact_value(value: Any, home: str) -> Any:
    """Recursively redact every string inside a JSON-like structure."""
    if isinstance(value, str):
        return redact_text(value, home)
    if isinstance(value, dict):
        return {key: redact_value(item, home) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_value(item, home) for item in value]
    return value
