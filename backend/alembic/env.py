from logging.config import fileConfig

from alembic import context

from app.database import Base, engine

fileConfig(context.config.config_file_name)
target_metadata = Base.metadata


def run_migrations() -> None:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations()
