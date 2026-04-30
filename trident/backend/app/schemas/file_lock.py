from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class FileLockRecord(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    project_id: uuid.UUID
    directive_id: uuid.UUID
    file_path: str
    locked_by_agent_role: str
    locked_by_user_id: uuid.UUID
    lock_status: str
    created_at: datetime
    expires_at: datetime | None
    released_at: datetime | None
