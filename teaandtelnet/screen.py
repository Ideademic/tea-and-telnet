"""ANSI rendering helpers — colours, boxes, panels and full-screen painting."""

import re

ESC = "\x1b"
RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
REVERSE = "\x1b[7m"

# Single-hue YELLOW theme. Every legacy colour name is intentionally mapped to
# a shade of yellow so the whole app reads as one colour; brightness + the bold
# and reverse attributes still provide all the visual hierarchy we need.
_BRIGHT = "\x1b[93m"  # bright yellow — primary accent / active / highlights
_GOLD = "\x1b[33m"    # normal yellow — borders, dividers, secondary accents
FG = {
    "bryellow": _BRIGHT, "yellow": _GOLD,
    "brcyan": _BRIGHT,   "cyan": _GOLD,
    "brgreen": _BRIGHT,  "green": _GOLD,
    "brwhite": _BRIGHT,  "white": _GOLD,
    "brmagenta": _BRIGHT, "magenta": _GOLD,
    "red": _BRIGHT,      "blue": _GOLD,
    "black": "\x1b[30m",
}

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

# Box drawing
TL, TR, BL, BR = "┌", "┐", "└", "┘"
HZ, VT = "─", "│"


def color(text: str, name: str) -> str:
    return f"{FG[name]}{text}{RESET}"


def visible_len(s: str) -> int:
    return len(_ANSI_RE.sub("", s))


def clip(s: str, width: int) -> str:
    """Truncate to a visible width, ignoring ANSI codes (assumes plain text)."""
    if len(s) <= width:
        return s
    if width <= 1:
        return s[:width]
    return s[: width - 1] + "…"


def pad(s: str, width: int) -> str:
    """Right-pad plain text to a visible width."""
    return s + " " * max(0, width - visible_len(s))


def cursor(row: int, col: int) -> str:
    return f"\x1b[{row};{col}H"


HIDE_CURSOR = "\x1b[?25l"
SHOW_CURSOR = "\x1b[?25h"
HOME = "\x1b[H"
CLEAR = "\x1b[2J\x1b[H"


def panel(title: str, items: list[str], selected: int, active: bool,
          width: int, height: int) -> list[str]:
    """Render a bordered, scrollable, optionally-active list panel.

    `items` are pre-formatted plain strings. Returns exactly `height` lines.
    """
    inner_w = width - 2
    inner_h = height - 2
    border_c = "brcyan" if active else "white"

    # Top border with the title embedded, e.g. ┌─ Chats ─────┐
    title_txt = clip(f"─ {title} ", inner_w - 1)
    bar = title_txt + HZ * (inner_w - len(title_txt))
    if active:
        top = color(TL, border_c) + BOLD + FG["brcyan"] + bar + RESET + color(TR, border_c)
    else:
        top = color(TL + bar + TR, border_c)

    # Scroll so the selection stays visible.
    start = 0
    if len(items) > inner_h:
        if selected >= inner_h:
            start = min(selected - inner_h + 1, len(items) - inner_h)
        start = max(0, start)
    visible = items[start:start + inner_h]

    lines = [top]
    for i, raw in enumerate(visible):
        idx = start + i
        text = clip(raw, inner_w)
        if idx == selected and active:
            cell = REVERSE + pad(text, inner_w) + RESET
        elif idx == selected:
            cell = FG["bryellow"] + pad(text, inner_w) + RESET
        else:
            cell = pad(text, inner_w)
        lines.append(color(VT, border_c) + cell + color(VT, border_c))
    for _ in range(inner_h - len(visible)):
        lines.append(color(VT, border_c) + " " * inner_w + color(VT, border_c))
    lines.append(color(BL + HZ * inner_w + BR, border_c))
    return lines


def join_panels(panels: list[list[str]], gap: int = 1) -> list[str]:
    """Place equal-height panels side by side."""
    height = max(len(p) for p in panels)
    sep = " " * gap
    out = []
    for r in range(height):
        out.append(sep.join(p[r] if r < len(p) else "" for p in panels))
    return out


def center(text: str, width: int) -> str:
    pad_total = max(0, width - visible_len(text))
    left = pad_total // 2
    return " " * left + text
