"""Runtime configuration, sourced from environment variables."""

import os

DB_PATH = os.environ.get("TT_DB", "teaandtelnet.db")
HOST = os.environ.get("TT_HOST", "0.0.0.0")
PORT = int(os.environ.get("TT_PORT", "2323"))

# Shown under the logo until an admin changes it from Admin Settings.
DEFAULT_BBS_NAME = os.environ.get("TT_BBS_NAME", "A Cozy Corner of the Net")

# Logical screen size we draw against. Real terminals are clamped up to this.
COLS = 80
ROWS = 24

# How long the messages backlog kept per chat room (rows in the DB).
CHAT_HISTORY = 200
