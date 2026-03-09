import psycopg2
import psycopg2.extras
from src.config import DATABASE_URL


class _Connection:
    """
    Thin wrapper over psycopg2 that exposes the same .execute() interface
    as sqlite3.Connection, so models don't need big changes.
    Rows are RealDictRow objects: accessed as row["field"].
    """

    def __init__(self, conn: psycopg2.extensions.connection):
        self._conn = conn

    def execute(self, sql: str, params=None):
        cur = self._conn.cursor()
        cur.execute(sql, params or ())
        return cur

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def get_connection() -> _Connection:
    conn = psycopg2.connect(
        DATABASE_URL,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )
    return _Connection(conn)


def init_db():
    """No-op: schema is managed by migrate.py at container startup."""
    pass
