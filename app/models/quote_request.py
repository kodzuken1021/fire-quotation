from datetime import date, datetime

from ..db import get_db

STATUSES = ("Pending", "Inspection Scheduled", "Quote Sent", "Cancelled")


class QuoteRequest:
    """One quote request by a client, with the items they selected."""

    def __init__(self, user_id, needs_installation=False, needs_testing=False,
                 wants_inspection=False, notes="", status="Pending", id=None, created_at=None,
                 inspection_address=None, preferred_date=None, inspection_date=None):
        self._id = id
        self._user_id = user_id
        self.needs_installation = bool(needs_installation)
        self.needs_testing = bool(needs_testing)
        self.wants_inspection = bool(wants_inspection)
        self.notes = notes or ""
        self._status = status
        self._created_at = created_at
        self._items = {}                      # item_id -> quantity
        self.inspection_address = inspection_address if self.wants_inspection else None
        self.preferred_date = preferred_date if self.wants_inspection else None
        self._inspection_date = inspection_date if self.wants_inspection else None

    @property
    def id(self): return self._id

    @property
    def user_id(self): return self._user_id

    @property
    def status(self): return self._status

    @property
    def created_at(self): return self._created_at

    @property
    def inspection_date(self): return self._inspection_date

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

    def update_details(self, needs_installation, needs_testing, wants_inspection, notes,
                       inspection_address=None, preferred_date=None):
        if not self.can_be_edited():
            raise ValueError("Only pending requests can be changed.")
        self.needs_installation = bool(needs_installation)
        self.needs_testing = bool(needs_testing)
        self.wants_inspection = bool(wants_inspection)
        self.notes = notes or ""
        self.inspection_address = inspection_address if self.wants_inspection else None
        self.preferred_date = preferred_date if self.wants_inspection else None
        if not self.wants_inspection:
            self._inspection_date = None

    def clear_items(self):
        if not self.can_be_edited():
            raise ValueError("Only pending requests can be changed.")
        self._items = {}

    def item_details(self):
        """List item names, categories and quantities for display."""
        if not self._items:
            return []
        ids = list(self._items)
        placeholders = ",".join(["%s"] * len(ids))
        with get_db().cursor() as cur:
            cur.execute(
                f"SELECT id, name, category FROM catalog_items WHERE id IN ({placeholders}) ORDER BY category, name",
                ids,
            )
            rows = cur.fetchall()
        for row in rows:
            row["quantity"] = self._items[row["id"]]
        return rows

    def schedule_inspection(self, when):
        """Admin sets the free inspection date and the status becomes Inspection Scheduled."""
        if self._id is None:
            raise ValueError("Save the request first.")
        if isinstance(when, datetime):
            when = when.date()
        if not isinstance(when, date):
            raise ValueError("Choose a valid inspection date.")
        if not self.wants_inspection:
            raise ValueError("This request did not ask for an inspection.")
        if self._status not in ("Pending", "Inspection Scheduled"):
            raise ValueError("Only pending or scheduled requests can get an inspection date.")
        if when < date.today():
            raise ValueError("The inspection date cannot be in the past.")
        conn = get_db()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM quote_requests WHERE id = %s FOR UPDATE", (self._id,))
                row = cur.fetchone()
                if row is None or row["status"] not in ("Pending", "Inspection Scheduled"):
                    raise ValueError("This request changed. Reload the page and try again.")
                cur.execute(
                    "UPDATE quote_requests SET inspection_date = %s, status = 'Inspection Scheduled' WHERE id = %s",
                    (when, self._id),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        self._inspection_date = when
        self._status = "Inspection Scheduled"

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
        """Insert or update a pending request and its items atomically."""
        if not self._items:
            raise ValueError("Select at least one item.")
        is_new = self._id is None
        if not is_new and not self.can_be_edited():
            raise ValueError("Only pending requests can be changed.")
        conn = get_db()
        try:
            with conn.cursor() as cur:
                if is_new:
                    cur.execute(
                        "INSERT INTO quote_requests (user_id, status, needs_installation, needs_testing, "
                        "wants_inspection, inspection_address, preferred_inspection_date, notes) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (self._user_id, self._status, int(self.needs_installation), int(self.needs_testing),
                         int(self.wants_inspection), self.inspection_address, self.preferred_date, self.notes),
                    )
                    self._id = cur.lastrowid
                else:
                    cur.execute(
                        "SELECT status FROM quote_requests WHERE id = %s AND user_id = %s FOR UPDATE",
                        (self._id, self._user_id),
                    )
                    row = cur.fetchone()
                    if row is None or row["status"] != "Pending":
                        raise ValueError("Only pending requests can be changed.")
                    cur.execute(
                        "UPDATE quote_requests SET needs_installation=%s, needs_testing=%s, wants_inspection=%s, "
                        "inspection_address=%s, preferred_inspection_date=%s, notes=%s "
                        "WHERE id=%s AND user_id=%s AND status='Pending'",
                        (int(self.needs_installation), int(self.needs_testing), int(self.wants_inspection),
                         self.inspection_address, self.preferred_date, self.notes, self._id, self._user_id),
                    )
                    cur.execute("DELETE FROM quote_request_items WHERE request_id = %s", (self._id,))
                cur.executemany(
                    "INSERT INTO quote_request_items (request_id, item_id, quantity) VALUES (%s, %s, %s)",
                    [(self._id, item_id, qty) for item_id, qty in self._items.items()],
                )
            conn.commit()
        except Exception:
            conn.rollback()
            if is_new:
                self._id = None
            raise
        return self

    @staticmethod
    def _from_row(row):
        req = QuoteRequest(row["user_id"], row["needs_installation"], row["needs_testing"],
                           row["wants_inspection"], row["notes"], row["status"], row["id"], row["created_at"],
                           row.get("inspection_address"), row.get("preferred_inspection_date"),
                           inspection_date=row.get("inspection_date"))
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

    @staticmethod
    def status_counts():
        """{status: number of requests}, for the admin dashboard."""
        counts = {s: 0 for s in STATUSES}
        with get_db().cursor() as cur:
            cur.execute("SELECT status, COUNT(*) AS n FROM quote_requests GROUP BY status")
            for r in cur.fetchall():
                counts[r["status"]] = r["n"]
        return counts

    @staticmethod
    def all_with_clients(status=None):
        """Every request (admin view) as a list of (QuoteRequest, client_info_dict)."""
        sql = ("SELECT r.*, u.full_name AS client_name, u.company_name AS client_company "
               "FROM quote_requests r JOIN users u ON u.id = r.user_id")
        params = []
        if status in STATUSES:
            sql += " WHERE r.status = %s"
            params.append(status)
        sql += " ORDER BY r.created_at DESC, r.id DESC"
        with get_db().cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [(QuoteRequest._from_row(r),
                 {"name": r["client_name"], "company": r["client_company"]}) for r in rows]

    @staticmethod
    def delete_by_id(request_id):
        conn = get_db()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM quote_request_items WHERE request_id = %s", (request_id,))
                cur.execute("DELETE FROM quote_requests WHERE id = %s", (request_id,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise