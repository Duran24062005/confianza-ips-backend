import json
from typing import Any

from sqlalchemy.orm import Session

from .models import AuditEvent, User


def record_audit(
    db: Session,
    actor: User | None,
    action: str,
    resource_type: str,
    resource_id: int | str,
    before: Any = None,
    after: Any = None,
    metadata: Any = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_user_id=actor.id if actor else None,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        before_json=json.dumps(before, default=str, ensure_ascii=False)
        if before is not None
        else None,
        after_json=json.dumps(after, default=str, ensure_ascii=False)
        if after is not None
        else None,
        metadata_json=json.dumps(metadata, default=str, ensure_ascii=False)
        if metadata is not None
        else None,
    )
    db.add(event)
    return event
