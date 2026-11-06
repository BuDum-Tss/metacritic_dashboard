from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event, inspect
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings


def make_engine(path: str) -> Engine:
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path}")

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.close()

    return engine


def alembic_config(connection) -> Config:
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    config.attributes["connection"] = connection
    return config


def init_db(engine: Engine) -> None:
    """Bring the database to the latest schema with Alembic.

    A database created before Alembic (tables but no alembic_version) is first marked as the
    baseline revision 0001, which describes its schema.
    """
    with engine.begin() as connection:
        config = alembic_config(connection)
        tables = set(inspect(connection).get_table_names())
        if "games" in tables and "alembic_version" not in tables:
            command.stamp(config, "0001")
        command.upgrade(config, "head")


engine = make_engine(settings.database_path)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


@contextmanager
def session_scope(factory: sessionmaker | None = None) -> Iterator[Session]:
    """One session per operation: commit on success, rollback on error."""
    session = (factory or SessionLocal)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
