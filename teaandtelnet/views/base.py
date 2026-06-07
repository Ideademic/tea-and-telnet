"""View base class and the QUIT sentinel.

A view's `handle` returns one of:
  * None             -> stay on this view
  * another View     -> switch to it
  * QUIT             -> disconnect the session
"""

from .. import screen

QUIT = object()


class View:
    async def enter(self, session) -> None:
        """Called when the view becomes active. Should paint the screen."""

    async def leave(self, session) -> None:
        """Called just before switching away."""

    async def handle(self, session, kind: str, data):
        """Handle one event. `kind` is 'key' or 'chat'."""
        return None

    # -- shared painting helpers -------------------------------------------- #
    def paint(self, session, lines: list[str], cursor=None) -> None:
        """Repaint the screen from the top using the given lines.

        Each line is cleared to EOL to avoid leftovers; the area below is
        cleared too. `cursor` may be a (row, col) tuple to show the caret.
        """
        out = [screen.HIDE_CURSOR, screen.HOME]
        for ln in lines:
            out.append(ln + "\x1b[K\r\n")
        out.append("\x1b[J")
        if cursor is not None:
            row, col = cursor
            out.append(screen.cursor(row, col) + screen.SHOW_CURSOR)
        session.write("".join(out))
