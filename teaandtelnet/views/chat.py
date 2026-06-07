"""A realtime chat room. Messages fan out to everyone in the room via the hub."""

import textwrap
import time

from .. import db, screen
from ..hub import hub
from ..widgets import CANCEL, SUBMIT, LineEditor
from .base import View


class ChatView(View):
    def __init__(self, room_id: int):
        self.room_id = room_id
        self.room = db.get_room(room_id)
        self.messages: list[dict] = []
        self.editor = LineEditor(max_len=400)

    async def enter(self, session):
        if self.room is None:
            self._render(session)  # show "room gone"; Esc returns to the menu
            return
        # Load history the first time we enter (not on resize repaints).
        if not self.messages:
            for m in db.recent_messages(self.room_id):
                self.messages.append(
                    {"username": m["username"], "body": m["body"],
                     "created_at": m["created_at"], "system": False}
                )
        if session.current_room != self.room_id:
            session.current_room = self.room_id
            hub.join_room(self.room_id, session)
        self._render(session)

    async def leave(self, session):
        if session.current_room == self.room_id:
            hub.leave_room(self.room_id, session)
            session.current_room = None

    def _fmt_message(self, m: dict, width: int) -> list[str]:
        if m.get("system"):
            return [screen.color(screen.clip(m["body"], width), "blue")]
        ts = time.strftime("%H:%M", time.localtime(m["created_at"]))
        prefix = f"[{ts}] <{m['username']}> "
        wrapped = textwrap.wrap(m["body"], width=max(10, width - len(prefix))) or [""]
        out = []
        for i, chunk in enumerate(wrapped):
            if i == 0:
                head = screen.DIM + f"[{ts}] " + screen.RESET + screen.color(f"<{m['username']}> ", "brgreen")
                out.append(head + chunk)
            else:
                out.append(" " * len(prefix) + chunk)
        return out

    def _render(self, session):
        w, h = session.width, session.height
        if self.room is None:
            self.paint(session, ["This room no longer exists. Press Esc to go back."])
            return

        members = hub.members(self.room_id)
        name = f" # {self.room['name']}"
        topic = f"  {self.room['topic']}" if self.room["topic"] else ""
        who = f"  ·  {len(members)} here: " + ", ".join(members)
        # Truncate the member list (only) so the whole header fits the width.
        budget = w - len(name) - len(topic)
        who = who[:budget] if len(who) > budget else who
        header = (
            screen.color(name, "brcyan")
            + screen.DIM + topic + screen.RESET
            + screen.color(who, "bryellow")
        )
        lines = [header, screen.color(screen.HZ * w, "white")]

        msg_h = h - 4  # 2 header + 2 input/footer
        rendered: list[str] = []
        for m in self.messages:
            rendered.extend(self._fmt_message(m, w))
        tail = rendered[-msg_h:] if len(rendered) > msg_h else rendered
        lines.extend(tail)
        while len(lines) < 2 + msg_h:
            lines.append("")

        lines.append(screen.color(screen.HZ * w, "white"))
        prompt = screen.color("say> ", "brgreen")
        typed = self.editor.display()
        lines.append(prompt + screen.clip(typed, w - 6))

        caret_col = 5 + 1 + min(len(typed), w - 6)  # after "say> " (5) + typed
        self.paint(session, lines[:h], cursor=(h, caret_col))

    async def handle(self, session, kind, data):
        if kind == "chat":
            self.messages.append(data)
            if len(self.messages) > 500:
                self.messages = self.messages[-400:]
            self._render(session)
            return None

        key = data
        if self.room is None:
            if key in ("ESC", "q", "Q"):
                return session.mainmenu
            return None

        result = self.editor.handle(key)
        if result is None:
            self._render(session)
            return None
        signal, value = result
        if signal == CANCEL:
            return session.mainmenu
        # SUBMIT
        value = value.strip()
        if value:
            row = db.add_message(self.room_id, session.user["username"], value)
            event = {"username": row["username"], "body": row["body"],
                     "created_at": row["created_at"], "system": False}
            hub.broadcast(self.room_id, event)
        self.editor = LineEditor(max_len=400)
        # broadcast already pushed the event to us; if alone, render anyway
        self._render(session)
        return None
