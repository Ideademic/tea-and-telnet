"""Asyncio telnet server that hosts one Session per connection."""

import asyncio
import logging

from . import config, db
from .session import Session

log = logging.getLogger("teaandtelnet")


async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    session = Session(reader, writer)
    peer = session.peer
    log.info("connect %s", peer)
    try:
        await session.run()
    except Exception:  # never let one client take down the server
        log.exception("session error %s", peer)
    finally:
        log.info("disconnect %s", peer)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    db.connect()  # initialise schema + seed data up front
    server = await asyncio.start_server(_handle, config.HOST, config.PORT)
    addrs = ", ".join(str(s.getsockname()) for s in server.sockets)
    log.info("Tea & Telnet listening on %s", addrs)
    async with server:
        await server.serve_forever()


def run() -> None:
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
