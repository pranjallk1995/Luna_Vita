import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from psycopg import Cursor
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


@dataclass
class Database:
    """Own the PostgreSQL connection pool used by LunaVita."""

    url: str
    min_size: int = 1
    max_size: int = 8

    def __post_init__(self) -> None:
        self._pool = ConnectionPool(
            self.url,
            min_size=self.min_size,
            max_size=self.max_size,
            open=False,
        )

    @classmethod
    def from_env(cls) -> "Database":
        return cls(os.environ["DATABASE_URL"])

    def open(self) -> None:
        self._pool.open(wait=True)

    def close(self) -> None:
        self._pool.close()

    @contextmanager
    def cursor(self) -> Iterator[Cursor]:
        with self._pool.connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                yield cursor
