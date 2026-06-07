"""A single connected client: I/O plumbing plus the view dispatch loop."""

import asyncio
import logging

from . import db, screen
from .hub import hub
from .telnet import INITIAL_NEGOTIATION, KeyDecoder, TelnetFilter
from .views.base import QUIT

# Imported lazily to avoid a circular import at module load.


class Session:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.events: asyncio.Queue = asyncio.Queue()
        self.width = 80
        self.height = 24
        self.user = None  # sqlite3.Row once logged in
        self.view = None
        self.mainmenu = None  # the shared main-menu instance, set after login
        self.current_room = None  # room_id while inside a chat view
        self.peer = writer.get_extra_info("peername")
        self._filter = TelnetFilter(self._raw_write, self._on_resize)
        self._decoder = KeyDecoder()
        self._esc_timer = None
        self._closed = False

    # -- low level I/O ------------------------------------------------------- #
    def _raw_write(self, data: bytes) -> None:
        if not self._closed:
            self.writer.write(data)

    def write(self, text: str) -> None:
        """Send text to the client, escaping any stray 0xFF as telnet requires."""
        data = text.encode("utf-8", "replace").replace(b"\xff", b"\xff\xff")
        self._raw_write(data)

    def _on_resize(self, cols: int, rows: int) -> None:
        cols = max(80, min(cols, 200))
        rows = max(24, min(rows, 60))
        if (cols, rows) != (self.width, self.height):
            self.width, self.height = cols, rows
            self.post_event(("resize", (cols, rows)))

    def post_event(self, event) -> None:
        """Thread-free way for the hub / timers to wake this session."""
        if not self._closed:
            self.events.put_nowait(event)

    # -- ESC handling: a lone ESC byte is flushed on a short timer ----------- #
    def _schedule_esc_flush(self) -> None:
        if self._decoder.buf == b"\x1b" or self._decoder.buf == bytearray(b"\x1b"):
            if self._esc_timer:
                self._esc_timer.cancel()
            loop = asyncio.get_running_loop()
            self._esc_timer = loop.call_later(0.06, self._flush_esc)

    def _flush_esc(self) -> None:
        if bytes(self._decoder.buf) == b"\x1b":
            self._decoder.buf.clear()
            self.post_event(("key", "ESC"))

    async def _reader_loop(self) -> None:
        try:
            while True:
                data = await self.reader.read(2048)
                if not data:
                    break
                if self._esc_timer:
                    self._esc_timer.cancel()
                    self._esc_timer = None
                app_bytes = self._filter.feed(data)
                for key in self._decoder.feed(app_bytes):
                    self.post_event(("key", key))
                self._schedule_esc_flush()
        except (ConnectionError, asyncio.CancelledError):
            pass
        except Exception:
            logging.getLogger("teaandtelnet").exception("reader loop error")
        finally:
            self.post_event(("eof", None))

    # -- main loop ----------------------------------------------------------- #
    async def run(self) -> None:
        from .views.login import LoginView

        # Enforce the "phone line" cap: if every slot is taken, give the caller
        # a busy signal and hang up before they occupy a line.
        slots = db.max_slots()
        if slots and hub.connection_count() >= slots:
            try:
                self.write(
                    f"\r\n  Sorry — all {slots} lines are busy right now.\r\n"
                    "  Please ring back in a little while. 73!\r\n\r\n"
                )
                await self.writer.drain()
            except Exception:
                pass
            try:
                self.writer.close()
            except Exception:
                pass
            return

        hub.connect(self)
        self._raw_write(INITIAL_NEGOTIATION)
        self.write(screen.CLEAR + screen.HIDE_CURSOR)
        reader_task = asyncio.create_task(self._reader_loop())

        self.view = LoginView()
        try:
            await self.view.enter(self)
            while True:
                kind, data = await self.events.get()
                if kind == "eof":
                    break
                if kind == "resize":
                    await self.view.enter(self)  # repaint at the new size
                    continue
                result = await self.view.handle(self, kind, data)
                if result is QUIT:
                    break
                if result is not None and result is not self.view:
                    await self.view.leave(self)
                    self.view = result
                    await self.view.enter(self)
        except (ConnectionError, asyncio.CancelledError):
            pass
        finally:
            self._closed = True
            if self._esc_timer:
                self._esc_timer.cancel()
            reader_task.cancel()
            if self.current_room is not None:
                hub.leave_room(self.current_room, self)
            hub.disconnect(self)
            try:
                self.write(screen.RESET + screen.SHOW_CURSOR + "\r\n")
                await self.writer.drain()
            except Exception:
                pass
            try:
                self.writer.close()
            except Exception:
                pass
