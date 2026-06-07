"""A "Table" — a classic BBS sub-board with sequential post numbers and a
per-user read pointer. Read a post and your pointer advances; unread posts are
flagged on the listing.
"""

import textwrap
import time

from .. import db, screen
from ..widgets import CANCEL, SUBMIT, LineEditor, TextArea
from .base import View


class BoardView(View):
    LIST = "list"
    READ = "read"
    SUBJECT = "subject"
    BODY = "body"

    def __init__(self, board_id: int):
        self.board_id = board_id
        self.board = db.get_board(board_id)
        self.mode = self.LIST
        self.sel = 0
        self.reading = None  # post number currently open
        self.subject_editor = None
        self.body_editor = None
        self.draft_subject = ""

    async def enter(self, session):
        self._render(session)

    # -- rendering ----------------------------------------------------------- #
    def _render(self, session):
        if self.board is None:
            self.paint(session, ["This table no longer exists. Press Esc to go back."])
            return
        if self.mode == self.LIST:
            self._render_list(session)
        elif self.mode == self.READ:
            self._render_read(session)
        elif self.mode == self.SUBJECT:
            self._render_subject(session)
        elif self.mode == self.BODY:
            self._render_body(session)

    def _title_bar(self, session):
        w = session.width
        name = self.board["name"]
        title = screen.color(f" ▤ {name} ", "brcyan") + screen.DIM + self.board["description"] + screen.RESET
        return [screen.clip(title, w), screen.color(screen.HZ * w, "white")]

    def _render_list(self, session):
        w, h = session.width, session.height
        posts = db.list_posts(self.board_id)
        last_read = db.get_read_pointer(session.user["id"], self.board_id)
        self.sel = max(0, min(self.sel, max(0, len(posts) - 1)))

        lines = self._title_bar(session)
        body_h = h - len(lines) - 1
        if not posts:
            lines.append("")
            lines.append(screen.center(screen.color("No posts yet. Press P to write the first one.", "bryellow"), w))
        else:
            start = 0
            if len(posts) > body_h:
                start = max(0, min(self.sel - body_h + 1, len(posts) - body_h))
            for i in range(start, min(len(posts), start + body_h)):
                p = posts[i]
                unread = p["number"] > last_read
                flag = screen.color("●", "bryellow") if unread else " "
                date = time.strftime("%b %d", time.localtime(p["created_at"]))
                num = f"{p['number']:>4}"
                subj = screen.clip(p["subject"], w - 28)
                meta = f"{p['username']:<12.12} {date}"
                row = f" {num} {flag} {subj}"
                row = screen.pad(row, w - len(meta) - 2) + screen.DIM + meta + screen.RESET
                if i == self.sel:
                    plain = f" {num} {'●' if unread else ' '} " + screen.clip(p['subject'], w - 28)
                    plain = screen.pad(plain, w - len(meta) - 2) + meta
                    lines.append(screen.REVERSE + screen.pad(plain, w) + screen.RESET)
                else:
                    lines.append(row)

        while len(lines) < h - 1:
            lines.append("")
        unread_total = db.unread_count(session.user["id"], self.board_id)
        footer = (
            screen.DIM
            + f" {len(posts)} posts · {unread_total} unread  ·  ↑↓ select · Enter read · N next unread · P post · Esc back"
            + screen.RESET
        )
        lines.append(footer)
        self.paint(session, lines[:h])

    def _render_read(self, session):
        w, h = session.width, session.height
        post = db.get_post(self.board_id, self.reading)
        if post is None:
            self.mode = self.LIST
            return self._render_list(session)
        date = time.strftime("%b %d, %Y %H:%M", time.localtime(post["created_at"]))
        lines = self._title_bar(session)
        lines.append(screen.color(f" #{post['number']}  {post['subject']}", "brwhite"))
        lines.append(screen.DIM + f" by {post['username']} · {date}" + screen.RESET)
        lines.append(screen.color(screen.HZ * w, "white"))
        for para in post["body"].split("\n"):
            for chunk in (textwrap.wrap(para, width=w - 2) or [""]):
                lines.append(" " + chunk)
        while len(lines) < h - 1:
            lines.append("")
        total = db.post_count(self.board_id)
        footer = (
            screen.DIM
            + f" post {post['number']}/{total}  ·  ←/→ or N/P prev/next · R reply · Esc back to list"
            + screen.RESET
        )
        lines.append(footer)
        self.paint(session, lines[:h])

    def _render_subject(self, session):
        w, h = session.width, session.height
        lines = self._title_bar(session)
        lines.append("")
        verb = "Reply" if self.draft_subject else "New post"
        lines.append(screen.color(f" {verb} on {self.board['name']}", "bryellow"))
        lines.append("")
        field = "Subject: " + self.subject_editor.display()
        lines.append(" " + field)
        while len(lines) < h - 1:
            lines.append("")
        lines.append(screen.DIM + " Enter to continue to the body · Esc to cancel" + screen.RESET)
        caret_col = 1 + len("Subject: ") + len(self.subject_editor.display()) + 1
        self.paint(session, lines[:h], cursor=(len(self._title_bar(session)) + 4, caret_col))

    def _render_body(self, session):
        w, h = session.width, session.height
        lines = self._title_bar(session)
        lines.append(screen.color(f" Subject: {self.draft_subject}", "brwhite"))
        lines.append(screen.color(screen.HZ * w, "white"))
        body_lines = self.body_editor.lines()
        # render with wrapping; track caret at the end
        rendered = []
        for para in body_lines:
            wrapped = textwrap.wrap(para, width=w - 2) if para else [""]
            for chunk in wrapped:
                rendered.append(" " + chunk)
        body_h = h - len(lines) - 1
        tail = rendered[-body_h:] if len(rendered) > body_h else rendered
        lines.extend(tail)
        while len(lines) < h - 1:
            lines.append("")
        lines.append(screen.DIM + " Type your message · Enter for newline · Ctrl-X to post · Esc to cancel" + screen.RESET)
        # caret at end of last rendered line
        last = tail[-1] if tail else " "
        caret_row = min(h - 1, len(self._title_bar(session)) + len(tail))
        caret_col = min(w, screen.visible_len(last) + 1)
        self.paint(session, lines[:h], cursor=(caret_row, caret_col))

    # -- input --------------------------------------------------------------- #
    async def handle(self, session, kind, data):
        if kind != "key":
            return None
        if self.board is None:
            return session.mainmenu if data in ("ESC", "q", "Q") else None
        if self.mode == self.LIST:
            return self._handle_list(session, data)
        if self.mode == self.READ:
            return self._handle_read(session, data)
        if self.mode == self.SUBJECT:
            return self._handle_subject(session, data)
        if self.mode == self.BODY:
            return self._handle_body(session, data)
        return None

    def _handle_list(self, session, key):
        posts = db.list_posts(self.board_id)
        if key in ("ESC", "q", "Q"):
            return session.mainmenu
        if key == "UP":
            self.sel = max(0, self.sel - 1)
        elif key == "DOWN":
            self.sel = min(max(0, len(posts) - 1), self.sel + 1)
        elif key == "ENTER" and posts:
            self.reading = posts[self.sel]["number"]
            db.set_read_pointer(session.user["id"], self.board_id, self.reading)
            self.mode = self.READ
        elif key in ("n", "N"):
            last_read = db.get_read_pointer(session.user["id"], self.board_id)
            nxt = next((p for p in posts if p["number"] > last_read), None)
            if nxt:
                self.reading = nxt["number"]
                db.set_read_pointer(session.user["id"], self.board_id, self.reading)
                self.mode = self.READ
        elif key in ("p", "P"):
            self.draft_subject = ""
            self.subject_editor = LineEditor(max_len=70)
            self.mode = self.SUBJECT
        self._render(session)
        return None

    def _handle_read(self, session, key):
        posts = db.list_posts(self.board_id)
        numbers = [p["number"] for p in posts]
        if key in ("ESC", "BACKSPACE", "q", "Q"):
            self.mode = self.LIST
            if self.reading in numbers:  # keep selection on the post we just read
                self.sel = numbers.index(self.reading)
            self._render(session)
            return None
        if key in ("RIGHT", "n", "N"):
            later = [n for n in numbers if n > self.reading]
            if later:
                self.reading = later[0]
                db.set_read_pointer(session.user["id"], self.board_id, self.reading)
        elif key in ("LEFT", "p", "P"):
            earlier = [n for n in numbers if n < self.reading]
            if earlier:
                self.reading = earlier[-1]
        elif key in ("r", "R"):
            cur = db.get_post(self.board_id, self.reading)
            base = cur["subject"] if cur else ""
            self.draft_subject = base if base.lower().startswith("re:") else f"Re: {base}"
            self.subject_editor = LineEditor(text=self.draft_subject, max_len=70)
            self.mode = self.SUBJECT
        self._render(session)
        return None

    def _handle_subject(self, session, key):
        result = self.subject_editor.handle(key)
        if result is None:
            self._render(session)
            return None
        signal, value = result
        if signal == CANCEL:
            self.mode = self.LIST
            self._render(session)
            return None
        value = value.strip()
        if not value:
            self._render(session)
            return None
        self.draft_subject = value
        self.body_editor = TextArea(max_len=4000)
        self.mode = self.BODY
        self._render(session)
        return None

    def _handle_body(self, session, key):
        result = self.body_editor.handle(key)
        if result is None:
            self._render(session)
            return None
        signal, value = result
        if signal == CANCEL:
            self.mode = self.LIST
            self._render(session)
            return None
        body = value.strip()
        if not body:
            self.mode = self.LIST
            self._render(session)
            return None
        number = db.add_post(self.board_id, session.user["username"], self.draft_subject, body)
        # Reading your own fresh post advances your pointer past it.
        db.set_read_pointer(session.user["id"], self.board_id, number)
        self.mode = self.READ
        self.reading = number
        self._render(session)
        return None
