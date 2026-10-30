from ..db import get_db

CATEGORIES = ("Extinguisher", "FDAS", "Suppression System", "Service")


class CatalogItem:
    """A product or service shown in the public catalog (never has a price)."""

    def __init__(self, name, category, description="", is_active=True, id=None):
        self._id = id
        self.name = name              # goes through the validating setters below
        self.category = category
        self.description = description
        self.is_active = bool(is_active)

    @property
    def id(self): return self._id

    @property
    def name(self): return self._name

    @name.setter
    def name(self, value):
        value = (value or "").strip()
        if not 2 <= len(value) <= 150:
            raise ValueError("Name must be 2 to 150 characters.")
        self._name = value

    @property
    def category(self): return self._category

    @category.setter
    def category(self, value):
        if value not in CATEGORIES:
            raise ValueError("Unknown category.")
        self._category = value

    # ---- database ----
    @staticmethod
    def _from_row(row):
        return CatalogItem(row["name"], row["category"], row["description"] or "",
                       row["is_active"], row["id"])

    @staticmethod
    def all_active(category=None):
        sql = "SELECT id, name, category, description, is_active FROM catalog_items WHERE is_active = 1"
        params = ()
        if category:
            sql += " AND category = %s"
            params = (category,)
        with get_db().cursor() as cur:
            cur.execute(sql + " ORDER BY category, name", params)
            return [CatalogItem._from_row(r) for r in cur.fetchall()]

    @staticmethod
    def search(category=None, query=None):
        """Active items, optionally filtered by category and a search word (name or description)."""
        sql = "SELECT id, name, category, description, is_active FROM catalog_items WHERE is_active = 1"
        params = []
        if category in CATEGORIES:
            sql += " AND category = %s"
            params.append(category)
        if query:
            # escape LIKE wildcards so a typed % or _ is searched literally
            like = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            sql += " AND (name LIKE %s OR description LIKE %s)"
            params += [like, like]
        sql += " ORDER BY FIELD(category, 'Extinguisher', 'FDAS', 'Suppression System', 'Service'), name"
        with get_db().cursor() as cur:
            cur.execute(sql, params)
            return [CatalogItem._from_row(r) for r in cur.fetchall()]

    @staticmethod
    def category_counts():
        """{category: number of active items}, for the filter buttons."""
        with get_db().cursor() as cur:
            cur.execute("SELECT category, COUNT(*) AS n FROM catalog_items WHERE is_active = 1 GROUP BY category")
            return {r["category"]: r["n"] for r in cur.fetchall()}

    @staticmethod
    def find(item_id):
        with get_db().cursor() as cur:
            cur.execute("SELECT id, name, category, description, is_active FROM catalog_items WHERE id = %s", (item_id,))
            row = cur.fetchone()
        return CatalogItem._from_row(row) if row else None

    @staticmethod
    def all_for_admin(category=None, query=None, status="all"):
        """Every item, including hidden ones, for the admin catalog page."""
        sql = "SELECT id, name, category, description, is_active FROM catalog_items WHERE 1 = 1"
        params = []
        if category in CATEGORIES:
            sql += " AND category = %s"
            params.append(category)
        if status == "active":
            sql += " AND is_active = 1"
        elif status == "hidden":
            sql += " AND is_active = 0"
        if query:
            like = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            sql += " AND (name LIKE %s OR description LIKE %s)"
            params += [like, like]
        sql += " ORDER BY FIELD(category, 'Extinguisher', 'FDAS', 'Suppression System', 'Service'), name"
        with get_db().cursor() as cur:
            cur.execute(sql, params)
            return [CatalogItem._from_row(r) for r in cur.fetchall()]

    @staticmethod
    def used_ids():
        """IDs of items that appear in at least one quote request."""
        with get_db().cursor() as cur:
            cur.execute("SELECT DISTINCT item_id FROM quote_request_items")
            return {r["item_id"] for r in cur.fetchall()}

    def delete(self):
        """Permanent delete, only if no request ever used this item."""
        if self._id is None:
            raise ValueError("Item is not saved yet.")
        conn = get_db()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM catalog_items WHERE id = %s "
                    "AND NOT EXISTS (SELECT 1 FROM quote_request_items WHERE item_id = %s)",
                    (self._id, self._id))
                deleted = cur.rowcount
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        if not deleted:
            raise ValueError("This item is used in a request, so it can only be hidden.")

    def save(self):
        conn = get_db()
        try:
            with conn.cursor() as cur:
                if self._id is None:
                    cur.execute("INSERT INTO catalog_items (name, category, description, is_active) VALUES (%s, %s, %s, %s)",
                                (self._name, self._category, self.description, int(self.is_active)))
                    self._id = cur.lastrowid
                else:
                    cur.execute("UPDATE catalog_items SET name=%s, category=%s, description=%s, is_active=%s WHERE id=%s",
                                (self._name, self._category, self.description, int(self.is_active), self._id))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return self