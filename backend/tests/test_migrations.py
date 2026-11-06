from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from app.db.models import Base
from app.db.session import alembic_config, init_db, make_engine


def test_migrations_produce_the_schema_of_the_models(tmp_path):
    engine = make_engine(str(tmp_path / "fresh.db"))
    init_db(engine)
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert diff == []


def test_database_created_before_alembic_is_stamped_and_upgraded(tmp_path):
    engine = make_engine(str(tmp_path / "old.db"))
    with engine.begin() as connection:
        command.upgrade(alembic_config(connection), "0001")  # the schema of the first deployment
        connection.execute(text("DROP TABLE alembic_version"))  # ...which had no Alembic
        connection.execute(
            text(
                "INSERT INTO games (source, slug, url, title, first_seen_at, updated_at, last_processed_at)"
                " VALUES ('metacritic', 'zelda', 'u', 'Zelda', '2026-01-01', '2026-01-01', '2026-01-01')"
            )
        )

    init_db(engine)

    with engine.connect() as connection:
        tables = set(inspect(connection).get_table_names())
        assert {"reviews", "summary_points", "summary_point_reviews", "alembic_version"} <= tables
        assert connection.execute(text("SELECT title FROM games")).scalar() == "Zelda"
        head = ScriptDirectory.from_config(alembic_config(connection)).get_current_head()
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == head


def test_init_db_is_idempotent(tmp_path):
    engine = make_engine(str(tmp_path / "twice.db"))
    init_db(engine)
    init_db(engine)
