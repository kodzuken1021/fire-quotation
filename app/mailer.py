"""Email helpers. Each function returns True if sent, False if not, and never raises,
so a mail problem can never undo a saved request."""
from flask import current_app
from flask_mail import Message

from .extensions import mail

BUSINESS = "Blazer Fire Extinguisher"

CONTACT = (
    f"{BUSINESS}\n"
    "Email: blazer.fireextinguishertrading@gmail.com\n"
    "Phone: (049) 523-9823 / +63 932-534-3195\n"
    "Fire alarm (FDAS): inquiry@lsramossafety.com | (049) 539-0604 / +63 922-775-0035\n"
    "Monday to Friday: 7:30 AM - 4:30 PM (Main Branch); "
    "8:00 AM - 5:00 PM (Pakil and Siniloan Branches)"
)


def _send(subject, recipient, body, attachment=None):
    """attachment = (path_on_disk, file_name_in_email) for a PDF, or None."""
    if not current_app.config.get("MAIL_USERNAME"):
        current_app.logger.warning("Email skipped: MAIL_USERNAME is not set in .env")
        return False
    try:
        msg = Message(subject, recipients=[recipient], body=body)
        if attachment:
            with open(attachment[0], "rb") as f:
                msg.attach(attachment[1], "application/pdf", f.read())
        mail.send(msg)
        return True
    except Exception:                      # SMTP error, no internet, bad password, no sender
        current_app.logger.exception("Email could not be sent to %s", recipient)
        return False


def send_request_received(user, req):
    lines = [f"  - {d['name']} x {d['quantity']}" for d in req.item_details()]
    body = (
        f"Hello {user.full_name},\n\n"
        f"We received your quote request #{req.id}.\n\n"
        "Items requested:\n" + "\n".join(lines) + "\n\n"
        f"Installation needed: {'Yes' if req.needs_installation else 'No'}\n"
        f"Testing needed: {'Yes' if req.needs_testing else 'No'}\n"
    )
    if req.wants_inspection:
        body += (
            "\nYou asked for a free on-site inspection.\n"
            f"Site address: {req.inspection_address}\n"
            f"Preferred date: {req.preferred_date.strftime('%B %d, %Y') if req.preferred_date else 'No preference'}\n"
            "We will email you the confirmed schedule.\n"
        )
    body += "\nWe will review your request and email your official quotation.\n\n" + CONTACT
    return _send(f"Quote request #{req.id} received", user.email, body)


def send_inspection_schedule(user, req):
    body = (
        f"Hello {user.full_name},\n\n"
        f"Your free on-site inspection for request #{req.id} is scheduled on "
        f"{req.inspection_date.strftime('%A, %B %d, %Y')}.\n"
        f"Site address: {req.inspection_address}\n\n"
        "If this date does not work for you, reply to this email and we will reschedule.\n\n"
        + CONTACT
    )
    return _send(f"Inspection schedule for request #{req.id}", user.email, body)


def send_quotation(user, req, pdf_path):
    body = (
        f"Hello {user.full_name},\n\n"
        f"Thank you for your request #{req.id}. Your official quotation is attached as a PDF.\n\n"
        "If you have questions or want to proceed, reply to this email.\n\n"
        + CONTACT
    )
    return _send(f"Official quotation for request #{req.id}", user.email, body,
                 attachment=(pdf_path, f"Quotation-{req.id}.pdf"))


def send_password_reset(user, link):
    body = (
        f"Hello {user.full_name},\n\n"
        "We received a request to reset your password. Open the link below to choose a new one. "
        "The link works for 30 minutes and can be used once.\n\n"
        f"{link}\n\n"
        "If you did not ask for this, ignore this email and your password will stay the same.\n\n"
        + BUSINESS
    )
    return _send("Reset your password", user.email, body)


def send_verification(user, link):
    body = (
        f"Hello {user.full_name},\n\n"
        "Thank you for registering. Open the link below to verify your email address. "
        "The link works for 24 hours.\n\n"
        f"{link}\n\n"
        "If you did not create an account, ignore this email.\n\n"
        + BUSINESS
    )
    return _send("Verify your email", user.email, body)