from logging.config import fileConfig

from alembic import context

from app import models
from app.database import engine

fileConfig(context.config.config_file_name)
target_metadata = models.Base.metadata


def run_migrations() -> None:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations()
