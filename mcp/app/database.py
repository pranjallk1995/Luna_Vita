import os
from contextlib import contextmanager

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


DATABASE_URL = os.environ["DATABASE_URL"]
pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=8, open=False)


def open_pool() -> None:
    pool.open(wait=True)


def close_pool() -> None:
    pool.close()


@contextmanager
def connection():
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            yield cursor
