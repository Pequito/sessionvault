"""ANSI / VT escape-sequence parser.

Returns ``(text, style)`` tuples where *style* is a plain dict::

    {
        "fg":        "#rrggbb" | None,
        "bg":        "#rrggbb" | None,
        "bold":      bool,
        "underline": bool,
    }

Intentionally free of Qt dependencies so the parser can be unit-tested
in isolation and reused without a display.
"""

from __future__ import annotations

import re
from typing import Optional

from app.constants import ANSI_COLORS_16, ANSI_256_CACHE

# ---------------------------------------------------------------------------
# Type alias
# ---------------------------------------------------------------------------
Style = dict  # {"fg": str|None, "bg": str|None, "bold": bool, "underline": bool}

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------
_CSI_RE = re.compile(r"\x1b\[([0-9;]*)([A-Za-z])")
_BARE_ESC_RE = re.compile(r"\x1b[^\x1b]?")


# ---------------------------------------------------------------------------
# 256-color lookup (standalone so it can be tested / reused)
# ---------------------------------------------------------------------------

def color_256(n: int) -> str:
    """Convert a 256-colour palette index to a ``#rrggbb`` string."""
    if n in ANSI_256_CACHE:
        return ANSI_256_CACHE[n]
    if n < 16:
        color = ANSI_COLORS_16[n]
    elif n < 232:
        # 6×6×6 colour cube
        idx = n - 16
        b = idx % 6
        g = (idx // 6) % 6
        r = (idx // 36) % 6

        def _v(x: int) -> int:
            return 0 if x == 0 else 55 + x * 40

        color = f"#{_v(r):02x}{_v(g):02x}{_v(b):02x}"
    else:
        # 24-step greyscale ramp
        v = 8 + (n - 232) * 10
        color = f"#{v:02x}{v:02x}{v:02x}"
    ANSI_256_CACHE[n] = color
    return color


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class AnsiParser:
    """Stateful ANSI/VT escape-sequence parser.

    Call :meth:`feed` repeatedly with incoming terminal data; each call
    returns a list of ``(text, style)`` pairs ready for rendering.
    """

    def __init__(self) -> None:
        self._fg: Optional[str] = None
        self._bg: Optional[str] = None
        self._bold = False
        self._underline = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def feed(self, data: str) -> list[tuple[str, Style]]:
        """Parse *data* and return a list of (text, style) pairs."""
        result: list[tuple[str, Style]] = []
        pos = 0
        for m in _CSI_RE.finditer(data):
            start, end = m.span()
            if start > pos:
                chunk = _BARE_ESC_RE.sub("", data[pos:start])
                if chunk:
                    result.append((chunk, self._snapshot()))
            self._handle_csi(m.group(1), m.group(2))
            pos = end
        if pos < len(data):
            chunk = _BARE_ESC_RE.sub("", data[pos:])
            if chunk:
                result.append((chunk, self._snapshot()))
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _snapshot(self) -> Style:
        return {
            "fg": self._fg,
            "bg": self._bg,
            "bold": self._bold,
            "underline": self._underline,
        }

    def _handle_csi(self, params_str: str, command: str) -> None:
        if command == "m":
            self._handle_sgr(params_str)
        # Other CSI commands (cursor movement, erase lines, …) are ignored

    def _handle_sgr(self, params_str: str) -> None:
        try:
            params = (
                [int(p) if p else 0 for p in params_str.split(";")]
                if params_str
                else [0]
            )
        except ValueError:
            return

        i = 0
        while i < len(params):
            p = params[i]
            if p == 0:
                self._fg = self._bg = None
                self._bold = self._underline = False
            elif p == 1:
                self._bold = True
            elif p == 4:
                self._underline = True
            elif p == 22:
                self._bold = False
            elif p == 24:
                self._underline = False
            elif p == 39:
                self._fg = None
            elif p == 49:
                self._bg = None
            elif 30 <= p <= 37:
                self._fg = ANSI_COLORS_16[p - 30]
            elif 40 <= p <= 47:
                self._bg = ANSI_COLORS_16[p - 40]
            elif 90 <= p <= 97:
                self._fg = ANSI_COLORS_16[p - 90 + 8]
            elif 100 <= p <= 107:
                self._bg = ANSI_COLORS_16[p - 100 + 8]
            elif p in (38, 48):
                if i + 2 < len(params) and params[i + 1] == 5:
                    color = color_256(params[i + 2])
                    if p == 38:
                        self._fg = color
                    else:
                        self._bg = color
                    i += 2
                elif i + 4 < len(params) and params[i + 1] == 2:
                    r, g, b = params[i + 2], params[i + 3], params[i + 4]
                    color = f"#{r:02x}{g:02x}{b:02x}"
                    if p == 38:
                        self._fg = color
                    else:
                        self._bg = color
                    i += 4
            i += 1
