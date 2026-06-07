"""In-memory presence + chat fan-out shared by all live sessions."""

from collections import defaultdict


class Hub:
    def __init__(self):
        self.sessions: set = set()  # all connected sessions
        self.room_members: dict[int, set] = defaultdict(set)  # room_id -> sessions

    # -- connection lifecycle ------------------------------------------------ #
    def connect(self, session) -> None:
        self.sessions.add(session)

    def disconnect(self, session) -> None:
        self.sessions.discard(session)
        for members in self.room_members.values():
            members.discard(session)

    def online_count(self) -> int:
        return sum(1 for s in self.sessions if s.user is not None)

    def connection_count(self) -> int:
        """Live connections (a 'line' is occupied from connect, before login)."""
        return len(self.sessions)

    def online_names(self) -> list[str]:
        return sorted(s.user["username"] for s in self.sessions if s.user is not None)

    # -- chat rooms ---------------------------------------------------------- #
    def join_room(self, room_id: int, session) -> None:
        self.room_members[room_id].add(session)
        self._announce(room_id, f"* {session.user['username']} joined the room", exclude=session)

    def leave_room(self, room_id: int, session) -> None:
        self.room_members[room_id].discard(session)
        self._announce(room_id, f"* {session.user['username']} left the room")

    def members(self, room_id: int) -> list[str]:
        return sorted(s.user["username"] for s in self.room_members.get(room_id, ()))

    def broadcast(self, room_id: int, event: dict) -> None:
        for s in list(self.room_members.get(room_id, ())):
            s.post_event(("chat", event))

    def _announce(self, room_id: int, text: str, exclude=None) -> None:
        for s in list(self.room_members.get(room_id, ())):
            if s is exclude:
                continue
            s.post_event(("chat", {"system": True, "body": text}))


hub = Hub()
