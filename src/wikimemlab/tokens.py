"""Proxy token counting: chars/4, documented and deliberately vendor-free.

No vendor tokenizer ships here - that would add a dependency and imply the
absolute counts matter. They don't: every published figure is a RATIO between
modes measured with the same proxy, and the proxy is stated next to every
number. chars/4 is the common rule of thumb for English text.
"""
from __future__ import annotations

import math


def proxy_tokens(text: str) -> int:
    """ceil(len/4); empty text costs 0."""
    if not text:
        return 0
    return math.ceil(len(text) / 4)
