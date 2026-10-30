import pymysql
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from ..decorators import admin_required
from ..models import CATEGORIES, STATUSES, CatalogItem, QuoteRequest, User
from ..validators import validate_catalog_item

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
    except pymysql.MySQLError:
        flash(DB_DOWN, "danger")
        return redirect(url_for("admin.dashboard"))
    return render_template("admin_request_detail.html", req=req, details=details,
                           client=client, statuses=STATUSES)


@admin_bp.route("/requests/<int:request_id>/status", methods=["POST"])
@admin_required
def update_status(request_id):
    try:
        req = QuoteRequest.find(request_id)
        if req is None:
            abort(404)
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