from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AdapterHealth:
    online: bool
    reason: str
    user_id: str | None = None
    nickname: str | None = None
