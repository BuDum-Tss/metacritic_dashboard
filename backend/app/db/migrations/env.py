from alembic import context

from app.db.models import Base

config = context.config
target_metadata = Base.metadata


def _migrate(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # init_db passes its own connection; the alembic CLI builds one from the settings
    connection = config.attributes.get("connection")
    if connection is not None:
        _migrate(connection)
        return

    from app.config import settings
    from app.db.session import make_engine

    with make_engine(settings.database_path).connect() as connection:
        _migrate(connection)
        connection.commit()


run_migrations_online()
