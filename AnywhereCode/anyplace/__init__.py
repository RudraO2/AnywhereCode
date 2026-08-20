"""
Anywhere Code — an AI coding CLI that actually works on a phone.

Termux-first, small-screen-first, thumb-first. Ask a few questions,
get a real project, ship it — from the device in your pocket.
"""

__version__ = "2.0.0"

#: Product name as shown to humans.
NAME = "Anywhere Code"

#: Single-line pitch, kept under 48 chars so it fits a phone screen.
TAGLINE = "Build and ship from a phone."

#: Longer pitch for --help and docs.
DESCRIPTION = (
    "An AI coding CLI designed for small screens and thumbs. "
    "Answer a few questions, get a working project, run it anywhere."
)

#: The command users type. `anyplace` stays as a compatibility alias.
COMMAND = "anywhere"

__all__ = ["__version__", "NAME", "TAGLINE", "DESCRIPTION", "COMMAND"]
