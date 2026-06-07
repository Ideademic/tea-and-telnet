"""Minimal telnet protocol handling + keyboard decoding.

We negotiate "character at a time" mode (the server echoes, the client sends
each keystroke immediately) and strip the IAC command stream out of the byte
flow, optionally learning the window size from NAWS.
"""

from typing import Callable, Optional

# Telnet command bytes
IAC = 255
DONT = 254
DO = 253
WONT = 252
WILL = 251
SB = 250
SE = 240

# Options
OPT_ECHO = 1
OPT_SGA = 3  # suppress go-ahead
OPT_NAWS = 31  # negotiate about window size

# Sent right after a client connects to push it into raw character mode.
INITIAL_NEGOTIATION = bytes(
    [
        IAC, WILL, OPT_ECHO,
        IAC, WILL, OPT_SGA,
        IAC, DO, OPT_SGA,
        IAC, DO, OPT_NAWS,
    ]
)


class TelnetFilter:
    """Consumes raw socket bytes, returns application bytes.

    `on_send` is called with bytes that must go back to the client (option
    replies). `on_resize` is called with (cols, rows) when NAWS arrives.
    """

    def __init__(
        self,
        on_send: Callable[[bytes], None],
        on_resize: Optional[Callable[[int, int], None]] = None,
    ):
        self.on_send = on_send
        self.on_resize = on_resize
        self._buf = bytearray()
        self._state = "data"
        self._cmd = 0
        self._sb = bytearray()

    def feed(self, data: bytes) -> bytes:
        out = bytearray()
        for b in data:
            if self._state == "data":
                if b == IAC:
                    self._state = "iac"
                else:
                    out.append(b)
            elif self._state == "iac":
                if b == IAC:  # escaped 0xFF -> literal byte
                    out.append(IAC)
                    self._state = "data"
                elif b in (DO, DONT, WILL, WONT):
                    self._cmd = b
                    self._state = "opt"
                elif b == SB:
                    self._sb.clear()
                    self._state = "sb"
                else:  # standalone command we don't care about
                    self._state = "data"
            elif self._state == "opt":
                self._handle_negotiation(self._cmd, b)
                self._state = "data"
            elif self._state == "sb":
                if b == IAC:
                    self._state = "sb_iac"
                else:
                    self._sb.append(b)
            elif self._state == "sb_iac":
                if b == SE:
                    self._handle_subnegotiation(bytes(self._sb))
                    self._state = "data"
                elif b == IAC:
                    self._sb.append(IAC)
                    self._state = "sb"
                else:
                    self._state = "sb"
        return bytes(out)

    def _handle_negotiation(self, cmd: int, opt: int) -> None:
        # We proactively offered ECHO/SGA and asked for NAWS; politely refuse
        # everything else so clients stop waiting on us.
        if cmd == DO:
            if opt not in (OPT_ECHO, OPT_SGA):
                self.on_send(bytes([IAC, WONT, opt]))
        elif cmd == DONT:
            pass
        elif cmd == WILL:
            if opt not in (OPT_NAWS, OPT_SGA):
                self.on_send(bytes([IAC, DONT, opt]))
        elif cmd == WONT:
            pass

    def _handle_subnegotiation(self, payload: bytes) -> None:
        if payload and payload[0] == OPT_NAWS and len(payload) >= 5:
            cols = (payload[1] << 8) | payload[2]
            rows = (payload[3] << 8) | payload[4]
            if self.on_resize and cols and rows:
                self.on_resize(cols, rows)


# Named keys produced by the decoder. Printable input is returned as the raw
# character string (length 1).
ARROWS = {b"A": "UP", b"B": "DOWN", b"C": "RIGHT", b"D": "LEFT", b"H": "HOME", b"F": "END"}
CTRL = {3: "CTRL_C", 4: "CTRL_D", 14: "CTRL_N", 16: "CTRL_P", 18: "CTRL_R", 24: "CTRL_X"}


class KeyDecoder:
    """Turns a byte stream into a list of key tokens, UTF-8 aware."""

    def __init__(self):
        self.buf = bytearray()

    def feed(self, data: bytes) -> list[str]:
        self.buf.extend(data)
        keys: list[str] = []
        while self.buf:
            b = self.buf[0]
            if b == 0x1B:  # ESC
                if len(self.buf) == 1:
                    break  # wait — session flushes a lone ESC on a timer
                nxt = self.buf[1]
                if nxt in (0x5B, 0x4F):  # '[' or 'O'
                    if len(self.buf) < 3:
                        break
                    final = bytes(self.buf[2:3])  # bytes, so dict lookup works
                    if final in ARROWS:
                        keys.append(ARROWS[final])
                        del self.buf[:3]
                        continue
                    if final == b"3":  # delete: ESC [ 3 ~
                        if len(self.buf) < 4:
                            break
                        del self.buf[:4]
                        keys.append("DELETE")
                        continue
                    del self.buf[:3]  # unknown CSI, drop it
                    continue
                else:
                    keys.append("ESC")
                    del self.buf[:1]
                    continue
            if b in (0x0D, 0x0A):  # CR / LF
                keys.append("ENTER")
                if b == 0x0D and len(self.buf) >= 2 and self.buf[1] in (0x0A, 0x00):
                    del self.buf[:2]
                else:
                    del self.buf[:1]
                continue
            if b in (0x7F, 0x08):
                keys.append("BACKSPACE")
                del self.buf[:1]
                continue
            if b == 0x09:
                keys.append("TAB")
                del self.buf[:1]
                continue
            if b < 0x20:
                if b in CTRL:
                    keys.append(CTRL[b])
                del self.buf[:1]
                continue
            # Printable: decode one (possibly multibyte) UTF-8 char.
            if b < 0x80:
                keys.append(chr(b))
                del self.buf[:1]
                continue
            n = 2 if b < 0xE0 else 3 if b < 0xF0 else 4
            if len(self.buf) < n:
                break
            try:
                keys.append(bytes(self.buf[:n]).decode("utf-8"))
            except UnicodeDecodeError:
                pass
            del self.buf[:n]
        return keys
