from datetime import date
from decimal import Decimal

from ..db import get_db

QUOTABLE = ("Pending", "Inspection Scheduled")
MAX_AMOUNT = Decimal("9999999.99")


def _money(value, label):
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except Exception:
        raise ValueError(f"{label} must be a valid amount.")
    if not 0 <= amount <= MAX_AMOUNT:
        raise ValueError(f"{label} must be between 0 and 9,999,999.99.")
    return amount


class Quotation:
    """The admin's priced quotation for one request (at most one per request)."""

    def __init__(self, request_id, valid_until=None, installation_charge=0, testing_charge=0,
                 id=None, quotation_no=None, sent_at=None, pdf_path=None):
        self._id = id
        self._request_id = request_id
        self._quotation_no = quotation_no
        self._sent_at = sent_at
        self._pdf_path = pdf_path
        self._lines = []                       # dicts: item_id, quantity, unit_price, line_total
        self.valid_until = valid_until
        self.installation_charge = installation_charge   # validated by the setters below
        self.testing_charge = testing_charge

    @property
    def id(self): return self._id

    @property
    def request_id(self): return self._request_id

    @property
    def quotation_no(self): return self._quotation_no

    @property
    def sent_at(self): return self._sent_at

    @property
    def pdf_path(self): return self._pdf_path

    @property
    def installation_charge(self): return self._installation_charge

    @installation_charge.setter
    def installation_charge(self, value):
        self._installation_charge = _money(value, "Installation charge")

    @property
    def testing_charge(self): return self._testing_charge

    @testing_charge.setter
    def testing_charge(self, value):
        self._testing_charge = _money(value, "Testing charge")

    @property
    def lines(self):
        return [dict(line) for line in self._lines]

    @property
    def total(self):
        return sum((l["line_total"] for l in self._lines), Decimal("0")) \
            + self._installation_charge + self._testing_charge

    # ---- business rules ----
    def add_line(self, item_id, quantity, unit_price):
        quantity = int(quantity)
        if quantity < 1:
            raise ValueError("Quantity must be at least 1.")
        price = _money(unit_price, "Unit price")
        self._lines.append({"item_id": int(item_id), "quantity": quantity,
                            "unit_price": price, "line_total": price * quantity})

    def line_details(self):
        """Saved lines with item names, for the PDF (Day 12) and the client view."""
        if self._id is None:
            return []
        with get_db().cursor() as cur:
            cur.execute(
                "SELECT i.name, i.category, qi.item_id, qi.quantity, qi.unit_price, qi.line_total "
                "FROM quotation_items qi JOIN catalog_items i ON i.id = qi.item_id "
                "WHERE qi.quotation_id = %s ORDER BY i.category, i.name", (self._id,))
            return cur.fetchall()

    # ---- database ----
    def save(self):
        """Create or replace the quotation and its lines in one transaction."""
        if not self._lines:
            raise ValueError("Add a price for at least one item.")
        if self.total > Decimal("9999999999.99"):
            raise ValueError("The total is too large.")
        conn = get_db()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM quote_requests WHERE id = %s FOR UPDATE", (self._request_id,))
                row = cur.fetchone()
                if row is None or row["status"] not in QUOTABLE:
                    raise ValueError("Only pending or scheduled requests can be quoted.")
                cur.execute("SELECT id, quotation_no, sent_at FROM quotations WHERE request_id = %s FOR UPDATE",
                            (self._request_id,))
                existing = cur.fetchone()
                if existing and existing["sent_at"]:
                    raise ValueError("This quotation was already sent.")
                if existing:
                    self._id, self._quotation_no = existing["id"], existing["quotation_no"]
                    cur.execute(
                        "UPDATE quotations SET installation_charge=%s, testing_charge=%s, "
                        "total_amount=%s, valid_until=%s WHERE id=%s",
                        (self._installation_charge, self._testing_charge, self.total,
                         self.valid_until, self._id))
                    cur.execute("DELETE FROM quotation_items WHERE quotation_id = %s", (self._id,))
                else:
                    self._quotation_no = f"QT-{date.today().year}-{self._request_id:05d}"
                    cur.execute(
                        "INSERT INTO quotations (request_id, quotation_no, installation_charge, "
                        "testing_charge, total_amount, valid_until) VALUES (%s,%s,%s,%s,%s,%s)",
                        (self._request_id, self._quotation_no, self._installation_charge,
                         self._testing_charge, self.total, self.valid_until))
                    self._id = cur.lastrowid
                cur.executemany(
                    "INSERT INTO quotation_items (quotation_id, item_id, quantity, unit_price, line_total) "
                    "VALUES (%s,%s,%s,%s,%s)",
                    [(self._id, l["item_id"], l["quantity"], l["unit_price"], l["line_total"])
                     for l in self._lines])
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return self

    @staticmethod
    def find_by_request(request_id):
        with get_db().cursor() as cur:
            cur.execute("SELECT * FROM quotations WHERE request_id = %s", (request_id,))
            row = cur.fetchone()
            if row is None:
                return None
            q = Quotation(row["request_id"], row["valid_until"], row["installation_charge"],
                          row["testing_charge"], row["id"], row["quotation_no"],
                          row["sent_at"], row["pdf_path"])
            cur.execute("SELECT item_id, quantity, unit_price, line_total FROM quotation_items "
                        "WHERE quotation_id = %s", (row["id"],))
            q._lines = list(cur.fetchall())
        return q
# --- PDF Quotation
    def mark_sent(self, pdf_filename):
        """Called only after the email went out: record the PDF and set the request to Quote Sent."""
        conn = get_db()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE quotations SET pdf_path=%s, sent_at=NOW() "
                            "WHERE id=%s AND sent_at IS NULL", (pdf_filename, self._id))
                if cur.rowcount != 1:
                    raise ValueError("This quotation was already sent.")
                cur.execute("UPDATE quote_requests SET status='Quote Sent' "
                            "WHERE id=%s AND status IN ('Pending','Inspection Scheduled')",
                            (self._request_id,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        self._pdf_path = pdf_filename