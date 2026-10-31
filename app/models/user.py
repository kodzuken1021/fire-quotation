from abc import ABC, abstractmethod

from werkzeug.security import check_password_hash, generate_password_hash

from ..db import get_db
from .base import BaseModel

_SELECT = "SELECT id, full_name, email, password_hash, role, company_name, contact_number, profile_photo FROM users "
# Used so a login for an unknown email takes as long as one for a real email
_DUMMY_HASH = generate_password_hash("not-a-real-password")


class User(BaseModel, ABC):
    """Base class for every account.

    Encapsulation: the password hash is private and only touched by set_password()
    and verify_password(). Other code reads values through read-only properties.
    """

    def __init__(self, full_name, email, company_name=None, contact_number=None,
                 password_hash=None, id=None, profile_photo=None):
        self._id = id
        self._full_name = full_name
        self._email = email
        self._company_name = company_name
        self._contact_number = contact_number
        self._password_hash = password_hash
        self._profile_photo = profile_photo

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

    @property
    def profile_photo(self): return self._profile_photo

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
            raise ValueError("Use update_profile() to change an existing user.")
        if not self._password_hash:
            raise ValueError("Set a password before saving.")
        with self.transaction() as cur:
            cur.execute(
                "INSERT INTO users (full_name, email, password_hash, role, company_name, contact_number) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (self._full_name, self._email, self._password_hash, self.role,
                 self._company_name, self._contact_number),
            )
            new_id = cur.lastrowid
        self._id = new_id        # set only after the commit succeeded
        return self

    @staticmethod
    def _from_row(row):
        if row is None:
            return None
        cls = _ROLE_CLASSES[row["role"]]
        return cls(row["full_name"], row["email"], row["company_name"],
                   row["contact_number"], row["password_hash"], row["id"], row["profile_photo"])

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

    # ---- profile updates ----
    def update_profile(self, full_name, email, company_name, contact_number):
        if self._id is None:
            raise ValueError("Save the user first.")
        with self.transaction() as cur:
            cur.execute(
                "UPDATE users SET full_name=%s, email=%s, company_name=%s, contact_number=%s WHERE id=%s",
                (full_name, email, company_name, contact_number, self._id))
        self._full_name, self._email = full_name, email
        self._company_name, self._contact_number = company_name, contact_number

    def change_password(self, old_password, new_password):
        if not self.verify_password(old_password):
            raise ValueError("Current password is incorrect.")
        new_hash = generate_password_hash(new_password)
        with self.transaction() as cur:
            cur.execute("UPDATE users SET password_hash=%s WHERE id=%s", (new_hash, self._id))
        self._password_hash = new_hash

    def set_profile_photo(self, filename):
        with self.transaction() as cur:
            cur.execute("UPDATE users SET profile_photo=%s WHERE id=%s", (filename, self._id))
        self._profile_photo = filename

    @staticmethod
    def email_taken_by_other(email, user_id):
        with get_db().cursor() as cur:
            cur.execute("SELECT 1 FROM users WHERE email = %s AND id <> %s", (email, user_id))
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