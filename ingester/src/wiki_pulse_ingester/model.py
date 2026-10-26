from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class RecentChange:
    event_time: datetime
    wiki: str
    server_name: str
    type: str
    namespace: int
    title: str
    user: str
    is_bot: bool
    is_minor: bool
    length_old: int
    length_new: int
    rev_id: int
    comment: str

    @classmethod
    def from_event(cls, event: dict[str, Any]) -> RecentChange:
        length = event.get("length") or {}
        revision = event.get("revision") or {}
        return cls(
            event_time=datetime.fromisoformat(event["meta"]["dt"]),
            wiki=event.get("wiki") or "",
            server_name=event.get("server_name") or "",
            type=event.get("type") or "",
            namespace=event.get("namespace") or 0,
            title=event.get("title") or "",
            user=event.get("user") or "",
            is_bot=bool(event.get("bot")),
            is_minor=bool(event.get("minor")),
            length_old=length.get("old") or 0,
            length_new=length.get("new") or 0,
            rev_id=revision.get("new") or 0,
            comment=event.get("comment") or "",
        )


COLUMNS = [field.name for field in fields(RecentChange)]
