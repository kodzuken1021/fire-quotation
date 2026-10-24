from flask import Blueprint, render_template

from ..decorators import admin_required

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    # TODO Day 8: pending requests, request list and detail pages
    return render_template("placeholder.html", title="Admin Dashboard", note="Built on Day 8.")
