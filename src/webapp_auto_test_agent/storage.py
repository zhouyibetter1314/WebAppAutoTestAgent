from __future__ import annotations

import builtins
import json
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from filelock import FileLock
from sqlalchemy import JSON, Integer, String, create_engine, event, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .config import Settings
from .schemas import Application, Event, Run, Scenario, now


class Base(DeclarativeBase):
    pass


class Record(Base):
    __tablename__ = "records"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String, index=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)


class EventRecord(Base):
    __tablename__ = "events"
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, index=True)
    kind: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)


class Store:
    def __init__(self, settings: Settings) -> None:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.root = settings.data_dir.resolve()
        self.engine = create_engine(
            settings.database_url, connect_args={"check_same_thread": False}
        )

        @event.listens_for(self.engine, "connect")
        def pragmas(connection: Any, _record: Any) -> None:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA busy_timeout=5000")

        with FileLock(str(self.root / "migration.lock")):
            config = Config()
            config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
            config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
            command.upgrade(config, "head")

    def save(self, kind: str, value: Application | Scenario | Run) -> None:
        with Session(self.engine) as session:
            session.merge(Record(id=value.id, kind=kind, data=value.model_dump(mode="json")))
            session.commit()

    def get(self, kind: str, identifier: str) -> dict[str, Any]:
        with Session(self.engine) as session:
            record = session.get(Record, identifier)
            if record is None or record.kind != kind:
                raise KeyError(identifier)
            return dict(record.data)

    def list(self, kind: str) -> list[dict[str, Any]]:
        with Session(self.engine) as session:
            records = session.scalars(select(Record).where(Record.kind == kind)).all()
            return [dict(r.data) for r in records]

    def run(self, identifier: str) -> Run:
        return Run.model_validate(self.get("run", identifier))

    def emit(self, run_id: str, kind: str, data: dict[str, Any]) -> Event:
        # Round-trip rejects non-JSON runtime objects before they reach the database.
        payload = json.loads(json.dumps(data, ensure_ascii=False))
        with Session(self.engine) as session:
            record = EventRecord(run_id=run_id, kind=kind, created_at=now(), data=payload)
            session.add(record)
            session.commit()
            return Event(
                sequence=record.sequence,
                run_id=run_id,
                kind=kind,
                created_at=record.created_at,
                data=payload,
            )

    def events(self, run_id: str, after: int = 0) -> builtins.list[Event]:
        with Session(self.engine) as session:
            rows = session.scalars(
                select(EventRecord)
                .where(EventRecord.run_id == run_id, EventRecord.sequence > after)
                .order_by(EventRecord.sequence)
            )
            return [
                Event(
                    sequence=r.sequence,
                    run_id=r.run_id,
                    kind=r.kind,
                    created_at=r.created_at,
                    data=r.data,
                )
                for r in rows
            ]
