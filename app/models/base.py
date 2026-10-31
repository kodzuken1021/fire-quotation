from contextlib import contextmanager

from ..db import get_db


class BaseModel:
    """Shared database behaviour: one place for commit and rollback."""

    @staticmethod
    @contextmanager
    def transaction():
        conn = get_db()
        try:
            with conn.cursor() as cur:
                yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise