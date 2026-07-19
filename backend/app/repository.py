import json
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine, String, Text, DateTime
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .config import settings


class Base(DeclarativeBase): pass
class Run(Base):
    __tablename__="runs"; id: Mapped[str]=mapped_column(String,primary_key=True); disruption: Mapped[str]=mapped_column(Text); results: Mapped[str]=mapped_column(Text); created_at: Mapped[datetime]=mapped_column(DateTime)
if settings.database_url == "sqlite://":
    engine=create_engine(settings.database_url,connect_args={"check_same_thread":False},poolclass=StaticPool)
else:
    engine=create_engine(settings.database_url,connect_args={"check_same_thread":False} if settings.database_url.startswith("sqlite") else {})
Session=sessionmaker(bind=engine)
def initialise_database(): Base.metadata.create_all(engine)
def save_run(run_id: str, disruption: dict, results: dict):
    with Session() as s:
        run=s.get(Run,run_id)
        if run is None:
            s.add(Run(id=run_id,disruption=json.dumps(disruption),results=json.dumps(results),created_at=datetime.now(timezone.utc)))
        else:
            run.disruption=json.dumps(disruption)
            run.results=json.dumps(results)
        s.commit()
def get_run(run_id: str) -> dict | None:
    with Session() as s:
        item=s.get(Run,run_id); return {"disruption":json.loads(item.disruption),"results":json.loads(item.results)} if item else None
def all_runs() -> list[dict]:
    with Session() as s: return [{"id":x.id,"created_at":x.created_at,"results":json.loads(x.results)} for x in s.query(Run).all()]
