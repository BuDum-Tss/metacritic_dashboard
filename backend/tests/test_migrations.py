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


def test_games_without_a_release_date_become_due_and_the_rest_keep_their_schedule(tmp_path):
    engine = make_engine(str(tmp_path / "recheck.db"))
    later = "2026-11-08 00:00:00"
    insert = (
        "INSERT INTO games (source, slug, url, title, first_seen_at, updated_at, last_processed_at, next_check_at, release_date)"
        " VALUES ('metacritic', :slug, 'u', :slug, '2026-11-06', '2026-11-06', '2026-11-06', :due, :release)"
    )
    with engine.begin() as connection:
        config = alembic_config(connection)
        command.upgrade(config, "0008")
        connection.execute(text(insert), {"slug": "undated", "due": later, "release": None})
        connection.execute(text(insert), {"slug": "dated", "due": later, "release": "2026-11-05"})

        command.upgrade(config, "0009")

        due = dict(connection.execute(text("SELECT slug, next_check_at FROM games")).all())
    assert due["undated"].startswith("1970-01-01")  # the most overdue: visited first
    assert due["dated"] == later  # untouched


def test_games_with_several_platforms_are_queued_for_a_new_analysis(tmp_path):
    engine = make_engine(str(tmp_path / "reanalyze.db"))
    checked = "2026-11-07 02:00:00"
    game = (
        "INSERT INTO games (id, source, slug, url, title, first_seen_at, updated_at, last_processed_at, next_check_at)"
        " VALUES (:id, 'metacritic', :slug, 'u', :slug, '2026-11-06', '2026-11-06', '2026-11-06', '2026-11-08')"
    )
    platform = "INSERT INTO game_platforms (game_id, platform, name, updated_at) VALUES (:id, :platform, :platform, '2026-11-06')"
    state = "INSERT INTO analysis_state (game_id, kind, checked_at, total_reviews) VALUES (:id, :kind, :checked, 12)"
    with engine.begin() as connection:
        config = alembic_config(connection)
        command.upgrade(config, "0009")
        for game_id, slug, platforms in ((1, "multi", ["pc", "ps5"]), (2, "single", ["pc"])):
            connection.execute(text(game), {"id": game_id, "slug": slug})
            for name in platforms:
                connection.execute(text(platform), {"id": game_id, "platform": name})
            for kind in ("critics", "users"):
                connection.execute(text(state), {"id": game_id, "kind": kind, "checked": checked})

        command.upgrade(config, "0010")

        rows = connection.execute(text("SELECT game_id, kind, checked_at, total_reviews FROM analysis_state")).all()
    by_game = {game_id: (str(at), total) for game_id, _, at, total in rows}
    assert by_game[1][0].startswith("1970-01-01") and by_game[1][1] == -1  # both kinds of the multi-platform game
    assert sum(1 for game_id, *_ in rows if game_id == 1) == 2
    assert by_game[2] == (checked, 12)  # one platform: the same reviews as before, untouched
