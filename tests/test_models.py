from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models import Inspection, Quotation, QuoteRequest


def test_quotation_total_includes_charges():
    q = Quotation(1, installation_charge=100, testing_charge=50)
    q.add_line(1, 2, "10.50")
    assert q.total == Decimal("171.00")


def test_quotation_rejects_zero_quantity():
    with pytest.raises(ValueError):
        Quotation(1).add_line(1, 0, "10")


def test_inspection_rejects_past_date():
    with pytest.raises(ValueError):
        Inspection("123 Main Street").schedule(date.today() - timedelta(days=1))


def test_inspection_rejects_short_address():
    with pytest.raises(ValueError):
        Inspection("abc")


def test_client_transitions():
    pending = QuoteRequest(1, status="Pending")
    sent = QuoteRequest(1, status="Quote Sent")
    assert pending.client_can_change_to("Cancelled")
    assert not pending.client_can_change_to("Accepted")
    assert sent.client_can_change_to("Accepted") and sent.client_can_change_to("Declined")
    assert not sent.client_can_change_to("Cancelled")


def test_cancel_blocked_after_quote_sent():
    with pytest.raises(ValueError):
        QuoteRequest(1, status="Quote Sent").cancel()