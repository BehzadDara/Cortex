from functools import lru_cache

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import settings


def plain_postgres_url() -> str:
    return settings.database_url.replace("+psycopg", "")


def warm_checkpointer() -> None:
    try:
        get_checkpointer()
    except Exception:
        pass


@lru_cache
def get_checkpointer() -> PostgresSaver:
    pool = ConnectionPool(
        plain_postgres_url(),
        max_size=4,
        open=False,
        kwargs={"autocommit": True, "row_factory": dict_row, "prepare_threshold": 0},
    )
    pool.open(wait=True, timeout=10)
    saver = PostgresSaver(pool)
    saver.setup()
    return saver
