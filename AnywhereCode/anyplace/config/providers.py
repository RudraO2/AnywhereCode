"""Facts about LLM providers that every layer needs to agree on.

Deliberately dependency-free: it imports nothing from ``anyplace`` and nothing
outside the standard library, so the pure-logic modules (``core.doctor``), the
config layer, and the CLI can all rely on it without any of them importing
each other.
"""

from __future__ import annotations

#: Providers that need no API key at all.
#:
#: OmniRoute is a gateway you run yourself. It holds whatever provider keys you
#: gave *it*, and answers on localhost with no auth of its own — so requiring a
#: key here would mean inventing one to satisfy a check.
KEYLESS_PROVIDERS = frozenset({"omniroute"})


def needs_api_key(provider: str) -> bool:
    """Does this provider require the user to supply a key?"""
    return (provider or "").strip().lower() not in KEYLESS_PROVIDERS
