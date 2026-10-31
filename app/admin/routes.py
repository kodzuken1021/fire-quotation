import os
import pymysql
from flask import current_app
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from ..mailer import send_inspection_schedule, send_quotation
from ..decorators import admin_required
from datetime import date, timedelta
from ..models import CATEGORIES, STATUSES, CatalogItem, QuoteRequest, Quotation, User
from ..validators import validate_catalog_item, validate_quotation
from ..quotation_pdf import build_quotation_pdf

admin_bp = Blueprint("admin", __name__)

DB_DOWN = "We could not reach the database. Please try again in a moment."


@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    status = request.args.get("status", "")
    if status not in STATUSES:
        status = ""
    rows, counts = [], {s: 0 for s in STATUSES}
    try:
        counts = QuoteRequest.status_counts()
        rows = QuoteRequest.all_with_clients(status or None)
    except pymysql.MySQLError:
        flash(DB_DOWN, "danger")
    return render_template("admin_dashboard.html", rows=rows, counts=counts,
                           status=status, statuses=STATUSES)


@admin_bp.route("/requests/<int:request_id>")
@admin_required
def request_detail(request_id):
    try:
        req = QuoteRequest.find(request_id)
        if req is None:
            abort(404)
        details = req.item_details()
        client = User.find_by_id(req.user_id)
        quotation = Quotation.find_by_request(request_id)
    except pymysql.MySQLError:
        flash(DB_DOWN, "danger")
        return redirect(url_for("admin.dashboard"))
    return render_template("admin_request_detail.html", req=req, details=details,
                           client=client, statuses=STATUSES, quotation=quotation,   # add quotation
                           today=date.today().isoformat())


@admin_bp.route("/requests/<int:request_id>/status", methods=["POST"])
@admin_required
def update_status(request_id):
    try:
        if request.form.get("status") == "Quote Sent":
            flash("Quote Sent is set automatically when you email the quotation.", "warning")
            return redirect(url_for("admin.request_detail", request_id=request_id))
        req = QuoteRequest.find(request_id)
        if req is None:
            abort(404)
        if req.status == "Quote Sent":
            flash("A quotation was already sent, so the status can't be changed.", "warning")
            return redirect(url_for("admin.request_detail", request_id=request_id))
        req.set_status(request.form.get("status", ""))
        flash(f"Status changed to {req.status}.", "success")
    except ValueError as error:
        flash(str(error), "warning")
    except pymysql.MySQLError:
        flash(DB_DOWN, "danger")
    return redirect(url_for("admin.request_detail", request_id=request_id))

@admin_bp.route("/requests/<int:request_id>/delete", methods=["POST"])
@admin_required
def delete_request(request_id):
    try:
        QuoteRequest.delete_by_id(request_id)
        flash("Request deleted.", "info")
    except pymysql.MySQLError:
        flash(DB_DOWN, "danger")
    return redirect(url_for("admin.dashboard"))

@admin_bp.route("/catalog")
@admin_required
def catalog_list():
    category = request.args.get("category", "")
    if category not in CATEGORIES:
        category = ""
    status = request.args.get("status", "all")
    if status not in ("all", "active", "hidden"):
        status = "all"
    q = request.args.get("q", "").strip()[:60]

    items, used = [], set()
    try:
        items = CatalogItem.all_for_admin(category or None, q or None, status)
        used = CatalogItem.used_ids()
    except pymysql.MySQLError:
        flash(DB_DOWN, "danger")
    return render_template("admin_catalog.html", items=items, used=used, categories=CATEGORIES,
                           category=category, status=status, q=q)


@admin_bp.route("/catalog/new", methods=["GET", "POST"])
@admin_required
def catalog_new():
    form, errors = {"is_active": "1"}, {}
    if request.method == "POST":
        form = request.form
        data, errors = validate_catalog_item(request.form, CATEGORIES)
        if not errors:
            try:
                CatalogItem(data["name"], data["category"], data["description"], data["is_active"]).save()
                flash("Item added to the catalog.", "success")
                return redirect(url_for("admin.catalog_list"))
            except pymysql.MySQLError:
                flash(DB_DOWN, "danger")
    return render_template("admin_catalog_form.html", item=None, form=form, errors=errors, categories=CATEGORIES)


@admin_bp.route("/catalog/<int:item_id>/edit", methods=["GET", "POST"])
@admin_required
def catalog_edit(item_id):
    errors = {}
    try:
        item = CatalogItem.find(item_id)
        if item is None:
            abort(404)
        form = {"name": item.name, "category": item.category, "description": item.description,
                "is_active": "1" if item.is_active else ""}
        if request.method == "POST":
            form = request.form
            data, errors = validate_catalog_item(request.form, CATEGORIES)
            if not errors:
                item.name = data["name"]
                item.category = data["category"]
                item.description = data["description"]
                item.is_active = data["is_active"]
                item.save()
                flash("Item updated.", "success")
                return redirect(url_for("admin.catalog_list"))
    except pymysql.MySQLError:
        flash(DB_DOWN, "danger")
        return redirect(url_for("admin.catalog_list"))
    return render_template("admin_catalog_form.html", item=item, form=form, errors=errors, categories=CATEGORIES)


@admin_bp.route("/catalog/<int:item_id>/toggle", methods=["POST"])
@admin_required
def catalog_toggle(item_id):
    try:
        item = CatalogItem.find(item_id)
        if item is None:
            abort(404)
        item.is_active = not item.is_active
        item.save()
        flash(f"“{item.name}” is now {'visible' if item.is_active else 'hidden'}.", "info")
    except pymysql.MySQLError:
        flash(DB_DOWN, "danger")
    return redirect(url_for("admin.catalog_list"))


@admin_bp.route("/catalog/<int:item_id>/delete", methods=["POST"])
@admin_required
def catalog_delete(item_id):
    try:
        item = CatalogItem.find(item_id)
        if item is None:
            abort(404)
        item.delete()
        flash(f"“{item.name}” was deleted.", "info")
    except ValueError as error:
        flash(str(error), "warning")
    except pymysql.MySQLError:
        flash(DB_DOWN, "danger")
    return redirect(url_for("admin.catalog_list"))

@admin_bp.route("/requests/<int:request_id>/inspection", methods=["POST"])
@admin_required
def schedule_inspection(request_id):
    try:
        req = QuoteRequest.find(request_id)
        if req is None:
            abort(404)
        try:
            when = date.fromisoformat(request.form.get("inspection_date", ""))
        except ValueError:
            flash("Choose a valid inspection date.", "warning")
            return redirect(url_for("admin.request_detail", request_id=request_id))
        req.schedule_inspection(when)
        client = User.find_by_id(req.user_id)
        if client and send_inspection_schedule(client, req):
            flash("Inspection scheduled and the client was emailed.", "success")
        else:
            flash("Inspection scheduled, but the email could not be sent.", "warning")
    except ValueError as error:
        flash(str(error), "warning")
    except pymysql.MySQLError:
        flash(DB_DOWN, "danger")
    return redirect(url_for("admin.request_detail", request_id=request_id))

@admin_bp.route("/requests/<int:request_id>/quote", methods=["GET", "POST"])
@admin_required
def build_quote(request_id):
    errors, form = {}, {}
    back = url_for("admin.request_detail", request_id=request_id)
    try:
        req = QuoteRequest.find(request_id)
        if req is None:
            abort(404)
        if req.status not in ("Pending", "Inspection Scheduled"):
            flash("Only pending or scheduled requests can be quoted.", "warning")
            return redirect(back)
        existing = Quotation.find_by_request(request_id)
        if existing and existing.sent_at:
            flash("This quotation was already sent.", "warning")
            return redirect(back)
        details = req.item_details()
        client = User.find_by_id(req.user_id)

        if request.method == "POST":
            form = request.form
            data, errors = validate_quotation(form, details, req.needs_installation, req.needs_testing)
            if not errors:
                quotation = Quotation(request_id, data["valid_until"],
                                      data["installation_charge"], data["testing_charge"])
                for item_id, qty, price in data["lines"]:
                    quotation.add_line(item_id, qty, price)
                quotation.save()
                flash("Quotation saved.", "success")
                return redirect(back)
        else:
            valid = (existing.valid_until if existing and existing.valid_until
                     else date.today() + timedelta(days=30))
            form = {"valid_until": valid.isoformat()}
            if existing:
                form["installation_charge"] = str(existing.installation_charge)
                form["testing_charge"] = str(existing.testing_charge)
                for line in existing.lines:
                    form[f"price_{line['item_id']}"] = str(line["unit_price"])
    except ValueError as error:
        flash(str(error), "warning")
        return redirect(back)
    except pymysql.MySQLError:
        flash(DB_DOWN, "danger")
        return redirect(back)
    return render_template("admin_build_quote.html", req=req, details=details, client=client,
                           form=form, errors=errors, today=date.today().isoformat())

@admin_bp.route("/requests/<int:request_id>/quote/send", methods=["POST"])
@admin_required
def send_quote(request_id):
    back = url_for("admin.request_detail", request_id=request_id)
    try:
        req = QuoteRequest.find(request_id)
        if req is None:
            abort(404)
        quotation = Quotation.find_by_request(request_id)
        if quotation is None:
            flash("Build the quotation first.", "warning")
            return redirect(back)
        if quotation.sent_at:
            flash("This quotation was already sent.", "warning")
            return redirect(back)
        if req.status not in ("Pending", "Inspection Scheduled"):
            flash("Only pending or scheduled requests can be quoted.", "warning")
            return redirect(back)
        client = User.find_by_id(req.user_id)
        if client is None:
            flash("Client account not found.", "warning")
            return redirect(back)

        folder = current_app.config["QUOTATION_FOLDER"]
        filename = build_quotation_pdf(folder, quotation, req, client)
        if send_quotation(client, req, os.path.join(folder, filename)):
            quotation.mark_sent(filename)
            flash("Quotation emailed to the client.", "success")
        else:
            flash("The PDF was created but the email could not be sent. Nothing was marked as sent, so you can try again.", "warning")
    except ValueError as error:
        flash(str(error), "warning")
    except pymysql.MySQLError:
        flash(DB_DOWN, "danger")
    return redirect(back)