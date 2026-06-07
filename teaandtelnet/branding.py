"""The Tea & Telnet logo and shared header rendering."""

from . import db, screen

# The logo exactly as provided: a 582-char string = 6 rows of 97 columns,
# using '%' for ink and '.' for background. Rendered verbatim, no substitution.
LOGO_RAW = ".%%%%%%..%%%%%%...%%%%............%%%%%...........%%%%%%..%%%%%%..%%......%%..%%..%%%%%%..%%%%%%....%%....%%......%%..%%..........%%...%%............%%....%%......%%......%%%.%%..%%........%%......%%....%%%%....%%%%%%...........%%.%%.............%%....%%%%....%%......%%.%%%..%%%%......%%......%%....%%......%%..%%..........%%.%%.%............%%....%%......%%......%%..%%..%%........%%......%%....%%%%%%..%%..%%...........%%%%%.............%%....%%%%%%..%%%%%%..%%..%%..%%%%%%....%%...................................................................................................."  # noqa: E501

_WIDTH = 97
# The first five rows are the artwork; the sixth row is blank padding.
LOGO = [LOGO_RAW[i * _WIDTH:(i + 1) * _WIDTH] for i in range(5)]
LOGO_WIDTH = _WIDTH


def _compact_box() -> list[str]:
    """Bold 'TEA & TELNET' inside a double-line box, for small terminals."""
    title = "TEA & TELNET"
    inner = f"   {title}   "
    w = len(inner)
    bright = screen.BOLD + screen.FG["bryellow"]
    top = bright + "╔" + "═" * w + "╗" + screen.RESET
    mid = bright + "║" + inner + "║" + screen.RESET
    bot = bright + "╚" + "═" * w + "╝" + screen.RESET
    return [top, mid, bot]


def header_lines(width: int) -> list[str]:
    """Centered logo + the admin-configurable BBS name underneath it.

    Wide terminals get the full block logo; narrow ones get the compact box.
    """
    if width >= LOGO_WIDTH:
        art = [screen.color(row, "bryellow") for row in LOGO]
    else:
        art = _compact_box()
    lines = [screen.center(row, width) for row in art]
    name = db.bbs_name()
    lines.append(screen.center(screen.color(f"~ {name} ~", "bryellow"), width))
    return lines
