from contextlib import contextmanager

from ..db import get_db


class BaseModel: #either save or undo
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