"""Shop Orders API: a small REST API for a local shop or restaurant.

Customers browse products and place orders. Each order comes back with a
ready-made WhatsApp link so the shop gets the order on the phone it already uses.
"""
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from urllib.parse import quote

from flask import Flask, jsonify, request, render_template

PRODUCTS = [
    {"id": 1, "name": "Chicken Biryani", "category": "mains", "price": 249},
    {"id": 2, "name": "Paneer Butter Masala", "category": "mains", "price": 219},
    {"id": 3, "name": "Natukodi Curry", "category": "mains", "price": 329},
    {"id": 4, "name": "Butter Naan", "category": "breads", "price": 45},
    {"id": 5, "name": "Gulab Jamun (2 pcs)", "category": "desserts", "price": 79},
    {"id": 6, "name": "Masala Chai", "category": "drinks", "price": 30},
]

STATUSES = ["received", "preparing", "ready", "delivered", "cancelled"]
NEXT_STATUS = {
    "received": {"preparing", "cancelled"},
    "preparing": {"ready", "cancelled"},
    "ready": {"delivered"},
    "delivered": set(),
    "cancelled": set(),
}
PHONE_RE = re.compile(r"^\+?\d{10,13}$")
MAX_QTY = 20


class ApiError(Exception):
    def __init__(self, status, message, details=None):
        super().__init__(message)
        self.status, self.message, self.details = status, message, details


def create_app(shop_whatsapp=None, admin_key=None):
    app = Flask(__name__)
    app.config["SHOP_WHATSAPP"] = shop_whatsapp or os.environ.get("SHOP_WHATSAPP", "910000000000")
    app.config["ADMIN_KEY"] = admin_key or os.environ.get("ADMIN_KEY", "demo-key")
    products = {p["id"]: p for p in PRODUCTS}
    orders = {}
    lock = threading.Lock()

    @app.errorhandler(ApiError)
    def handle_api_error(err):
        body = {"error": err.message}
        if err.details:
            body["details"] = err.details
        return jsonify(body), err.status

    @app.errorhandler(404)
    def not_found(_):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(405)
    def bad_method(_):
        return jsonify({"error": "Method not allowed"}), 405

    def json_body():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ApiError(400, "Send a JSON object in the request body")
        return data

    def require_admin():
        if request.headers.get("X-API-Key") != app.config["ADMIN_KEY"]:
            raise ApiError(401, "Missing or wrong X-API-Key header")

    @app.get("/")
    def docs():
        return render_template("index.html", products=PRODUCTS)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/api/products")
    def list_products():
        category = request.args.get("category")
        items = [p for p in PRODUCTS if not category or p["category"] == category]
        return jsonify({"count": len(items), "products": items})

    @app.get("/api/products/<int:product_id>")
    def get_product(product_id):
        if product_id not in products:
            raise ApiError(404, f"No product with id {product_id}")
        return jsonify(products[product_id])

    @app.post("/api/orders")
    def create_order():
        data = json_body()
        errors = {}
        name = str(data.get("customer_name", "")).strip()
        phone = re.sub(r"[\s-]", "", str(data.get("phone", "")))
        items = data.get("items")
        if not name:
            errors["customer_name"] = "Required"
        if not PHONE_RE.match(phone):
            errors["phone"] = "Use 10 to 13 digits, optionally starting with +"
        lines = []
        if not isinstance(items, list) or not items:
            errors["items"] = "Add at least one item"
        else:
            for i, item in enumerate(items):
                pid = item.get("product_id") if isinstance(item, dict) else None
                qty = item.get("qty", 1) if isinstance(item, dict) else None
                if pid not in products:
                    errors[f"items[{i}].product_id"] = "Unknown product"
                elif not isinstance(qty, int) or isinstance(qty, bool) or not 1 <= qty <= MAX_QTY:
                    errors[f"items[{i}].qty"] = f"Whole number from 1 to {MAX_QTY}"
                else:
                    p = products[pid]
                    lines.append({"product_id": pid, "name": p["name"], "qty": qty,
                                  "unit_price": p["price"], "line_total": p["price"] * qty})
        if errors:
            raise ApiError(422, "Order is not valid", errors)

        order = {
            "id": uuid.uuid4().hex[:8],
            "customer_name": name,
            "phone": phone,
            "items": lines,
            "total": sum(l["line_total"] for l in lines),
            "note": str(data.get("note", "")).strip()[:200],
            "status": "received",
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        text = "\n".join(
            [f"New order #{order['id']} from {name} ({phone})"]
            + [f"- {l['qty']} x {l['name']} = Rs {l['line_total']}" for l in lines]
            + [f"Total: Rs {order['total']}"]
            + ([f"Note: {order['note']}"] if order["note"] else [])
        )
        order["whatsapp_url"] = f"https://wa.me/{app.config['SHOP_WHATSAPP']}?text={quote(text)}"
        with lock:
            orders[order["id"]] = order
        return jsonify(order), 201

    @app.get("/api/orders/<order_id>")
    def get_order(order_id):
        if order_id not in orders:
            raise ApiError(404, f"No order with id {order_id}")
        return jsonify(orders[order_id])

    @app.get("/api/orders")
    def list_orders():
        require_admin()
        status = request.args.get("status")
        items = [o for o in orders.values() if not status or o["status"] == status]
        return jsonify({"count": len(items), "orders": items})

    @app.patch("/api/orders/<order_id>")
    def update_status(order_id):
        require_admin()
        if order_id not in orders:
            raise ApiError(404, f"No order with id {order_id}")
        new = json_body().get("status")
        if new not in STATUSES:
            raise ApiError(422, f"status must be one of {STATUSES}")
        with lock:
            order = orders[order_id]
            if new not in NEXT_STATUS[order["status"]]:
                raise ApiError(409, f"Can't move an order from {order['status']} to {new}")
            order["status"] = new
        return jsonify(order)

    return app
