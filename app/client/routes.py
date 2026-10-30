from datetime import date

import pymysql
from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from ..decorators import client_required
from ..mailer import send_request_received
from ..models import CATEGORIES, STATUSES, CatalogItem, QuoteRequest, User
from ..validators import validate_quote_request

client_bp = Blueprint("client", __name__)
DB_DOWN = "We could not reach the database. Please try again in a moment."


def _grouped_items():
    items = CatalogItem.all_active()
    groups = [(c, [i for i in items if i.category == c]) for c in CATEGORIES]
    return [(c, rows) for c, rows in groups if rows]


def _request_form_context(groups, selected=None, flags=None, notes="", errors=None,
                          form=None, qtys=None, editing=False, req=None):
    return {
        "groups": groups,
        "selected": selected or set(),
        "flags": flags or {},
        "notes": notes,
        "errors": errors or {},
        "form": form or {},
        "qtys": qtys or {},
        "editing": editing,
        "req": req,
        "today": date.today().isoformat(),
    }


def _posted_selection(items):
    valid_ids = {item.id for item in items}
    selected = {
        raw for raw in request.form.getlist("items")
        if raw.isascii() and raw.isdigit() and int(raw) in valid_ids
    }
    qtys = {key[4:]: value for key, value in request.form.items() if key.startswith("qty_")}
    return selected, qtys


def _flags_from_request(req):
    return {
        "needs_installation": req.needs_installation,
        "needs_testing": req.needs_testing,
        "wants_inspection": req.wants_inspection,
    }


@client_bp.route("/dashboard")
@client_required
def dashboard():
    requests_, counts = [], {status: 0 for status in STATUSES}
    try:
        requests_ = QuoteRequest.for_user(session["user_id"])
    except pymysql.MySQLError:
        flash(DB_DOWN, "danger")
    for quote_request in requests_:
        counts[quote_request.status] += 1
    return render_template("client_dashboard.html", requests=requests_, counts=counts)


@client_bp.route("/request/new", methods=["GET", "POST"])
@client_bp.route("/requests/new", methods=["GET", "POST"])
@client_required
def new_request():
    groups, errors, flags, form, notes = [], {}, {}, {}, ""
    selected, qtys = set(), {}
    try:
        groups = _grouped_items()
        items = [item for _, rows in groups for item in rows]
        valid_ids = {item.id for item in items}

        if request.method == "POST":
            selected, qtys = _posted_selection(items)
            form = request.form
            data, errors = validate_quote_request(request.form, valid_ids)
            flags = {
                "needs_installation": data["needs_installation"],
                "needs_testing": data["needs_testing"],
                "wants_inspection": data["wants_inspection"],
            }
            notes = data["notes"]
            if not errors:
                quote_request = QuoteRequest(
                    session["user_id"],
                    data["needs_installation"],
                    data["needs_testing"],
                    data["wants_inspection"],
                    data["notes"],
                    inspection_address=data["inspection_address"],
                    preferred_date=data["preferred_date"],
                )
                for item_id, quantity in data["items"]:
                    quote_request.add_item(item_id, quantity)
                    quote_request.save()
                    user = User.find_by_id(session["user_id"])
                    if user and send_request_received(user, quote_request):
                        flash("Quote request submitted. A confirmation email is on its way.", "success")
                    else:
                        flash("Quote request submitted, but we could not send the confirmation email.", "warning")
                    return redirect(url_for("client.request_detail", request_id=quote_request.id))
        else:
            preset = request.args.get("item", type=int)
            if preset in valid_ids:
                selected = {str(preset)}
                qtys[str(preset)] = "1"
    except ValueError as error:
        errors["items"] = str(error)
    except pymysql.MySQLError:
        flash(DB_DOWN, "danger")
    return render_template(
        "request_form.html",
        **_request_form_context(groups, selected, flags, notes, errors, form, qtys),
    )


@client_bp.route("/requests/<int:request_id>")
@client_required
def request_detail(request_id):
    try:
        quote_request = QuoteRequest.find(request_id, session["user_id"])
        if quote_request is None:
            abort(404)
        details = quote_request.item_details()
    except pymysql.MySQLError:
        flash(DB_DOWN, "danger")
        return redirect(url_for("client.dashboard"))
    return render_template("request_detail.html", req=quote_request, details=details)


@client_bp.route("/requests/<int:request_id>/edit", methods=["GET", "POST"])
@client_required
def edit_request(request_id):
    try:
        quote_request = QuoteRequest.find(request_id, session["user_id"])
        if quote_request is None:
            abort(404)
        if not quote_request.can_be_edited():
            flash("Only pending requests can be edited.", "warning")
            return redirect(url_for("client.request_detail", request_id=quote_request.id))

        groups = _grouped_items()
        items = [item for _, rows in groups for item in rows]
        valid_ids = {item.id for item in items}
        selected = {str(item_id) for item_id, _ in quote_request.items}
        qtys = {str(item_id): str(quantity) for item_id, quantity in quote_request.items}
        flags = _flags_from_request(quote_request)
        notes = quote_request.notes
        form = {
            "inspection_address": quote_request.inspection_address or "",
            "preferred_date": quote_request.preferred_date.isoformat() if quote_request.preferred_date else "",
        }
        errors = {}

        if request.method == "POST":
            selected, qtys = _posted_selection(items)
            form = request.form
            data, errors = validate_quote_request(request.form, valid_ids)
            flags = {
                "needs_installation": data["needs_installation"],
                "needs_testing": data["needs_testing"],
                "wants_inspection": data["wants_inspection"],
            }
            notes = data["notes"]
            if not errors:
                quote_request.update_details(
                    needs_installation=data["needs_installation"],
                    needs_testing=data["needs_testing"],
                    wants_inspection=data["wants_inspection"],
                    notes=data["notes"],
                    inspection_address=data["inspection_address"],
                    preferred_date=data["preferred_date"],
                )
                quote_request.clear_items()
                for item_id, quantity in data["items"]:
                    quote_request.add_item(item_id, quantity)
                quote_request.save()
                flash("Request updated.", "success")
                return redirect(url_for("client.request_detail", request_id=quote_request.id))
    except ValueError as error:
        errors["items"] = str(error)
        flash(str(error), "warning")
    except pymysql.MySQLError:
        flash(DB_DOWN, "danger")
        return redirect(url_for("client.dashboard"))

    return render_template(
        "request_form.html",
        **_request_form_context(groups, selected, flags, notes, errors, form, qtys, True, quote_request),
    )


@client_bp.route("/requests/<int:request_id>/cancel", methods=["POST"])
@client_required
def cancel_request(request_id):
    try:
        quote_request = QuoteRequest.find(request_id, session["user_id"])
        if quote_request is None:
            abort(404)
        quote_request.cancel()
        flash("Request cancelled.", "info")
    except ValueError as error:
        flash(str(error), "warning")
    except pymysql.MySQLError:
        flash(DB_DOWN, "danger")
    return redirect(url_for("client.dashboard"))