from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.task_ledger import TaskLedger


class TaskLedgerRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_directive_id(self, directive_id: uuid.UUID) -> TaskLedger | None:
        return self._session.scalar(select(TaskLedger).where(TaskLedger.directive_id == directive_id))
