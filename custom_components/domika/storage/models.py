"""Storage models."""
from dataclasses import dataclass
from datetime import datetime


@dataclass
class AppSession:
    id: str
    user_id: str
    push_session_id: str
    last_update: datetime
    push_token_hash: str

    @staticmethod
    def init_from_dict(app_session_id: str, d: dict):
        return AppSession(
            id=app_session_id,
            user_id=d.get("user_id"),
            push_session_id=d.get("push_session_id"),
            last_update=d.get("last_update"),
            push_token_hash=d.get("push_token_hash")
        )


@dataclass
class Subscription:
    entity_id: str
    attribute: str
    need_push: bool