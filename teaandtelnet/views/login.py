"""Login / registration flow shown to every fresh connection."""

from .. import branding, db, screen
from ..widgets import CANCEL, SUBMIT, LineEditor
from .base import QUIT, View


class LoginView(View):
    # states
    USER = "user"
    PASS = "pass"
    NEWPASS = "newpass"
    CONFIRM = "confirm"

    def __init__(self):
        self.state = self.USER
        self.editor = LineEditor(max_len=32)
        self.username = ""
        self.first_password = ""
        self.message = "New here? Just pick a name and you'll be signed up."
        self.message_color = "white"

    async def enter(self, session):
        self._render(session)

    def _prompt(self) -> str:
        return {
            self.USER: "Username:",
            self.PASS: "Password:",
            self.NEWPASS: "Choose a password:",
            self.CONFIRM: "Confirm password:",
        }[self.state]

    def _render(self, session):
        w, h = session.width, session.height
        lines = [""]
        lines += branding.header_lines(w)
        lines += [""] * 2

        prompt = self._prompt()
        shown = self.editor.display()
        field = f"{prompt} {shown}"
        lines.append(screen.center(field, w))

        lines += [""] * 2
        lines.append(screen.center(screen.color(self.message, self.message_color), w))

        # pad to full height, footer at the bottom
        while len(lines) < h - 1:
            lines.append("")
        footer = screen.color(" Tea & Telnet ", "brcyan") + screen.DIM + "· Enter to continue · Esc to clear" + screen.RESET
        lines.append(footer)

        # caret sits right after the visible field text, on the field's row
        field_row = 2 + len(branding.header_lines(w)) + 2 + 1
        left = max(0, (w - screen.visible_len(field)) // 2)
        caret_col = left + len(prompt) + 1 + len(shown) + 1
        self.paint(session, lines[:h], cursor=(field_row, caret_col))

    def _set_message(self, text, color="white"):
        self.message = text
        self.message_color = color

    async def handle(self, session, kind, data):
        if kind != "key":
            return None
        key = data
        result = self.editor.handle(key)
        if result is None:
            self._render(session)
            return None

        signal, value = result
        if signal == CANCEL:
            self.editor.text = ""
            self._render(session)
            return None

        # SUBMIT
        value = value.strip() if self.state in (self.USER,) else value
        if self.state == self.USER:
            return self._submit_username(session, value)
        if self.state == self.PASS:
            return self._submit_password(session, value)
        if self.state == self.NEWPASS:
            return self._submit_newpass(session, value)
        if self.state == self.CONFIRM:
            return self._submit_confirm(session, value)
        return None

    # -- steps -------------------------------------------------------------- #
    def _submit_username(self, session, value):
        if not value:
            self._set_message("Please type a username.", "bryellow")
            self._render(session)
            return None
        if len(value) < 2 or not all(c.isalnum() or c in "_-." for c in value):
            self._set_message("Use 2+ letters/digits (._- allowed).", "red")
            self.editor = LineEditor(max_len=32)
            self._render(session)
            return None
        self.username = value
        existing = db.get_user(value)
        self.editor = LineEditor(masked=True, max_len=64)
        if existing:
            self.state = self.PASS
            self._set_message(f"Welcome back, {value}. Enter your password.", "brgreen")
        else:
            self.state = self.NEWPASS
            self._set_message(f"Creating account '{value}'. Pick a password.", "brgreen")
        self._render(session)
        return None

    def _submit_password(self, session, value):
        user = db.get_user(self.username)
        if user and db.verify_password(user, value):
            return self._login(session, user)
        self._set_message("Wrong password. Try again.", "red")
        self.editor = LineEditor(masked=True, max_len=64)
        self._render(session)
        return None

    def _submit_newpass(self, session, value):
        if len(value) < 4:
            self._set_message("Password must be at least 4 characters.", "red")
            self.editor = LineEditor(masked=True, max_len=64)
            self._render(session)
            return None
        self.first_password = value
        self.state = self.CONFIRM
        self.editor = LineEditor(masked=True, max_len=64)
        self._set_message("Type it once more to confirm.", "white")
        self._render(session)
        return None

    def _submit_confirm(self, session, value):
        if value != self.first_password:
            self._set_message("Passwords didn't match. Start over.", "red")
            self.state = self.NEWPASS
            self.first_password = ""
            self.editor = LineEditor(masked=True, max_len=64)
            self._render(session)
            return None
        # Double-check the name wasn't taken while we were typing.
        if db.get_user(self.username):
            self._set_message("That name was just taken. Pick another.", "red")
            self.state = self.USER
            self.editor = LineEditor(max_len=32)
            self._render(session)
            return None
        user = db.create_user(self.username, value)
        return self._login(session, user, fresh=True)

    def _login(self, session, user, fresh=False):
        from .mainmenu import MainMenuView

        session.user = user
        db.touch_user(user["id"])
        session.mainmenu = MainMenuView()
        if fresh and user["is_admin"]:
            session.mainmenu.flash = "You're the first user — you're an admin!"
        return session.mainmenu
