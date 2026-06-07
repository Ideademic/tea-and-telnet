"""Small in-view input helpers used by the views.

They are plain state machines (not views): a view feeds key tokens in and
checks the returned signal. This keeps the session event loop simple.
"""

SUBMIT = "submit"
CANCEL = "cancel"


class LineEditor:
    """Single-line text entry with optional masking."""

    def __init__(self, text: str = "", masked: bool = False, max_len: int = 200):
        self.text = text
        self.masked = masked
        self.max_len = max_len

    def handle(self, key: str):
        if key == "ENTER":
            return (SUBMIT, self.text)
        if key == "ESC" or key == "CTRL_C":
            return (CANCEL, None)
        if key == "BACKSPACE":
            self.text = self.text[:-1]
            return None
        if len(key) == 1 and key >= " " and len(self.text) < self.max_len:
            self.text += key
        return None

    def display(self) -> str:
        return "*" * len(self.text) if self.masked else self.text


class TextArea:
    """Multi-line editor. Enter inserts a newline; Ctrl-X saves; Esc cancels."""

    def __init__(self, text: str = "", max_len: int = 4000):
        self.text = text
        self.max_len = max_len

    def handle(self, key: str):
        if key == "CTRL_X":
            return (SUBMIT, self.text)
        if key == "ESC" or key == "CTRL_C":
            return (CANCEL, None)
        if key == "ENTER":
            if len(self.text) < self.max_len:
                self.text += "\n"
            return None
        if key == "BACKSPACE":
            self.text = self.text[:-1]
            return None
        if len(key) == 1 and key >= " " and len(self.text) < self.max_len:
            self.text += key
        return None

    def lines(self) -> list[str]:
        return self.text.split("\n")
