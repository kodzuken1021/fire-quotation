from flask import Blueprint, render_template

from ..decorators import login_required

client_bp = Blueprint("client", __name__)


@client_bp.route("/dashboard")
@login_required
def dashboard():
    # TODO Day 7: My Requests with statuses
    return render_template("placeholder.html", title="Client Dashboard", note="Built on Day 7.")
