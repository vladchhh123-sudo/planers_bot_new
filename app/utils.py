from __future__ import annotations

import html
import re
from typing import Any


_TAG_RE = re.compile(r"<[^>]+>")


def user_first_name(user: Any) -> str:
    first_name = getattr(user, "first_name", None) or "друг"
    return html.escape(first_name, quote=False)


def render_text(template: str, *, name: str, **extra: Any) -> str:
    data = {"name": name, **extra}
    return template.format(**data)


def visible_text_length(text: str) -> int:
    without_tags = _TAG_RE.sub("", text)
    return len(without_tags)
