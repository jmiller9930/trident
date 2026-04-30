"""Facade for memory reader/writer (100D)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.config.settings import Settings

from app.memory.memory_reader import MemoryReader
from app.memory.memory_writer import MemoryWriter


class MemoryService:
    def __init__(self, session: Session, cfg: Settings | None = None) -> None:
        self.session = session
        self.cfg = cfg
        self.reader = MemoryReader(session, cfg)
        self.writer = MemoryWriter(session, cfg)
