from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from pathlib import Path
from urllib.parse import quote
import os

app = Flask(__name__)
app.secret_key = "change-this-to-a-long-random-secret-key"
DB_PATH = Path(__file__).with_name("orders.db")
# Replace with the vendor WhatsApp number, country code included, digits only.
# Example India: 919876543210 (no +, spaces, or dashes).
VENDOR_WHATSAPP = os.getenv("VENDOR_WHATSAPP", "9908849867")

PRODUCTS = [
    # Change these details to your own single product.
    {"id": 1, "name": "Royal Stag", "description": "A standard full bottle of Royal Stag whisky 750 ml", "price": 40, "emoji": "📦", "image": "/static/RSW.avif", "category": "Product"},
]
PRODUCT_BY_ID = {p["id"]: p for p in PRODUCTS}


def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    # The orders table intentionally has no delivery_fee column.
    # If an older project database still has that column, rebuild the table
    # and copy the existing order data into the fee-free schema.
    with connect_db() as conn:
        existing = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='orders'"
        ).fetchone()
        if existing:
            old_columns = [row[1] for row in conn.execute("PRAGMA table_info(orders)")]
        else:
            old_columns = []

        create_sql = """CREATE TABLE IF NOT EXISTS {table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT,
            address TEXT NOT NULL,
            notes TEXT,
            items_json TEXT NOT NULL,
            subtotal REAL NOT NULL,
            total REAL NOT NULL,
            payment_method TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""

        if "delivery_fee" in old_columns:
            conn.execute("DROP TABLE IF EXISTS orders_migrating")
            conn.execute(create_sql.format(table_name="orders_migrating"))
            allowed = [
                "id", "customer_name", "phone", "email", "address", "notes",
                "items_json", "subtotal", "total", "payment_method", "created_at"
            ]
            common = [column for column in allowed if column in old_columns]
            columns_sql = ", ".join(common)
            conn.execute(
                f"INSERT INTO orders_migrating ({columns_sql}) "
                f"SELECT {columns_sql} FROM orders"
            )
            conn.execute("DROP TABLE orders")
            conn.execute("ALTER TABLE orders_migrating RENAME TO orders")
        else:
            conn.execute(create_sql.format(table_name="orders"))


def cart_items():
    cart = session.get("cart", {})
    items = []
    subtotal = 0
    for product_id, quantity in cart.items():
        product = PRODUCT_BY_ID.get(int(product_id))
        quantity = int(quantity)
        if product and quantity > 0:
            line_total = product["price"] * quantity
            items.append({**product, "quantity": quantity, "line_total": line_total})
            subtotal += line_total
    return items, subtotal


@app.context_processor
def inject_cart_count():
    return {"cart_count": sum(int(q) for q in session.get("cart", {}).values())}


@app.route("/")
def home():
    # Single-product site: show the product details immediately when the link opens.
    return render_template("index.html", product=PRODUCTS[0])


@app.route("/product/<int:product_id>")
def product_detail(product_id):
    product = PRODUCT_BY_ID.get(product_id)
    if not product:
        return redirect(url_for("home"))
    return render_template("product.html", product=product)


@app.post("/order-now/<int:product_id>")
def order_now(product_id):
    product = PRODUCT_BY_ID.get(product_id)
    if not product:
        flash("That item is not available.", "error")
        return redirect(url_for("home"))
    try:
        quantity = max(1, min(int(request.form.get("quantity", "1")), 99))
    except (TypeError, ValueError):
        quantity = 1
    cart = session.get("cart", {})
    cart[str(product_id)] = quantity
    session["cart"] = cart
    return redirect(url_for("checkout"))


@app.post("/cart/add/<int:product_id>")
def add_to_cart(product_id):
    if product_id not in PRODUCT_BY_ID:
        flash("That item is not available.", "error")
        return redirect(url_for("home"))
    cart = session.get("cart", {})
    key = str(product_id)
    cart[key] = min(int(cart.get(key, 0)) + 1, 99)
    session["cart"] = cart
    flash(f'{PRODUCT_BY_ID[product_id]["name"]} added to your cart.', "success")
    return redirect(request.referrer or url_for("home"))


@app.route("/cart", methods=["GET", "POST"])
def cart():
    if request.method == "POST":
        cart = session.get("cart", {})
        for product_id in list(cart.keys()):
            raw = request.form.get(f"qty_{product_id}", "0")
            try:
                qty = max(0, min(int(raw), 99))
            except ValueError:
                qty = int(cart[product_id])
            if qty == 0:
                cart.pop(product_id, None)
            else:
                cart[product_id] = qty
        session["cart"] = cart
        flash("Cart updated.", "success")
        return redirect(url_for("cart"))
    items, subtotal = cart_items()
    return render_template("cart.html", items=items, subtotal=subtotal, total=subtotal)


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    items, subtotal = cart_items()
    if not items:
        flash("Your cart is empty. Add something delicious first!", "error")
        return redirect(url_for("home"))
    total = subtotal

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        address = request.form.get("address", "").strip()
        notes = request.form.get("notes", "").strip()
        payment_method = request.form.get("payment_method", "Cash on delivery")
        if not name or not phone or not address:
            flash("Please enter your name, phone number and delivery address.", "error")
            return render_template("checkout.html", items=items, subtotal=subtotal, total=total)
        if request.form.get("age_confirmed") != "yes":
            flash("Please confirm legal-age and local-law eligibility before ordering.", "error")
            return render_template("checkout.html", items=items, subtotal=subtotal, total=total)
        if payment_method not in ("Cash on delivery", "UPI on delivery"):
            payment_method = "Cash on delivery"

        import json
        order_items = [{"id": i["id"], "name": i["name"], "quantity": i["quantity"], "price": i["price"]} for i in items]
        with connect_db() as conn:
            cursor = conn.execute("""INSERT INTO orders
                (customer_name, phone, email, address, notes, items_json, subtotal, total, payment_method)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (name, phone, email, address, notes, json.dumps(order_items), subtotal, total, payment_method))
            order_id = cursor.lastrowid
        # Open WhatsApp with the complete order pre-filled for the vendor.
        # The customer must tap Send in WhatsApp; websites cannot silently send WhatsApp messages.
        message_lines = [
            f"NEW ORDER #{order_id}",
            f"Name: {name}",
            f"Phone: {phone}",
            f"Room number: {address}",
            f"Notes: {notes or '-'}",
        ]
        message_lines.extend([f"- {i['quantity']} x {i['name']} (₹{i['line_total']})" for i in items])
        message_lines.extend([f"TOTAL: AED {total}"])
        whatsapp_url = f"https://wa.me/{VENDOR_WHATSAPP}?text={quote(chr(10).join(message_lines))}"
        session["cart"] = {}
        return redirect(whatsapp_url)

    return render_template("checkout.html", items=items, subtotal=subtotal, total=total)


@app.route("/order/<int:order_id>")
def confirmation(order_id):
    with connect_db() as conn:
        order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        return redirect(url_for("home"))
    return render_template("confirmation.html", order=order)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
