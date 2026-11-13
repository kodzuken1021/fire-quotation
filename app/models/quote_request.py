import math

from ..db import get_db
from .base import BaseModel
from .inspection import Inspection


STATUSES = ("Pending", "Inspection Scheduled", "Quote Sent", "Accepted", "Declined", "Cancelled")

# Manual admin changes are deliberately limited. Inspection Scheduled is set by
# schedule_inspection(), and Quote Sent is set only after the email is sent.
ADMIN_STATUS_TRANSITIONS = {
    "Pending": ("Cancelled",),
    "Inspection Scheduled": ("Cancelled",),
    "Quote Sent": (),
    "Accepted": (),
    "Declined": (),
    "Cancelled": (),
}


class QuoteRequest(BaseModel):
    """One quote request by a client, with the items they selected."""

    def __init__(self, user_id, needs_installation=False, needs_testing=False,
                 wants_inspection=False, notes="", status="Pending", id=None, created_at=None,
                 inspection_address=None, preferred_date=None, inspection_date=None):
        self._id = id
        self._user_id = user_id
        self.needs_installation = bool(needs_installation)
        self.needs_testing = bool(needs_testing)
        self.notes = notes or ""
        self._status = status
        self._created_at = created_at
        self._items = {}                      # item_id -> quantity
        # A request that asked for a free inspection owns one Inspection object (composition).
        self._inspection = (Inspection(inspection_address, preferred_date, inspection_date)
                            if wants_inspection else None)

    @property
    def id(self): return self._id

    @property
    def user_id(self): return self._user_id

    @property
    def status(self): return self._status

    @property
    def created_at(self): return self._created_at

    @property
    def inspection(self): return self._inspection

    @property
    def wants_inspection(self): return self._inspection is not None

    # Read-through shortcuts so templates and emails can keep using req.inspection_address etc.
    @property
    def inspection_address(self): return self._inspection.site_address if self._inspection else None

    @property
    def preferred_date(self): return self._inspection.preferred_date if self._inspection else None

    @property
    def inspection_date(self): return self._inspection.scheduled_date if self._inspection else None

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

    def admin_status_options(self):
        """Statuses the admin may select directly from the current state."""
        return ADMIN_STATUS_TRANSITIONS.get(self._status, ())

    def admin_set_status(self, new_status):
        """Apply a manual admin status change without bypassing the workflow."""
        if new_status == "Quote Sent":
            raise ValueError("Quote Sent is set automatically when you email the quotation.")
        if new_status == "Inspection Scheduled":
            raise ValueError("Use the inspection form to choose a date and email the client.")
        if new_status not in self.admin_status_options():
            raise ValueError("That status change is not allowed for this request.")
        if self._id is None:
            raise ValueError("Save the request first.")
        self._status = new_status
        self._update_status()

    def cancel(self):
        if not self.can_be_edited():
            raise ValueError("Only pending requests can be cancelled.")
        self.set_status("Cancelled")

    def respond_to_quote(self, accepted):
        """Client accepts or declines a sent quotation. Only valid while Quote Sent."""
        if self._id is None:
            raise ValueError("Save the request first.")
        new_status = "Accepted" if accepted else "Declined"
        with self.transaction() as cur:
            cur.execute(
                "UPDATE quote_requests SET status = %s WHERE id = %s AND user_id = %s AND status = 'Quote Sent'",
                (new_status, self._id, self._user_id))
            if cur.rowcount != 1:
                raise ValueError("This quotation can no longer be answered.")
        self._status = new_status

    def update_details(self, needs_installation, needs_testing, wants_inspection, notes,
                       inspection_address=None, preferred_date=None):
        if not self.can_be_edited():
            raise ValueError("Only pending requests can be changed.")
        self.needs_installation = bool(needs_installation)
        self.needs_testing = bool(needs_testing)
        self.notes = notes or ""
        if not wants_inspection:
            self._inspection = None           # save() deletes the saved inspection row
        elif self._inspection is None:
            self._inspection = Inspection(inspection_address, preferred_date)
        else:
            self._inspection.change_details(inspection_address, preferred_date)

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
        if self._inspection is None:
            raise ValueError("This request did not ask for an inspection.")
        if self._status not in ("Pending", "Inspection Scheduled"):
            raise ValueError("Only pending or scheduled requests can get an inspection date.")
        self._inspection.schedule(when)       # the Inspection checks the date itself
        with self.transaction() as cur:
            cur.execute("SELECT status FROM quote_requests WHERE id = %s FOR UPDATE", (self._id,))
            row = cur.fetchone()
            if row is None or row["status"] not in ("Pending", "Inspection Scheduled"):
                raise ValueError("This request changed. Reload the page and try again.")
            self._inspection.persist(cur, self._id)
            cur.execute("UPDATE quote_requests SET status = 'Inspection Scheduled' WHERE id = %s", (self._id,))
        self._status = "Inspection Scheduled"

    # ---- database ----
    def _update_status(self):
        with self.transaction() as cur:
            cur.execute("UPDATE quote_requests SET status = %s WHERE id = %s", (self._status, self._id))

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
                        "INSERT INTO quote_requests (user_id, status, needs_installation, needs_testing, notes) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (self._user_id, self._status, int(self.needs_installation), int(self.needs_testing),
                         self.notes),
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
                        "UPDATE quote_requests SET needs_installation=%s, needs_testing=%s, notes=%s "
                        "WHERE id=%s AND user_id=%s AND status='Pending'",
                        (int(self.needs_installation), int(self.needs_testing), self.notes,
                         self._id, self._user_id),
                    )
                    cur.execute("DELETE FROM quote_request_items WHERE request_id = %s", (self._id,))
                    cur.execute("DELETE FROM quotations WHERE request_id = %s", (self._id,))   # edited request: old draft quote is void
                cur.executemany(
                    "INSERT INTO quote_request_items (request_id, item_id, quantity) VALUES (%s, %s, %s)",
                    [(self._id, item_id, qty) for item_id, qty in self._items.items()],
                )
                if self._inspection is not None:
                    self._inspection.persist(cur, self._id)
                else:
                    cur.execute("DELETE FROM inspections WHERE request_id = %s", (self._id,))
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
                           False, row["notes"], row["status"], row["id"], row["created_at"])
        with get_db().cursor() as cur:
            cur.execute("SELECT item_id, quantity FROM quote_request_items WHERE request_id = %s", (row["id"],))
            for r in cur.fetchall():
                req._items[r["item_id"]] = r["quantity"]
            cur.execute("SELECT site_address, preferred_date, scheduled_date FROM inspections "
                        "WHERE request_id = %s", (row["id"],))
            inspection_row = cur.fetchone()
        if inspection_row:
            req._inspection = Inspection.from_row(inspection_row)
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
    def calendar_events(start, end):
        """Inspection events from start to end (inclusive) for the admin calendar.
        Uses the confirmed date if set, otherwise the client's preferred date."""
        sql = (
            "SELECT r.id, r.status, i.site_address AS inspection_address, "
            "COALESCE(i.scheduled_date, i.preferred_date) AS day, "
            "(i.scheduled_date IS NOT NULL) AS confirmed, "
            "u.full_name, u.company_name "
            "FROM quote_requests r "
            "JOIN inspections i ON i.request_id = r.id "
            "JOIN users u ON u.id = r.user_id "
            "WHERE ("
            "  (i.scheduled_date IS NOT NULL AND r.status IN ('Inspection Scheduled', 'Quote Sent', 'Accepted')) "
            "  OR (i.scheduled_date IS NULL AND r.status = 'Pending')) "
            "AND COALESCE(i.scheduled_date, i.preferred_date) BETWEEN %s AND %s "
            "ORDER BY day, r.id"
        )
        with get_db().cursor() as cur:
            cur.execute(sql, (start, end))
            return cur.fetchall()
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
    def search_with_clients(status=None, q=None, page=1, per_page=10):
        """Admin list with optional status filter and search (client name, company, request no.).
        Returns (rows, total, page, pages); rows is a list of (QuoteRequest, client_info_dict)."""
        where, params = [], []
        if status in STATUSES:
            where.append("r.status = %s")
            params.append(status)
        if q:
            like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            clause = "(u.full_name LIKE %s OR u.company_name LIKE %s"
            params += [like, like]
            num = q.lstrip("#").strip()
            if num.isascii() and num.isdigit() and len(num) <= 9:
                clause += " OR r.id = %s"
                params.append(int(num))
            where.append(clause + ")")

        base = " FROM quote_requests r JOIN users u ON u.id = r.user_id"
        if where:
            base += " WHERE " + " AND ".join(where)

        with get_db().cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n" + base, params)
            total = cur.fetchone()["n"]
            pages = max(1, math.ceil(total / per_page))
            page = min(max(page, 1), pages)          # clamp out-of-range pages
            cur.execute(
                "SELECT r.*, u.full_name AS client_name, u.company_name AS client_company" + base +
                " ORDER BY r.created_at DESC, r.id DESC LIMIT %s OFFSET %s",
                params + [per_page, (page - 1) * per_page])
            rows = cur.fetchall()
        return ([(QuoteRequest._from_row(r),
                  {"name": r["client_name"], "company": r["client_company"]}) for r in rows],
                total, page, pages)
    
    @staticmethod
    def delete_by_id(request_id):
        with BaseModel.transaction() as cur:
            cur.execute("DELETE FROM quote_request_items WHERE request_id = %s", (request_id,))
            cur.execute("DELETE FROM quote_requests WHERE id = %s", (request_id,))