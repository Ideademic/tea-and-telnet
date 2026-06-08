# Tea & Telnet ☕

A cozy mini **BBS** you reach over plain `telnet`. Pick a username and
password, and you land on a three-column home screen you drive with the arrow
keys:

```
                    ╔══════════════════╗
                    ║   TEA & TELNET   ║
                    ╚══════════════════╝
                  ~ A Cozy Corner of the Net ~
 ┌─ Chats ─────────────┐ ┌─ Tables ────────────┐ ┌─ Programs ──────────┐
 │ Lobby               │ │ General         (3) │ │ Settings            │
 │ Tech Talk           │ │ Trade & Barter      │ │ Admin Settings      │
 │ Late Night          │ │ The Archive         │ │                     │
 └─────────────────────┘ └─────────────────────┘ └─────────────────────┘
 sysop [admin]  ·  2/16 online  ·  ↑↓ move  ←→ column  Enter open  Q quit
```

The whole interface is rendered in a single-hue amber/yellow theme.

* **Chats** — realtime chat rooms. Press <kbd>Enter</kbd> on a room to join;
  messages fan out live to everyone inside, with join/leave notices.
* **Tables** — classic BBS sub-boards with **sequential post numbers** and a
  per-user **read pointer**: unread posts are flagged, <kbd>N</kbd> jumps to the
  next unread, and reading advances your pointer. Post and reply in-line.
* **Programs** — **Settings** (change password, who's online, account info) and,
  for admins, **Admin Settings** (rename the BBS, set an online-slot limit, edit
  the quit and busy messages, add/remove chat rooms and tables, and
  promote/demote admins).

An admin can cap the number of simultaneous connections ("phone lines"). When
the BBS is full, extra callers get a busy signal and are hung up; the status bar
shows `n/x online` instead of plain `n online`. Set it to `0` for unlimited.

The **quit message** (shown on sign-off) and the **busy message** (shown when
all lines are full) are admin-editable; use `{slots}` in either to drop in the
configured line count.

The **first account created becomes an admin.** It's built in pure-stdlib
Python — no dependencies — so the container image is tiny.

## Controls

| Key | Action |
| --- | --- |
| <kbd>←</kbd> <kbd>→</kbd> | Move between columns / pages |
| <kbd>↑</kbd> <kbd>↓</kbd> | Move within a list |
| <kbd>Enter</kbd> | Open / send |
| <kbd>Esc</kbd> | Go back |
| <kbd>Ctrl-X</kbd> | Save a post you're writing |
| <kbd>Q</kbd> | Quit (from the home screen) |

> The full block logo shows in terminals at least 97 columns wide; narrower
> terminals (e.g. a standard 80-column `telnet`) automatically get a compact
> `TEA & TELNET` double-line box instead.

## Run it with Docker

The image listens on **2323** inside the container. Map it to the classic
telnet port **23** on your host.

```bash
docker run -d --name tea-and-telnet \
  -p 23:2323 \
  -v tea_data:/data \
  ghcr.io/ideademic/tea-and-telnet:latest

telnet your-server 23
```

Or with the provided `docker-compose.yml` (already points at your image):

```bash
docker compose up -d
```

All state (users, posts, chat history) lives in the `/data` volume, so it
survives restarts and upgrades.

### Configuration

| Env var | Default | Meaning |
| --- | --- | --- |
| `TT_PORT` | `2323` | Port to listen on inside the container |
| `TT_HOST` | `0.0.0.0` | Bind address |
| `TT_DB` | `/data/teaandtelnet.db` | SQLite database path |
| `TT_BBS_NAME` | `A Cozy Corner of the Net` | Initial name under the logo (an admin can change it live) |

## Publishing to GitHub Container Registry (ghcr.io)

A workflow at `.github/workflows/docker-publish.yml` builds and pushes the image
automatically on every push to `main` (and on `v*` tags). Just push the repo:

```bash
git init && git add . && git commit -m "Tea & Telnet"
git branch -M main
git remote add origin https://github.com/Ideademic/tea-and-telnet.git
git push -u origin main
```

Then make the package public (GitHub → the **Ideademic** org → Packages →
`tea-and-telnet` → Package settings → Change visibility) so your Debian box can
pull it without logging in.

### Or build & push by hand

```bash
echo "$GITHUB_TOKEN" | docker login ghcr.io -u Ideademic --password-stdin
docker build -t ghcr.io/ideademic/tea-and-telnet:latest .
docker push ghcr.io/ideademic/tea-and-telnet:latest
```

## Pull and run on Debian

```bash
sudo apt-get install -y telnet            # the client, if you don't have it
docker pull ghcr.io/ideademic/tea-and-telnet:latest
docker run -d --name tea-and-telnet --restart unless-stopped \
  -p 23:2323 -v tea_data:/data \
  ghcr.io/ideademic/tea-and-telnet:latest

telnet localhost            # connect locally, or `telnet <host>` from elsewhere
```

## Run locally without Docker

```bash
python3 -m teaandtelnet      # listens on 2323; set TT_PORT/TT_DB to taste
telnet localhost 2323
```

## How it works

| File | Role |
| --- | --- |
| `teaandtelnet/server.py` | asyncio telnet server, one `Session` per connection |
| `teaandtelnet/telnet.py` | IAC negotiation (char-at-a-time mode) + keyboard decoding |
| `teaandtelnet/session.py` | I/O plumbing and the view event loop |
| `teaandtelnet/screen.py` | ANSI colours, boxes, panels, full-screen painting |
| `teaandtelnet/db.py` | SQLite: users, settings, rooms, boards, posts, read pointers |
| `teaandtelnet/hub.py` | in-memory presence + chat fan-out |
| `teaandtelnet/views/` | login, the three-column main menu, chat, tables, settings, admin |

Passwords are stored as salted PBKDF2-SHA256 hashes. Telnet is, of course,
**unencrypted** — fine for a hobby BBS on a trusted network. For exposure to the
wider internet, put it behind a VPN or an SSH/`stunnel` front end.

## License

Tea & Telnet is licensed under the **GNU Affero General Public License v3.0**
(AGPL-3.0) — see [`LICENSE`](LICENSE). Because it's network-facing software, the
AGPL's key point applies: if you run a modified version and let other people
connect to it, you must offer those users the corresponding source of your
modified version.
