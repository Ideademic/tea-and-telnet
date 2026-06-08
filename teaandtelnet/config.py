"""Runtime configuration, sourced from environment variables."""

import os

DB_PATH = os.environ.get("TT_DB", "teaandtelnet.db")
HOST = os.environ.get("TT_HOST", "0.0.0.0")
PORT = int(os.environ.get("TT_PORT", "2323"))

# Shown under the logo until an admin changes it from Admin Settings.
DEFAULT_BBS_NAME = os.environ.get("TT_BBS_NAME", "A Cozy Corner of the Net")

# Sign-off and "all lines busy" messages. Admins can edit these in Admin
# Settings. The {slots} placeholder is replaced with the online-slot count.
DEFAULT_QUIT_MESSAGE = "Thanks for visiting Tea & Telnet. 73!"
DEFAULT_BUSY_MESSAGE = "Sorry — all {slots} lines are busy right now. Please ring back soon. 73!"

# Logical screen size we draw against. Real terminals are clamped up to this.
COLS = 80
ROWS = 24

# How long the messages backlog kept per chat room (rows in the DB).
CHAT_HISTORY = 200
