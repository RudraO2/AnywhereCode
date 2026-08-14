"""
Terminal QR codes.

Used to hand a freshly-built APK to a second device: the phone that ran the
build prints a QR, another phone scans it and downloads. Rendered with
half-block characters so the code is half as tall as the naive one-cell-per-
module version — on a phone terminal, full-height QR codes scroll off screen
and become unscannable.

`qrcode` is a pure-Python dependency (no native build, so it installs fine
under Termux), but rendering degrades to a plain URL if it is missing rather
than taking the command down with it.
"""

from typing import List, Optional

# Upper half filled / lower half filled / both / neither.
# QR "dark" modules are rendered as light terminal cells, because virtually
# every phone camera expects dark-on-light and many terminals are dark-themed.
_UPPER = "▀"  # ▀
_LOWER = "▄"  # ▄
_FULL = "█"   # █
_EMPTY = " "


def is_available() -> bool:
    """True when the optional `qrcode` dependency is importable."""
    try:
        import qrcode  # noqa: F401
    except ImportError:
        return False
    return True


def _matrix(data: str, border: int = 2) -> Optional[List[List[bool]]]:
    """Encode `data` and return the module matrix, or None if unavailable."""
    try:
        import qrcode
    except ImportError:
        return None

    code = qrcode.QRCode(
        border=border,
        # Low correction keeps the code small; a screen is a clean scan
        # surface, unlike print.
        error_correction=qrcode.constants.ERROR_CORRECT_L,
    )
    code.add_data(data)
    code.make(fit=True)
    return code.get_matrix()


def render(data: str, border: int = 2) -> Optional[str]:
    """
    Render `data` as a QR code using half-block characters.

    Each output line encodes two matrix rows, so the result is roughly square
    in a terminal where cells are twice as tall as they are wide.

    Returns:
        The rendered block, or None when `qrcode` is not installed.
    """
    matrix = _matrix(data, border=border)
    if matrix is None:
        return None

    width = len(matrix[0])
    lines: List[str] = []

    for row_index in range(0, len(matrix), 2):
        top = matrix[row_index]
        # Pad an odd-height matrix with a blank (light) row.
        bottom = matrix[row_index + 1] if row_index + 1 < len(matrix) else [False] * width

        line = []
        for column in range(width):
            # A "dark" QR module becomes an unlit terminal cell.
            top_light = not top[column]
            bottom_light = not bottom[column]

            if top_light and bottom_light:
                line.append(_FULL)
            elif top_light:
                line.append(_UPPER)
            elif bottom_light:
                line.append(_LOWER)
            else:
                line.append(_EMPTY)
        lines.append("".join(line))

    return "\n".join(lines)


def print_qr(data: str, console=None, label: str = "") -> bool:
    """
    Print a QR code for `data`, falling back to the raw value.

    Args:
        data: Text to encode (typically a download URL).
        console: Optional rich Console; plain `print` is used when omitted.
        label: Short caption shown above the code.

    Returns:
        True if a QR code was drawn, False if only the URL was printed.
    """
    write = console.print if console is not None else print

    rendered = render(data)
    if rendered is None:
        write(f"{label}\n{data}" if label else data)
        return False

    if label:
        write(label)
    # Printed without markup so rich never tries to interpret block glyphs.
    if console is not None:
        console.print(rendered, markup=False, highlight=False)
    else:
        print(rendered)
    write(data)
    return True
