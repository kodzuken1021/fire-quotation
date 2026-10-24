import pymysql
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from ..db import get_db
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
                conn = get_db()
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM users WHERE email = %s", (data["email"],))
                    if cur.fetchone():
                        errors["email"] = "That email is already registered."
                    else:
                        cur.execute(
                            "INSERT INTO users (full_name, email, password_hash, role, company_name, contact_number) "
                            "VALUES (%s, %s, %s, 'client', %s, %s)",
                            (f"{data['first_name']} {data['last_name']}", data["email"],
                             generate_password_hash(data["password"]),
                             data["company_name"], data["contact_number"]),
                        )
                        conn.commit()
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
        if not email or not password:
            flash("Please enter your email and password.", "danger")
        else:
            try:
                with get_db().cursor() as cur:
                    cur.execute(
                        "SELECT id, full_name, password_hash, role FROM users WHERE email = %s", (email,)
                    )
                    user = cur.fetchone()
            except pymysql.MySQLError:
                flash(DB_DOWN, "danger")
            else:
                if user and check_password_hash(user["password_hash"], password):
                    session.clear()                  # drop anything left from before login
                    session.permanent = True         # expires after PERMANENT_SESSION_LIFETIME
                    session["user_id"] = user["id"]
                    session["role"] = user["role"]
                    session["name"] = user["full_name"]
                    flash(f"Welcome back, {user['full_name']}!", "success")
                    return redirect(_home_for(user["role"]))
                flash("Invalid email or password.", "danger")   # same message for both cases on purpose
    return render_template("login.html", email=email)


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
