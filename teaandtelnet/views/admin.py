"""Admin Settings — only reachable by admins. Configure the BBS name, chat
rooms, tables, and who is an admin.
"""

from .. import config, db, screen
from ..widgets import CANCEL, LineEditor
from .base import View


class AdminView(View):
    MENU = "menu"
    BBSNAME = "bbsname"
    SLOTS = "slots"
    QUITMSG = "quitmsg"
    BUSYMSG = "busymsg"
    ROOMS = "rooms"
    TABLES = "tables"
    USERS = "users"
    ADD_NAME = "add_name"
    ADD_DESC = "add_desc"
    CONFIRM_DEL = "confirm_del"

    MENU_ITEMS = [
        "Set BBS name",
        "Set online slots",
        "Set quit message",
        "Set busy message",
        "Manage chat rooms",
        "Manage tables",
        "Manage users",
        "Back to main menu",
    ]

    def __init__(self):
        self.mode = self.MENU
        self.sel = 0
        self.list_sel = 0
        self.editor = None
        self.add_target = None  # "room" or "table"
        self.add_name = ""
        self.del_target = None  # (kind, id, label)
        self.message = ""
        self.message_color = "brgreen"

    async def enter(self, session):
        if not session.user["is_admin"]:
            return session.mainmenu  # safety net; not reachable normally
        self._render(session)

    # -- rendering ----------------------------------------------------------- #
    def _frame(self, session, body, footer, cursor=None):
        w, h = session.width, session.height
        lines = [screen.color(" ★ Admin Settings", "brmagenta"),
                 screen.color(screen.HZ * w, "white"), ""]
        lines.extend(body)
        while len(lines) < h - 1:
            lines.append("")
        if self.message:
            lines.append(screen.color(" " + self.message, self.message_color))
        else:
            lines.append(screen.DIM + footer + screen.RESET)
        self.paint(session, lines[:h], cursor=cursor)

    def _menu_body(self, items, sel):
        body = []
        for i, item in enumerate(items):
            if i == sel:
                body.append("   " + screen.REVERSE + f" {item} " + screen.RESET)
            else:
                body.append(f"    {item}")
        return body

    def _render(self, session):
        if self.mode == self.MENU:
            self._frame(session, self._menu_body(self.MENU_ITEMS, self.sel),
                        " ↑↓ select · Enter choose · Esc back")
        elif self.mode == self.BBSNAME:
            field = "BBS name: " + self.editor.display()
            self._frame(session, ["  Shown under the logo on every screen.", "", "  " + field],
                        " Enter to save · Esc to cancel",
                        cursor=(6, 2 + len("BBS name: ") + len(self.editor.display()) + 1))
        elif self.mode == self.SLOTS:
            field = "Online slots: " + self.editor.display()
            self._frame(session,
                        ["  Max simultaneous connections ('phone lines'). Extra",
                         "  callers get a busy signal. Status bar shows \"n/x online\".",
                         "  0 = unlimited (status shows just \"n online\").",
                         "", "  " + field],
                        " Enter to save · Esc to cancel",
                        cursor=(8, 2 + len("Online slots: ") + len(self.editor.display()) + 1))
        elif self.mode in (self.QUITMSG, self.BUSYMSG):
            if self.mode == self.QUITMSG:
                hint = "  Shown when a user quits. {slots} = online-slot count."
            else:
                hint = "  Shown when the BBS is full. Use {slots} for the line count."
            value = self.editor.display()
            body = [hint, "", "  > " + value]
            self._frame(session, body, " Enter to save · Esc to cancel",
                        cursor=(6, 2 + len("> ") + len(value) + 1))
        elif self.mode == self.ROOMS:
            self._render_collection(session, "Chat rooms", db.list_rooms(),
                                    lambda r: f"{r['name']}  —  {r['topic']}")
        elif self.mode == self.TABLES:
            self._render_collection(session, "Tables", db.list_boards(),
                                    lambda b: f"{b['name']}  —  {b['description']}")
        elif self.mode == self.USERS:
            self._render_users(session)
        elif self.mode in (self.ADD_NAME, self.ADD_DESC):
            label = "Name:" if self.mode == self.ADD_NAME else (
                "Topic:" if self.add_target == "room" else "Description:")
            kind = "chat room" if self.add_target == "room" else "table"
            body = [f"  New {kind}", ""]
            if self.mode == self.ADD_DESC:
                body.append(f"  Name: {self.add_name}")
            body.append("  " + label + " " + self.editor.display())
            row = len(body) + 2
            self._frame(session, body, " Enter to continue · Esc to cancel",
                        cursor=(row, 2 + len(label) + 1 + len(self.editor.display()) + 1))
        elif self.mode == self.CONFIRM_DEL:
            _, _, label = self.del_target
            body = [screen.color(f"  Delete '{label}'? This removes its contents too.", "red"),
                    "", "  Press Y to confirm, N or Esc to cancel."]
            self._frame(session, body, " Y confirm · N cancel")

    def _render_collection(self, session, title, rows, fmt):
        self.list_sel = max(0, min(self.list_sel, len(rows)))  # last index = "+ Add"
        body = [screen.color(f"  {title}", "bryellow"), ""]
        for i, r in enumerate(rows):
            text = "    " + fmt(r)
            if i == self.list_sel:
                body.append("  " + screen.REVERSE + screen.pad(" " + fmt(r), session.width - 4) + screen.RESET)
            else:
                body.append(text)
        add_idx = len(rows)
        add_label = "+ Add new"
        if self.list_sel == add_idx:
            body.append("  " + screen.color(screen.REVERSE + f" {add_label} " + screen.RESET, "brgreen"))
        else:
            body.append("    " + screen.color(add_label, "brgreen"))
        self._frame(session, body, " ↑↓ select · Enter add · D delete · Esc back")

    def _render_users(self, session):
        users = db.list_users()
        self.list_sel = max(0, min(self.list_sel, max(0, len(users) - 1)))
        body = [screen.color("  Users  (Enter toggles admin)", "bryellow"), ""]
        for i, u in enumerate(users):
            tag = screen.color(" [admin]", "brmagenta") if u["is_admin"] else ""
            line = f"    {u['username']}{' [admin]' if u['is_admin'] else ''}"
            if i == self.list_sel:
                body.append("  " + screen.REVERSE + screen.pad(f" {u['username']}" + (" [admin]" if u["is_admin"] else ""), session.width - 4) + screen.RESET)
            else:
                body.append(f"    {u['username']}" + tag)
        self._frame(session, body, " ↑↓ select · Enter toggle admin · Esc back")

    # -- input --------------------------------------------------------------- #
    async def handle(self, session, kind, data):
        if kind != "key":
            return None
        key = data
        self.message = ""
        if self.mode == self.MENU:
            return self._handle_menu(session, key)
        if self.mode == self.BBSNAME:
            return self._handle_bbsname(session, key)
        if self.mode == self.SLOTS:
            return self._handle_slots(session, key)
        if self.mode in (self.QUITMSG, self.BUSYMSG):
            return self._handle_message(session, key)
        if self.mode == self.ROOMS:
            return self._handle_collection(session, key, "room")
        if self.mode == self.TABLES:
            return self._handle_collection(session, key, "table")
        if self.mode == self.USERS:
            return self._handle_users(session, key)
        if self.mode in (self.ADD_NAME, self.ADD_DESC):
            return self._handle_add(session, key)
        if self.mode == self.CONFIRM_DEL:
            return self._handle_confirm(session, key)
        return None

    def _handle_menu(self, session, key):
        if key in ("ESC", "q", "Q", "LEFT"):
            return session.mainmenu
        if key == "UP":
            self.sel = (self.sel - 1) % len(self.MENU_ITEMS)
        elif key == "DOWN":
            self.sel = (self.sel + 1) % len(self.MENU_ITEMS)
        elif key == "ENTER":
            choice = self.MENU_ITEMS[self.sel]
            if choice == "Set BBS name":
                self.editor = LineEditor(text=db.bbs_name(), max_len=60)
                self.mode = self.BBSNAME
            elif choice == "Set online slots":
                cur = db.max_slots()
                self.editor = LineEditor(text=str(cur) if cur else "", max_len=5)
                self.mode = self.SLOTS
            elif choice == "Set quit message":
                self.editor = LineEditor(text=db.quit_message(), max_len=200)
                self.mode = self.QUITMSG
            elif choice == "Set busy message":
                self.editor = LineEditor(text=db.busy_message(), max_len=200)
                self.mode = self.BUSYMSG
            elif choice == "Manage chat rooms":
                self.list_sel = 0
                self.mode = self.ROOMS
            elif choice == "Manage tables":
                self.list_sel = 0
                self.mode = self.TABLES
            elif choice == "Manage users":
                self.list_sel = 0
                self.mode = self.USERS
            elif choice == "Back to main menu":
                return session.mainmenu
        self._render(session)
        return None

    def _handle_bbsname(self, session, key):
        result = self.editor.handle(key)
        if result is None:
            self._render(session)
            return None
        signal, value = result
        if signal != CANCEL:
            value = value.strip()
            if value:
                db.set_setting("bbs_name", value)
                self.message = "BBS name updated."
        self.mode = self.MENU
        self._render(session)
        return None

    def _handle_slots(self, session, key):
        result = self.editor.handle(key)
        if result is None:
            self._render(session)
            return None
        signal, value = result
        if signal != CANCEL:
            value = value.strip()
            if value == "" or value == "0":
                db.set_max_slots(0)
                self.message = "Online slots hidden."
            elif value.isdigit():
                db.set_max_slots(int(value))
                self.message = f"Online slots set to {int(value)}."
            else:
                self.message = "Please enter a number."
                self.message_color = "red"
        self.mode = self.MENU
        self._render(session)
        return None

    def _handle_message(self, session, key):
        is_quit = self.mode == self.QUITMSG
        result = self.editor.handle(key)
        if result is None:
            self._render(session)
            return None
        signal, value = result
        if signal != CANCEL:
            value = value.strip()
            if value:
                if is_quit:
                    db.set_quit_message(value)
                    self.message = "Quit message updated."
                else:
                    db.set_busy_message(value)
                    self.message = "Busy message updated."
        self.mode = self.MENU
        self._render(session)
        return None

    def _handle_collection(self, session, key, target):
        rows = db.list_rooms() if target == "room" else db.list_boards()
        add_idx = len(rows)
        if key in ("ESC", "q", "Q", "LEFT"):
            self.mode = self.MENU
            label = "Manage chat rooms" if target == "room" else "Manage tables"
            self.sel = self.MENU_ITEMS.index(label)
            self._render(session)
            return None
        if key == "UP":
            self.list_sel = max(0, self.list_sel - 1)
        elif key == "DOWN":
            self.list_sel = min(add_idx, self.list_sel + 1)
        elif key == "ENTER" and self.list_sel == add_idx:
            self.add_target = target
            self.add_name = ""
            self.editor = LineEditor(max_len=40)
            self.mode = self.ADD_NAME
        elif key in ("d", "D") and self.list_sel < add_idx:
            r = rows[self.list_sel]
            self.del_target = (target, r["id"], r["name"])
            self.mode = self.CONFIRM_DEL
        self._render(session)
        return None

    def _handle_add(self, session, key):
        result = self.editor.handle(key)
        if result is None:
            self._render(session)
            return None
        signal, value = result
        if signal == CANCEL:
            self.mode = self.ROOMS if self.add_target == "room" else self.TABLES
            self._render(session)
            return None
        value = value.strip()
        if self.mode == self.ADD_NAME:
            if not value:
                self.mode = self.ROOMS if self.add_target == "room" else self.TABLES
                self._render(session)
                return None
            self.add_name = value
            self.editor = LineEditor(max_len=80)
            self.mode = self.ADD_DESC
        else:  # ADD_DESC
            if self.add_target == "room":
                db.add_room(self.add_name, value)
                self.message = f"Room '{self.add_name}' created."
                self.mode = self.ROOMS
            else:
                db.add_board(self.add_name, value)
                self.message = f"Table '{self.add_name}' created."
                self.mode = self.TABLES
            self.list_sel = 0
        self._render(session)
        return None

    def _handle_confirm(self, session, key):
        target, obj_id, label = self.del_target
        if key in ("y", "Y"):
            if target == "room":
                db.delete_room(obj_id)
                self.mode = self.ROOMS
            else:
                db.delete_board(obj_id)
                self.mode = self.TABLES
            self.message = f"Deleted '{label}'."
            self.list_sel = 0
        else:
            self.mode = self.ROOMS if target == "room" else self.TABLES
        self.del_target = None
        self._render(session)
        return None

    def _handle_users(self, session, key):
        users = db.list_users()
        if key in ("ESC", "q", "Q", "LEFT"):
            self.mode = self.MENU
            self.sel = self.MENU_ITEMS.index("Manage users")
            self._render(session)
            return None
        if key == "UP":
            self.list_sel = max(0, self.list_sel - 1)
        elif key == "DOWN":
            self.list_sel = min(max(0, len(users) - 1), self.list_sel + 1)
        elif key == "ENTER" and users:
            u = users[self.list_sel]
            admins = sum(1 for x in users if x["is_admin"])
            if u["is_admin"] and admins <= 1:
                self.message = "Can't demote the last admin."
                self.message_color = "red"
            else:
                db.set_admin(u["id"], not u["is_admin"])
                self.message = f"{u['username']} is now {'an admin' if not u['is_admin'] else 'a member'}."
                self.message_color = "brgreen"
                if session.user["id"] == u["id"]:
                    session.user = db.get_user(u["username"])  # refresh own role
        self._render(session)
        return None
