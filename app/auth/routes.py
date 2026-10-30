import os
import uuid

import pymysql
from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, session, url_for)

from ..decorators import login_required
from ..models.user import Client, User
from ..security import detect_image_type, login_throttle
from ..validators import validate_password_change, validate_profile, validate_registration
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

@auth_bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if "user_id" in session:
        return redirect(_home_for(session.get("role")))

    email = ""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        key = f"admin|{request.remote_addr}|{email}"

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
                if user and user.role == "admin" and user.verify_password(password):
                    login_throttle.reset(key)
                    session.clear()
                    session.permanent = True
                    session["user_id"] = user.id
                    session["role"] = user.role
                    session["name"] = user.full_name
                    flash(f"Welcome back, {user.full_name}!", "success")
                    return redirect(url_for("admin.dashboard"))
                if user is None:
                    User.dummy_verify(password)
                login_throttle.record_failure(key)
                flash("Invalid admin email or password.", "danger")
    return render_template("admin_login.html", email=email)


# ---------------- profile (client and admin) ----------------
def _remove_photo_file(filename):
    if not filename:
        return
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], os.path.basename(filename))
    if os.path.isfile(path):
        os.remove(path)


def _load_user():
    try:
        return User.find_by_id(session["user_id"])
    except pymysql.MySQLError:
        return None


def _render_profile(user, form=None, errors=None, pw_errors=None):
    if form is None:
        form = {"full_name": user.full_name, "email": user.email,
                "contact_number": user.contact_number or "", "company_name": user.company_name or ""}
    return render_template("profile.html", user=user, form=form,
                           errors=errors or {}, pw_errors=pw_errors or {})


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = _load_user()
    if user is None:
        flash(DB_DOWN, "danger")
        return redirect(url_for("main.home"))

    if request.method == "POST":
        data, errors = validate_profile(request.form, user.role == "client")
        if not errors:
            try:
                if User.email_taken_by_other(data["email"], user.id):
                    errors["email"] = "That email is already registered."
                else:
                    user.update_profile(data["full_name"], data["email"],
                                        data["company_name"], data["contact_number"])
                    session["name"] = user.full_name
                    flash("Profile updated.", "success")
                    return redirect(url_for("auth.profile"))
            except pymysql.err.IntegrityError:
                errors["email"] = "That email is already registered."
            except pymysql.MySQLError:
                flash(DB_DOWN, "danger")
        return _render_profile(user, request.form, errors)
    return _render_profile(user)


@auth_bp.route("/profile/password", methods=["POST"])
@login_required
def change_password():
    user = _load_user()
    if user is None:
        flash(DB_DOWN, "danger")
        return redirect(url_for("main.home"))
    data, pw_errors = validate_password_change(request.form)
    if not pw_errors:
        try:
            user.change_password(data["old"], data["new"])
            flash("Password changed.", "success")
            return redirect(url_for("auth.profile"))
        except ValueError as error:
            pw_errors["old_password"] = str(error)
        except pymysql.MySQLError:
            flash(DB_DOWN, "danger")
    return _render_profile(user, pw_errors=pw_errors)


@auth_bp.route("/profile/photo", methods=["POST"])
@login_required
def update_photo():
    file = request.files.get("photo")
    if not file or not file.filename:
        flash("Choose an image first.", "warning")
        return redirect(url_for("auth.profile"))
    data = file.read()
    ext = detect_image_type(data)
    if ext is None:
        flash("Upload a PNG, JPG or WEBP image.", "danger")
        return redirect(url_for("auth.profile"))

    folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(folder, exist_ok=True)
    filename = f"user_{session['user_id']}_{uuid.uuid4().hex[:12]}.{ext}"   # never use the uploaded name
    path = os.path.join(folder, filename)
    with open(path, "wb") as fh:
        fh.write(data)

    user = _load_user()
    try:
        if user is None:
            raise pymysql.MySQLError()
        old = user.profile_photo
        user.set_profile_photo(filename)
    except pymysql.MySQLError:
        os.remove(path)
        flash(DB_DOWN, "danger")
        return redirect(url_for("auth.profile"))
    _remove_photo_file(old)
    flash("Profile photo updated.", "success")
    return redirect(url_for("auth.profile"))

@auth_bp.route("/profile/photo/remove", methods=["POST"])
@login_required
def remove_photo():
    user = _load_user()
    try:
        if user is None:
            raise pymysql.MySQLError()
        old = user.profile_photo
        user.set_profile_photo(None)
        _remove_photo_file(old)
        flash("Profile photo removed.", "info")
    except pymysql.MySQLError:
        flash(DB_DOWN, "danger")
    return redirect(url_for("auth.profile"))

@auth_bp.route("/logout", methods=["POST"])          # POST + CSRF token: another site can't log you out
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))