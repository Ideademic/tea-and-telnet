"""The Programs column lands here: per-user Settings."""

import time

from .. import db, screen
from ..hub import hub
from ..widgets import CANCEL, LineEditor
from .base import View


class SettingsView(View):
    MENU = "menu"
    OLD = "old"
    NEW = "new"
    CONFIRM = "confirm"

    ITEMS = ["Change password", "Who's online", "Account info", "Back to main menu"]

    def __init__(self):
        self.mode = self.MENU
        self.sel = 0
        self.editor = None
        self.new_pw = ""
        self.message = ""
        self.message_color = "white"

    async def enter(self, session):
        self._render(session)

    def _frame(self, session, body_lines, footer, cursor=None):
        w, h = session.width, session.height
        lines = [screen.color(" ⚙ Settings", "brcyan"), screen.color(screen.HZ * w, "white"), ""]
        lines.extend(body_lines)
        while len(lines) < h - 1:
            lines.append("")
        if self.message:
            footer = screen.color(" " + self.message, self.message_color)
        lines.append(footer if footer.startswith("\x1b") else screen.DIM + footer + screen.RESET)
        self.paint(session, lines[:h], cursor=cursor)

    def _render(self, session):
        if self.mode == self.MENU:
            body = []
            for i, item in enumerate(self.ITEMS):
                if i == self.sel:
                    body.append("   " + screen.REVERSE + f" {item} " + screen.RESET)
                else:
                    body.append(f"    {item}")
            self._frame(session, body, " ↑↓ select · Enter choose · Esc back")
        elif self.mode in (self.OLD, self.NEW, self.CONFIRM):
            label = {self.OLD: "Current password:", self.NEW: "New password:",
                     self.CONFIRM: "Confirm new password:"}[self.mode]
            field = f"{label} {self.editor.display()}"
            self._frame(session, ["  " + field], " Enter to continue · Esc to cancel",
                        cursor=(4, 2 + len(label) + 1 + len(self.editor.display()) + 1))
        elif self.mode == "online":
            names = hub.online_names()
            body = [screen.color(f"  {len(names)} user(s) online:", "bryellow"), ""]
            body += [f"    • {n}" for n in names]
            self._frame(session, body, " Esc back")
        elif self.mode == "info":
            u = session.user
            created = time.strftime("%b %d, %Y", time.localtime(u["created_at"]))
            body = [
                f"  Username : {u['username']}",
                f"  Role     : {'Administrator' if u['is_admin'] else 'Member'}",
                f"  Joined   : {created}",
            ]
            self._frame(session, body, " Esc back")

    async def handle(self, session, kind, data):
        if kind != "key":
            return None
        key = data
        self.message = ""
        if self.mode == self.MENU:
            return self._handle_menu(session, key)
        if self.mode in (self.OLD, self.NEW, self.CONFIRM):
            return self._handle_pw(session, key)
        # online / info screens
        if key in ("ESC", "BACKSPACE", "q", "Q", "ENTER"):
            self.mode = self.MENU
            self._render(session)
        return None

    def _handle_menu(self, session, key):
        if key in ("ESC", "q", "Q", "LEFT"):
            return session.mainmenu
        if key == "UP":
            self.sel = (self.sel - 1) % len(self.ITEMS)
        elif key == "DOWN":
            self.sel = (self.sel + 1) % len(self.ITEMS)
        elif key == "ENTER":
            choice = self.ITEMS[self.sel]
            if choice == "Change password":
                self.mode = self.OLD
                self.editor = LineEditor(masked=True, max_len=64)
            elif choice == "Who's online":
                self.mode = "online"
            elif choice == "Account info":
                self.mode = "info"
            elif choice == "Back to main menu":
                return session.mainmenu
        self._render(session)
        return None

    def _handle_pw(self, session, key):
        result = self.editor.handle(key)
        if result is None:
            self._render(session)
            return None
        signal, value = result
        if signal == CANCEL:
            self.mode = self.MENU
            self._render(session)
            return None
        if self.mode == self.OLD:
            if not db.verify_password(session.user, value):
                self.message = "That's not your current password."
                self.message_color = "red"
                self.mode = self.MENU
            else:
                self.mode = self.NEW
                self.editor = LineEditor(masked=True, max_len=64)
        elif self.mode == self.NEW:
            if len(value) < 4:
                self.message = "Password must be at least 4 characters."
                self.message_color = "red"
                self.editor = LineEditor(masked=True, max_len=64)
            else:
                self.new_pw = value
                self.mode = self.CONFIRM
                self.editor = LineEditor(masked=True, max_len=64)
        elif self.mode == self.CONFIRM:
            if value != self.new_pw:
                self.message = "Passwords didn't match."
                self.message_color = "red"
                self.mode = self.MENU
            else:
                db.set_password(session.user["id"], self.new_pw)
                self.message = "Password changed."
                self.message_color = "brgreen"
                self.mode = self.MENU
        self._render(session)
        return None
