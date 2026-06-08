"""The home screen: three navigable columns — Chats, Tables, Programs."""

from .. import branding, db, screen
from ..hub import hub
from .base import QUIT, View


class MainMenuView(View):
    CHATS, TABLES, PROGRAMS = 0, 1, 2

    def __init__(self):
        self.col = self.CHATS
        self.sel = [0, 0, 0]
        self.flash = ""

    # -- data ---------------------------------------------------------------- #
    def _columns(self, session):
        rooms = db.list_rooms()
        boards = db.list_boards()
        programs = ["Settings"]
        if session.user["is_admin"]:
            programs.append("Admin Settings")

        chat_items = [r["name"] for r in rooms] or ["(no rooms yet)"]
        table_items = []
        for b in boards:
            unread = db.unread_count(session.user["id"], b["id"])
            tag = f" ({unread})" if unread else ""
            table_items.append(f"{b['name']}{tag}")
        if not boards:
            table_items = ["(no tables yet)"]

        return rooms, boards, programs, [chat_items, table_items, programs]

    async def enter(self, session):
        self._render(session)

    def _render(self, session):
        w, h = session.width, session.height
        rooms, boards, programs, items = self._columns(session)

        # clamp selections
        for i in range(3):
            n = max(1, len(items[i]))
            self.sel[i] = max(0, min(self.sel[i], n - 1))

        lines = [""]
        lines += branding.header_lines(w)
        lines.append("")

        panel_h = h - len(lines) - 2  # leave room for footer
        panel_h = max(6, panel_h)
        col_w = (w - 4) // 3

        titles = ["Chats", "Tables", "Programs"]
        panels = []
        for i in range(3):
            panels.append(
                screen.panel(
                    titles[i], items[i], self.sel[i], self.col == i, col_w, panel_h
                )
            )
        body = screen.join_panels(panels, gap=1)
        # center the three-panel block
        block_w = screen.visible_len(body[0]) if body else 0
        pad_left = max(0, (w - block_w) // 2)
        for row in body:
            lines.append(" " * pad_left + row)

        # footer / status
        while len(lines) < h - 1:
            lines.append("")
        online = hub.online_count()
        slots = db.max_slots()
        online_txt = f"{online}/{slots} online" if slots else f"{online} online"
        admin_tag = screen.color(" [admin]", "brmagenta") if session.user["is_admin"] else ""
        status = (
            screen.color(f" {session.user['username']}", "brgreen")
            + admin_tag
            + screen.DIM
            + f"  ·  {online_txt}  ·  ↑↓ move  ←→ column  Enter open  Q quit"
            + screen.RESET
        )
        if self.flash:
            status = screen.color(" " + self.flash, "bryellow")
            self.flash = ""
        lines.append(status)
        self.paint(session, lines[:h])

    # -- input --------------------------------------------------------------- #
    async def handle(self, session, kind, data):
        if kind == "chat":
            return None  # ignore stray chat events on the menu
        key = data
        rooms, boards, programs, items = self._columns(session)

        if key in ("q", "Q", "CTRL_C"):
            session.write(screen.RESET + screen.SHOW_CURSOR + screen.CLEAR)
            session.write(db.format_message(db.quit_message()) + "\r\n")
            return QUIT
        if key == "LEFT":
            self.col = (self.col - 1) % 3
            self._render(session)
        elif key == "RIGHT":
            self.col = (self.col + 1) % 3
            self._render(session)
        elif key == "UP":
            self.sel[self.col] = max(0, self.sel[self.col] - 1)
            self._render(session)
        elif key == "DOWN":
            n = len(items[self.col])
            self.sel[self.col] = min(n - 1, self.sel[self.col] + 1)
            self._render(session)
        elif key == "ENTER":
            return self._activate(session, rooms, boards, programs)
        return None

    def _activate(self, session, rooms, boards, programs):
        if self.col == self.CHATS and rooms:
            from .chat import ChatView

            room = rooms[self.sel[0]]
            return ChatView(room["id"])
        if self.col == self.TABLES and boards:
            from .tables import BoardView

            board = boards[self.sel[1]]
            return BoardView(board["id"])
        if self.col == self.PROGRAMS:
            choice = programs[self.sel[2]]
            if choice == "Settings":
                from .programs import SettingsView

                return SettingsView()
            if choice == "Admin Settings":
                from .admin import AdminView

                return AdminView()
        return None
