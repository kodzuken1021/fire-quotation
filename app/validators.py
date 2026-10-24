"""Server-side form rules.

The same rules also run in static/js/validation.js for instant feedback, but this
file is the one that counts: browser checks can always be bypassed.
"""
import re

try:
    import dns.resolver
    import dns.exception
except ImportError:      # dnspython not installed: the DNS check is skipped
    dns = None

NAME_RE = re.compile(r"^[A-Za-z'-]{2,20}$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^09\d{9}$")
REPEAT_RE = re.compile(r"(\d)\1{3,}")              # same digit 4+ times in a row
COMPANY_RE = re.compile(r"^[A-Za-z0-9 .,&'()\-]{2,100}$")

# Set to False to accept any email domain (company addresses); the DNS check still applies.
RESTRICT_EMAIL_DOMAINS = True
ALLOWED_EMAIL_DOMAINS = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "aol.com"}
ALLOWED_EMAIL_SUFFIXES = (".edu.ph",)
FAKE_DOMAINS = {"example.com", "test.com", "fake.com", "sample.com", "yourwebsite.com"}
TYPO_DOMAINS = {
    "gmai.com": "gmail.com", "gmial.com": "gmail.com", "gmal.com": "gmail.com", "gamil.com": "gmail.com",
    "yaho.com": "yahoo.com", "yahooo.com": "yahoo.com",
    "hotmial.com": "hotmail.com", "hotmal.com": "hotmail.com",
    "outlok.com": "outlook.com", "outloo.com": "outlook.com", "iclod.com": "icloud.com",
}


def clean(value):
    return (value or "").strip()


def domain_has_mx(domain):
    """True if the domain can receive email. If DNS itself can't be reached, allow it."""
    if dns is None:
        return True
    try:
        dns.resolver.resolve(domain, "MX", lifetime=3)
        return True
    except dns.resolver.NXDOMAIN:
        return False
    except dns.resolver.NoAnswer:          # no MX record: a plain A record also works
        try:
            dns.resolver.resolve(domain, "A", lifetime=3)
            return True
        except dns.exception.DNSException:
            return False
    except dns.exception.DNSException:     # timeout, no internet, etc.
        return True


def validate_email(raw, restrict=RESTRICT_EMAIL_DOMAINS, check_dns=True):
    """Returns (cleaned_email, error_message_or_None)."""
    email = clean(raw).lower()
    if not EMAIL_RE.match(email):
        return email, "Enter a valid email address."
    local, domain = email.rsplit("@", 1)
    if len(local) < 2:
        return email, "The part before @ must be at least 2 characters."
    if domain in TYPO_DOMAINS:
        return email, f"Did you mean {local}@{TYPO_DOMAINS[domain]}?"
    if domain in FAKE_DOMAINS:
        return email, "Please use a real email address."
    if restrict and not (domain in ALLOWED_EMAIL_DOMAINS or domain.endswith(ALLOWED_EMAIL_SUFFIXES)):
        return email, ("Use a recognized email provider (Gmail, Yahoo, Hotmail, Outlook, iCloud, AOL) "
                       "or a school .edu.ph address.")
    if check_dns and not domain_has_mx(domain):
        return email, "That email domain cannot receive email."
    return email, None


def validate_registration(form):
    """Returns (data, errors). errors is a dict {field_name: message}."""
    data = {k: clean(form.get(k)) for k in ("first_name", "last_name", "company_name", "contact_number")}
    errors = {}

    for key, label in (("first_name", "First name"), ("last_name", "Last name")):
        if not NAME_RE.match(data[key]):
            errors[key] = f"{label} must be 2 to 20 letters (apostrophes and hyphens allowed)."

    data["email"], err = validate_email(form.get("email"))
    if err:
        errors["email"] = err

    contact = data["contact_number"]
    if not PHONE_RE.match(contact):
        errors["contact_number"] = "Enter an 11-digit mobile number starting with 09 (example: 09171234567)."
    elif REPEAT_RE.search(contact):
        errors["contact_number"] = "The number cannot repeat the same digit 4 or more times in a row."

    if not COMPANY_RE.match(data["company_name"]):
        errors["company_name"] = "Company name must be 2 to 100 characters (letters, numbers and . , & ' ( ) - only)."

    password = form.get("password") or ""
    confirm = form.get("confirm_password") or ""
    if len(password) < 8 or not re.search(r"\d", password):
        errors["password"] = "Password must be at least 8 characters and include a number."
    elif len(password) > 128:
        errors["password"] = "Password is too long (128 characters maximum)."
    elif password != confirm:
        errors["confirm_password"] = "Passwords do not match."
    data["password"] = password

    return data, errors
