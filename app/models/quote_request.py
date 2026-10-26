from ..db import get_db

STATUSES = ("Pending", "Inspection Scheduled", "Quote Sent", "Cancelled")


class QuoteRequest:
    """One quote request by a client, with the items they selected."""

    def __init__(self, user_id, needs_installation=False, needs_testing=False,
                 wants_inspection=False, notes="", status="Pending", id=None, created_at=None):
        self._id = id
        self._user_id = user_id
        self.needs_installation = bool(needs_installation)
        self.needs_testing = bool(needs_testing)
        self.wants_inspection = bool(wants_inspection)
        self.notes = notes or ""
        self._status = status
        self._created_at = created_at
        self._items = {}                      # item_id -> quantity

    @property
    def id(self): return self._id

    @property
    def user_id(self): return self._user_id

    @property
    def status(self): return self._status

    @property
    def created_at(self): return self._created_at

    @property
    def items(self):
        """Read-only copy: list of (item_id, quantity)."""
        return list(self._items.items())

    # ---- business rules ----
    def add_item(self, item_id, quantity):
        if not self.can_be_edited():
            raise ValueError("Only pending requests can be changed.")
        quantity = int(quantity)
        if quantity < 1:
            raise ValueError("Quantity must be at least 1.")
        self._items[int(item_id)] = self._items.get(int(item_id), 0) + quantity

    def can_be_edited(self):
        return self._status == "Pending"

    def set_status(self, new_status):
        """Used by the admin side (inspection scheduled, quote sent)."""
        if new_status not in STATUSES:
            raise ValueError("Unknown status.")
        self._status = new_status
        if self._id is not None:
            self._update_status()

    def cancel(self):
        if not self.can_be_edited():
            raise ValueError("Only pending requests can be cancelled.")
        self.set_status("Cancelled")

    # ---- database ----
    def _update_status(self):
        conn = get_db()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE quote_requests SET status = %s WHERE id = %s", (self._status, self._id))
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def save(self):
        """Insert a new request and its items in one transaction (all or nothing)."""
        if self._id is not None:
            raise ValueError("Editing a saved request is built on Day 7.")
        if not self._items:
            raise ValueError("Select at least one item.")
        conn = get_db()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO quote_requests (user_id, status, needs_installation, needs_testing, wants_inspection, notes) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (self._user_id, self._status, int(self.needs_installation), int(self.needs_testing),
                     int(self.wants_inspection), self.notes),
                )
                self._id = cur.lastrowid
                cur.executemany(
                    "INSERT INTO quote_request_items (request_id, item_id, quantity) VALUES (%s, %s, %s)",
                    [(self._id, item_id, qty) for item_id, qty in self._items.items()],
                )
            conn.commit()
        except Exception:
            conn.rollback()
            self._id = None
            raise
        return self

    @staticmethod
    def _from_row(row):
        req = QuoteRequest(row["user_id"], row["needs_installation"], row["needs_testing"],
                           row["wants_inspection"], row["notes"], row["status"], row["id"], row["created_at"])
        with get_db().cursor() as cur:
            cur.execute("SELECT item_id, quantity FROM quote_request_items WHERE request_id = %s", (row["id"],))
            for r in cur.fetchall():
                req._items[r["item_id"]] = r["quantity"]
        return req

    @staticmethod
    def for_user(user_id):
        """A client's own requests, newest first. Always filtered by user_id."""
        with get_db().cursor() as cur:
            cur.execute("SELECT * FROM quote_requests WHERE user_id = %s ORDER BY created_at DESC, id DESC", (user_id,))
            return [QuoteRequest._from_row(r) for r in cur.fetchall()]

    @staticmethod
    def find(request_id, user_id=None):
        """Pass user_id for clients so they can only open their own requests."""
        sql, params = "SELECT * FROM quote_requests WHERE id = %s", [request_id]
        if user_id is not None:
            sql += " AND user_id = %s"
            params.append(user_id)
        with get_db().cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        return QuoteRequest._from_row(row) if row else None
