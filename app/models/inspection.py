from datetime import date, datetime

from .base import BaseModel


class Inspection(BaseModel):
    """The free on-site inspection of one quote request (at most one per request).

    A QuoteRequest owns its Inspection. The client supplies the site address and an
    optional preferred date; the admin later confirms the scheduled date.
    """

    def __init__(self, site_address, preferred_date=None, scheduled_date=None):
        self.site_address = site_address          # validated by the setters below
        self.preferred_date = preferred_date
        self._scheduled_date = scheduled_date     # only schedule() changes it afterwards

    # ---- properties ----
    @property
    def site_address(self): return self._site_address

    @site_address.setter
    def site_address(self, value):
        value = (value or "").strip()
        if not 5 <= len(value) <= 255:
            raise ValueError("Enter the site address (5 to 255 characters).")
        self._site_address = value

    @property
    def preferred_date(self): return self._preferred_date

    @preferred_date.setter
    def preferred_date(self, value):
        if isinstance(value, datetime):
            value = value.date()
        if value is not None and not isinstance(value, date):
            raise ValueError("Enter a valid preferred date.")
        self._preferred_date = value

    @property
    def scheduled_date(self): return self._scheduled_date

    @property
    def is_scheduled(self): return self._scheduled_date is not None

    # ---- business rules ----
    def change_details(self, site_address, preferred_date):
        """Client edits the address and preferred date while the request is still Pending."""
        self.site_address = site_address
        self.preferred_date = preferred_date

    def schedule(self, when):
        """Admin confirms the visit date (date only, never in the past)."""
        if isinstance(when, datetime):
            when = when.date()
        if not isinstance(when, date):
            raise ValueError("Choose a valid inspection date.")
        if when < date.today():
            raise ValueError("The inspection date cannot be in the past.")
        self._scheduled_date = when

    # ---- database ----
    def persist(self, cur, request_id):
        """Insert or update this request's inspection row using the caller's cursor,
        so it commits or rolls back together with the request."""
        cur.execute(
            "INSERT INTO inspections (request_id, site_address, preferred_date, scheduled_date) "
            "VALUES (%s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE site_address = VALUES(site_address), "
            "preferred_date = VALUES(preferred_date), scheduled_date = VALUES(scheduled_date)",
            (request_id, self._site_address, self._preferred_date, self._scheduled_date))

    @staticmethod
    def from_row(row):
        """Build from a saved row without re-validating old data."""
        inspection = Inspection.__new__(Inspection)
        inspection._site_address = row["site_address"]
        inspection._preferred_date = row["preferred_date"]
        inspection._scheduled_date = row["scheduled_date"]
        return inspection