import pymysql
from flask import Blueprint, flash, render_template, request

from ..models.catalog_item import CATEGORIES, CatalogItem

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def home():
    return render_template("home.html")


@main_bp.route("/catalog")
def catalog():
    """Public catalog: browse, filter by category, search. Never shows prices."""
    category = request.args.get("category", "")
    if category not in CATEGORIES:           # ignore anything that is not a real category
        category = ""
    q = request.args.get("q", "").strip()[:60]

    items, counts = [], {}
    try:
        items = CatalogItem.search(category or None, q or None)
        counts = CatalogItem.category_counts()
    except pymysql.MySQLError:
        flash("We could not load the catalog right now. Please try again in a moment.", "danger")

    groups = [(c, [i for i in items if i.category == c]) for c in CATEGORIES]
    groups = [(c, rows) for c, rows in groups if rows]
    return render_template("catalog.html", groups=groups, total=len(items), category=category,
                           q=q, categories=CATEGORIES, counts=counts)