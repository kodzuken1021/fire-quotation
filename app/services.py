"""Workflows that combine several classes."""
import os

from .mailer import send_quotation
from .quotation_pdf import build_quotation_pdf


class QuotationIssuer:
    """Builds the PDF, emails it, and marks the quotation as sent."""

    def __init__(self, folder):
        self._folder = folder

    def issue(self, quotation, req, client):
        """Return True if the email was sent. mark_sent() runs only after the email succeeded."""
        filename = build_quotation_pdf(self._folder, quotation, req, client)
        if not send_quotation(client, req, os.path.join(self._folder, filename)):
            return False
        quotation.mark_sent(filename)
        return True