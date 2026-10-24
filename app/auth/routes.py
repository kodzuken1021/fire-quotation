from flask import Blueprint, redirect, render_template, session, url_for

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register")
def register():
    # TODO Day 3: registration form, validation, hashed password
    return render_template("placeholder.html", title="Register", note="Built on Day 3.")


@auth_bp.route("/login")
def login():
    # TODO Day 3: login form, session with user_id and role
    return render_template("placeholder.html", title="Login", note="Built on Day 3.")


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.home"))
