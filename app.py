
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash
)

import sqlite3
import json
import os

from pathlib import Path
from urllib.parse import quote


# ==========================================
# FLASK APPLICATION CONFIGURATION
# ==========================================

app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY")

if not app.secret_key:
    raise RuntimeError(
        "SECRET_KEY environment variable is missing"
    )


# ==========================================
# DATABASE CONFIGURATION
# ==========================================

# Vercel temporary storage.
# Important: Database data is not guaranteed
# to persist across function instances.

DB_PATH = Path("/tmp/orders.db")


def connect_db():

    conn = sqlite3.connect(DB_PATH)

    conn.row_factory = sqlite3.Row

    return conn


def init_db():

    with connect_db() as conn:

        existing = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table' AND name='orders'
            """
        ).fetchone()

        if existing:

            old_columns = [
                row[1]
                for row in conn.execute(
                    "PRAGMA table_info(orders)"
                )
            ]

        else:

            old_columns = []


        create_sql = """
        CREATE TABLE IF NOT EXISTS {table_name} (

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

        )
        """


        # Migrate an older database schema if necessary.

        if "delivery_fee" in old_columns:

            conn.execute(
                "DROP TABLE IF EXISTS orders_migrating"
            )

            conn.execute(
                create_sql.format(
                    table_name="orders_migrating"
                )
            )

            allowed = [
                "id",
                "customer_name",
                "phone",
                "email",
                "address",
                "notes",
                "items_json",
                "subtotal",
                "total",
                "payment_method",
                "created_at"
            ]

            common = [
                column
                for column in allowed
                if column in old_columns
            ]

            columns_sql = ", ".join(common)

            conn.execute(
                f"""
                INSERT INTO orders_migrating ({columns_sql})
                SELECT {columns_sql}
                FROM orders
                """
            )

            conn.execute("DROP TABLE orders")

            conn.execute(
                """
                ALTER TABLE orders_migrating
                RENAME TO orders
                """
            )

        else:

            conn.execute(
                create_sql.format(
                    table_name="orders"
                )
            )


# Initialize database when application loads.
init_db()


# ==========================================
# WHATSAPP CONFIGURATION
# ==========================================

VENDOR_WHATSAPP = os.getenv(
    "VENDOR_WHATSAPP",
    "919908849867"
)


# ==========================================
# PRODUCT CONFIGURATION
# ==========================================

PRODUCTS = [

    {
        "id": 1,

        "name": "Royal Stag",

        "description": (
            "A standard full bottle of Royal Stag "
            "whisky 750 ml"
        ),

        "price": 40,

        "emoji": "📦",

        "image": "/RSW.avif",

        "category": "Product"
    }

]


PRODUCT_BY_ID = {
    product["id"]: product
    for product in PRODUCTS
}


# ==========================================
# SHOPPING CART FUNCTIONS
# ==========================================

def cart_items():

    cart = session.get("cart", {})

    items = []

    subtotal = 0

    for product_id, quantity in cart.items():

        try:

            product = PRODUCT_BY_ID.get(
                int(product_id)
            )

            quantity = int(quantity)

        except (ValueError, TypeError):

            continue

        if product and quantity > 0:

            line_total = product["price"] * quantity

            items.append({

                **product,

                "quantity": quantity,

                "line_total": line_total

            })

            subtotal += line_total

    return items, subtotal


# ==========================================
# CART COUNT
# ==========================================

@app.context_processor
def inject_cart_count():

    cart = session.get("cart", {})

    count = 0

    for quantity in cart.values():

        try:

            count += max(0, int(quantity))

        except (ValueError, TypeError):

            continue

    return {
        "cart_count": count
    }


# ==========================================
# HOME PAGE
# ==========================================

@app.route("/")
def home():

    return render_template(
        "index.html",
        product=PRODUCTS[0]
    )


# ==========================================
# PRODUCT DETAILS
# ==========================================

@app.route("/product/<int:product_id>")
def product_detail(product_id):

    product = PRODUCT_BY_ID.get(product_id)

    if not product:

        return redirect(
            url_for("home")
        )

    return render_template(
        "product.html",
        product=product
    )


# ==========================================
# ORDER NOW
# ==========================================

@app.post("/order-now/<int:product_id>")
def order_now(product_id):

    product = PRODUCT_BY_ID.get(product_id)

    if not product:

        flash(
            "That item is not available.",
            "error"
        )

        return redirect(
            url_for("home")
        )

    try:

        quantity = max(
            1,
            min(
                int(request.form.get("quantity", "1")),
                99
            )
        )

    except (TypeError, ValueError):

        quantity = 1

    cart = session.get("cart", {})

    cart[str(product_id)] = quantity

    session["cart"] = cart

    return redirect(
        url_for("checkout")
    )


# ==========================================
# ADD TO CART
# ==========================================

@app.post("/cart/add/<int:product_id>")
def add_to_cart(product_id):

    if product_id not in PRODUCT_BY_ID:

        flash(
            "That item is not available.",
            "error"
        )

        return redirect(
            url_for("home")
        )

    cart = session.get("cart", {})

    key = str(product_id)

    cart[key] = min(
        int(cart.get(key, 0)) + 1,
        99
    )

    session["cart"] = cart

    flash(
        f'{PRODUCT_BY_ID[product_id]["name"]} added to your cart.',
        "success"
    )

    return redirect(
        request.referrer or url_for("home")
    )


# ==========================================
# CART PAGE
# ==========================================

@app.route("/cart", methods=["GET", "POST"])
def cart():

    if request.method == "POST":

        cart = session.get("cart", {})

        for product_id in list(cart.keys()):

            raw = request.form.get(
                f"qty_{product_id}",
                "0"
            )

            try:

                qty = max(
                    0,
                    min(int(raw), 99)
                )

            except (ValueError, TypeError):

                qty = int(cart[product_id])

            if qty == 0:

                cart.pop(product_id, None)

            else:

                cart[product_id] = qty

        session["cart"] = cart

        flash(
            "Cart updated.",
            "success"
        )

        return redirect(
            url_for("cart")
        )

    items, subtotal = cart_items()

    return render_template(
        "cart.html",
        items=items,
        subtotal=subtotal,
        total=subtotal
    )


# ==========================================
# CHECKOUT PAGE
# ==========================================

@app.route("/checkout", methods=["GET", "POST"])
def checkout():

    items, subtotal = cart_items()

    if not items:

        flash(
            "Your cart is empty. Add something delicious first!",
            "error"
        )

        return redirect(
            url_for("home")
        )

    total = subtotal

    if request.method == "POST":

        name = request.form.get(
            "name", ""
        ).strip()

        phone = request.form.get(
            "phone", ""
        ).strip()

        email = request.form.get(
            "email", ""
        ).strip()

        address = request.form.get(
            "address", ""
        ).strip()

        notes = request.form.get(
            "notes", ""
        ).strip()

        payment_method = request.form.get(
            "payment_method",
            "Cash on delivery"
        )


        # Validate customer information.

        if not name or not phone or not address:

            flash(
                "Please enter your name, phone number and delivery address.",
                "error"
            )

            return render_template(
                "checkout.html",
                items=items,
                subtotal=subtotal,
                total=total
            )


        # Validate age confirmation.

        if request.form.get("age_confirmed") != "yes":

            flash(
                "Please confirm legal-age and local-law eligibility before ordering.",
                "error"
            )

            return render_template(
                "checkout.html",
                items=items,
                subtotal=subtotal,
                total=total
            )


        # Validate payment method.

        if payment_method not in (
            "Cash on delivery",
            "UPI on delivery"
        ):

            payment_method = "Cash on delivery"


        # Prepare order details.

        order_items = [

            {
                "id": item["id"],

                "name": item["name"],

                "quantity": item["quantity"],

                "price": item["price"]
            }

            for item in items

        ]


        # Save order in SQLite.

        with connect_db() as conn:

            cursor = conn.execute(
                """
                INSERT INTO orders
                (
                    customer_name,
                    phone,
                    email,
                    address,
                    notes,
                    items_json,
                    subtotal,
                    total,
                    payment_method
                )

                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,

                (
                    name,
                    phone,
                    email,
                    address,
                    notes,
                    json.dumps(order_items),
                    subtotal,
                    total,
                    payment_method
                )

            )

            order_id = cursor.lastrowid


        # Prepare WhatsApp order message.

        message_lines = [

            f"NEW ORDER #{order_id}",

            f"Name: {name}",

            f"Phone: {phone}",

            f"Room number: {address}",

            f"Notes: {notes or '-'}"

        ]


        message_lines.extend(

            [
                f"- {item['quantity']} x "
                f"{item['name']} (₹{item['line_total']})"

                for item in items
            ]

        )


        message_lines.append(
            f"TOTAL: AED {total}"
        )


        whatsapp_url = (

            f"https://wa.me/{VENDOR_WHATSAPP}"

            f"?text={quote(chr(10).join(message_lines))}"

        )


        # Clear cart after successful order.

        session["cart"] = {}

        return redirect(
            whatsapp_url
        )


    return render_template(
        "checkout.html",
        items=items,
        subtotal=subtotal,
        total=total
    )


# ==========================================
# ORDER CONFIRMATION
# ==========================================

@app.route("/order/<int:order_id>")
def confirmation(order_id):

    with connect_db() as conn:

        order = conn.execute(
            """
            SELECT *
            FROM orders
            WHERE id = ?
            """,

            (order_id,)

        ).fetchone()


    if not order:

        return redirect(
            url_for("home")
        )


    return render_template(
        "confirmation.html",
        order=order
    )


# ==========================================
# APPLICATION START
# ==========================================

if __name__ == "__main__":

    app.run(
        debug=False
    )
