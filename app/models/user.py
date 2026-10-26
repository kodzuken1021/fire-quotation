from abc import ABC, abstractmethod

from werkzeug.security import check_password_hash, generate_password_hash

from ..db import get_db

_SELECT = "SELECT id, full_name, email, password_hash, role, company_name, contact_number FROM users "
# Used so a login for an unknown email takes as long as one for a real email
_DUMMY_HASH = generate_password_hash("not-a-real-password")


class User(ABC):
    """Base class for every account.

    Encapsulation: the password hash is private and only touched by set_password()
    and verify_password(). Other code reads values through read-only properties.
    """

    def __init__(self, full_name, email, company_name=None, contact_number=None,
                 password_hash=None, id=None):
        self._id = id
        self._full_name = full_name
        self._email = email
        self._company_name = company_name
        self._contact_number = contact_number
        self._password_hash = password_hash

    # ---- read-only properties ----
    @property
    def id(self): return self._id

    @property
    def full_name(self): return self._full_name

    @property
    def email(self): return self._email

    @property
    def company_name(self): return self._company_name

    @property
    def contact_number(self): return self._contact_number

    # ---- each subclass must define these (abstraction / polymorphism) ----
    @property
    @abstractmethod
    def role(self): ...

    @property
    @abstractmethod
    def dashboard_endpoint(self): ...

    # ---- password handling ----
    def set_password(self, plain_password):
        self._password_hash = generate_password_hash(plain_password)

    def verify_password(self, plain_password):
        return bool(self._password_hash) and check_password_hash(self._password_hash, plain_password)

    @staticmethod
    def dummy_verify(plain_password):
        check_password_hash(_DUMMY_HASH, plain_password)

    # ---- database ----
    def save(self):
        """Insert a new user. The caller handles database errors."""
        if self._id is not None:
            raise ValueError("Updating an existing user is not built yet.")
        if not self._password_hash:
            raise ValueError("Set a password before saving.")
        conn = get_db()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (full_name, email, password_hash, role, company_name, contact_number) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (self._full_name, self._email, self._password_hash, self.role,
                     self._company_name, self._contact_number),
                )
                self._id = cur.lastrowid
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return self

    @staticmethod
    def _from_row(row):
        if row is None:
            return None
        cls = _ROLE_CLASSES[row["role"]]
        return cls(row["full_name"], row["email"], row["company_name"],
                   row["contact_number"], row["password_hash"], row["id"])

    @staticmethod
    def find_by_email(email):
        with get_db().cursor() as cur:
            cur.execute(_SELECT + "WHERE email = %s", (email,))
            return User._from_row(cur.fetchone())

    @staticmethod
    def find_by_id(user_id):
        with get_db().cursor() as cur:
            cur.execute(_SELECT + "WHERE id = %s", (user_id,))
            return User._from_row(cur.fetchone())

    @staticmethod
    def email_exists(email):
        with get_db().cursor() as cur:
            cur.execute("SELECT 1 FROM users WHERE email = %s", (email,))
            return cur.fetchone() is not None


class Client(User):
    """A customer who requests quotes."""
    @property
    def role(self): return "client"

    @property
    def dashboard_endpoint(self): return "client.dashboard"

    def can_manage_catalog(self): return False


class Admin(User):
    """Staff who review requests, schedule inspections and send quotations."""
    @property
    def role(self): return "admin"

    @property
    def dashboard_endpoint(self): return "admin.dashboard"

    def can_manage_catalog(self): return True


_ROLE_CLASSES = {"client": Client, "admin": Admin}
