import pymysql
from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from ..models.user import Client, User
from ..security import login_throttle
from ..validators import validate_registration

auth_bp = Blueprint("auth", __name__)

DB_DOWN = "We could not reach the database. Please try again in a moment."


def _home_for(role):
    return url_for("admin.dashboard" if role == "admin" else "client.dashboard")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    # Guests only: logged-in users go straight to their dashboard
    if "user_id" in session:
        return redirect(_home_for(session.get("role")))

    form, errors = {}, {}
    if request.method == "POST":
        form = request.form
        data, errors = validate_registration(form)
        if not errors:
            try:
                if User.email_exists(data["email"]):
                    errors["email"] = "That email is already registered."
                else:
                    client = Client(f"{data['first_name']} {data['last_name']}", data["email"],
                                    data["company_name"], data["contact_number"])
                    client.set_password(data["password"])
                    client.save()
                    flash("Account created. You can now log in.", "success")
                    return redirect(url_for("auth.login"))
            except pymysql.err.IntegrityError:      # two people registered the same email at once
                errors["email"] = "That email is already registered."
            except pymysql.MySQLError:
                flash(DB_DOWN, "danger")
    return render_template("register.html", form=form, errors=errors)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(_home_for(session.get("role")))

    email = ""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        key = f"{request.remote_addr}|{email}"

        if not email or not password:
            flash("Please enter your email and password.", "danger")
        elif login_throttle.is_blocked(key):
            flash(f"Too many failed attempts. Try again in {login_throttle.minutes_left(key)} minute(s).", "danger")
        else:
            try:
                user = User.find_by_email(email)
            except pymysql.MySQLError:
                flash(DB_DOWN, "danger")
            else:
                if user and user.verify_password(password):
                    login_throttle.reset(key)
                    session.clear()                  # drop anything left from before login
                    session.permanent = True         # idle timeout: PERMANENT_SESSION_LIFETIME
                    session["user_id"] = user.id
                    session["role"] = user.role
                    session["name"] = user.full_name
                    flash(f"Welcome back, {user.full_name}!", "success")
                    return redirect(url_for(user.dashboard_endpoint))
                if user is None:
                    User.dummy_verify(password)      # same response time whether or not the email exists
                login_throttle.record_failure(key)
                flash("Invalid email or password.", "danger")   # same message for both cases on purpose
    return render_template("login.html", email=email)


@auth_bp.route("/logout", methods=["POST"])          # POST + CSRF token: another site can't log you out
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))