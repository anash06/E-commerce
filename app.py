import os
import sqlite3
from datetime import datetime
from urllib.parse import quote
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, make_response, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from openpyxl import Workbook

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "mgm_store_secret_key")

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
IS_VERCEL = bool(os.environ.get("VERCEL"))
DB_BASE = "/tmp" if IS_VERCEL else BASE_DIR
DB_PATH = os.path.join(DB_BASE, "mgm_store.db")
EXCEL_DIR = os.path.join("/tmp" if IS_VERCEL else BASE_DIR, "excel")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            phone TEXT UNIQUE,
            password_hash TEXT,
            role TEXT,
            created_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            price REAL,
            stock INTEGER,
            created_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            status TEXT,
            total REAL,
            created_at TEXT,
            shipping_address TEXT,
            FOREIGN KEY(customer_id) REFERENCES users(id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            price REAL,
            FOREIGN KEY(order_id) REFERENCES orders(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            amount REAL,
            method TEXT,
            status TEXT,
            transaction_id TEXT,
            paid_at TEXT,
            FOREIGN KEY(order_id) REFERENCES orders(id)
        )
    """)
    conn.commit()
    cur.execute("PRAGMA table_info(orders)")
    cols = [r[1] for r in cur.fetchall()]
    if "shipping_address" not in cols:
        cur.execute("ALTER TABLE orders ADD COLUMN shipping_address TEXT")
        conn.commit()
    # detailed address columns
    for col in ["door_no","street","landmark","place","district","state","alt_mobile","pincode"]:
        if col not in cols:
            cur.execute(f"ALTER TABLE orders ADD COLUMN {col} TEXT")
            conn.commit()
    cur.execute("PRAGMA table_info(products)")
    pcols = [r[1] for r in cur.fetchall()]
    if "image_url" not in pcols:
        cur.execute("ALTER TABLE products ADD COLUMN image_url TEXT")
        conn.commit()
    cur.execute("PRAGMA table_info(payments)")
    paycols = [r[1] for r in cur.fetchall()]
    if "notes" not in paycols:
        cur.execute("ALTER TABLE payments ADD COLUMN notes TEXT")
        conn.commit()
    cur.execute("SELECT id FROM users WHERE role=?", ("admin",))
    admin = cur.fetchone()
    if not admin:
        cur.execute(
            "INSERT INTO users (name, email, phone, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                "Admin",
                "admin@mgmstore.com",
                "0000000000",
                generate_password_hash("admin123"),
                "admin",
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
    if not os.path.exists(EXCEL_DIR):
        os.makedirs(EXCEL_DIR, exist_ok=True)
    cur.execute("SELECT COUNT(*) FROM products")
    pcnt = cur.fetchone()[0]
    if pcnt == 0:
        t_img = "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0nMjAwJyBoZWlnaHQ9JzE2MCcgdmlld0JveD0nMCAwIDIwMCAxNjAnIHhtbG5zPSdodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2Zyc+PHJlY3Qgd2lkdGg9JzIwMCcgaGVpZ2h0PScxNjAnIGZpbGw9JyNjMjE4NWInLz48dGV4dCB4PScxMDAnIHk9JzcwJyBmb250LXNpemU9JzIwJyBmaWxsPScjZmZmJyB0ZXh0LWFuY2hvcj0nY2VudGVyJz5ULVNIRVJUPC90ZXh0Pjwvc3ZnPg=="
        j_img = "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0nMjAwJyBoZWlnaHQ9JzE2MCcgdmlld0JveD0nMCAwIDIwMCAxNjAnIHhtbG5zPSdodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2Zyc+PHJlY3Qgd2lkdGg9JzIwMCcgaGVpZ2h0PScxNjAnIGZpbGw9JyM0OTQ5NDknLz48dGV4dCB4PScxMDAnIHk9JzcwJyBmb250LXNpemU9JzIwJyBmaWxsPScjZmZmJyB0ZXh0LWFuY2hvcj0nY2VudGVyJz5KRUFOUzwvdGV4dD48L3N2Zz4="
        k_img = "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0nMjAwJyBoZWlnaHQ9JzE2MCcgdmlld0JveD0nMCAwIDIwMCAxNjAnIHhtbG5zPSdodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2Zyc+PHJlY3Qgd2lkdGg9JzIwMCcgaGVpZ2h0PScxNjAnIGZpbGw9JyM5ODI4N2MnLz48dGV4dCB4PScxMDAnIHk9JzcwJyBmb250LXNpemU9JzIwJyBmaWxsPScjZmZmJyB0ZXh0LWFuY2hvcj0nY2VudGVyJz5LVVJUQTwvdGV4dD48L3N2Zz4="
        s_img = "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0nMjAwJyBoZWlnaHQ9JzE2MCcgdmlld0JveD0nMCAwIDIwMCAxNjAnIHhtbG5zPSdodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2Zyc+PHJlY3Qgd2lkdGg9JzIwMCcgaGVpZ2h0PScxNjAnIGZpbGw9JyNmZjQwOGQnLz48dGV4dCB4PScxMDAnIHk9JzcwJyBmb250LXNpemU9JzIwJyBmaWxsPScjZmZmJyB0ZXh0LWFuY2hvcj0nY2VudGVyJz5TQVJFRTwvdGV4dD48L3N2Zz4="
        cur.execute("INSERT INTO products (name, description, price, stock, created_at, image_url) VALUES (?, ?, ?, ?, ?, ?)", ("Classic T-Shirt", "Cotton t-shirt", 499.0, 50, datetime.utcnow().isoformat(), t_img))
        cur.execute("INSERT INTO products (name, description, price, stock, created_at, image_url) VALUES (?, ?, ?, ?, ?, ?)", ("Denim Jeans", "Blue slim fit", 1299.0, 30, datetime.utcnow().isoformat(), j_img))
        cur.execute("INSERT INTO products (name, description, price, stock, created_at, image_url) VALUES (?, ?, ?, ?, ?, ?)", ("Men Kurta", "Festive wear", 999.0, 20, datetime.utcnow().isoformat(), k_img))
        cur.execute("INSERT INTO products (name, description, price, stock, created_at, image_url) VALUES (?, ?, ?, ?, ?, ?)", ("Silk Saree", "Traditional saree", 2499.0, 15, datetime.utcnow().isoformat(), s_img))
        conn.commit()
    conn.close()

def export_table_to_excel(table_name, file_name):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {table_name}")
    rows = cur.fetchall()
    wb = Workbook()
    ws = wb.active
    ws.title = table_name
    if rows:
        ws.append(rows[0].keys())
        for r in rows:
            ws.append([r[k] for k in r.keys()])
    else:
        ws.append(["no_data"])
    path = os.path.join(EXCEL_DIR, file_name)
    wb.save(path)
    conn.close()
    return path

def sync_excel_all():
    export_table_to_excel("products", "products.xlsx")
    export_table_to_excel("users", "customers.xlsx")
    export_table_to_excel("orders", "orders.xlsx")

def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id=?", (uid,))
    u = cur.fetchone()
    conn.close()
    return u

def require_role(role):
    u = current_user()
    return u and u["role"] == role

@app.context_processor
def inject_user():
    return {"user": current_user()}

def get_cart():
    c = session.get("cart") or {}
    return {int(k): int(v) for k, v in c.items()}

def save_cart(cart):
    session["cart"] = {str(k): int(v) for k, v in cart.items()}

def clear_cart():
    session["cart"] = {}

@app.before_request
def ensure_db():
    init_db()

@app.route("/")
def index():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM products ORDER BY id DESC")
    products = cur.fetchall()
    conn.close()
    return render_template("index.html", products=products)

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        password = request.form.get("password")
        if not email and not phone:
            flash("Provide email or phone")
            return redirect(url_for("signup"))
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO users (name, email, phone, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    name,
                    email,
                    phone,
                    generate_password_hash(password),
                    "customer",
                    datetime.utcnow().isoformat(),
                ),
            )
            conn.commit()
            sync_excel_all()
            flash("Signup successful")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email or phone already exists")
            return redirect(url_for("signup"))
        finally:
            conn.close()
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identity = request.form.get("identity")
        password = request.form.get("password")
        conn = get_db()
        cur = conn.cursor()
        if "@" in identity:
            cur.execute("SELECT * FROM users WHERE email=?", (identity,))
        else:
            cur.execute("SELECT * FROM users WHERE phone=?", (identity,))
        u = cur.fetchone()
        conn.close()
        if u and check_password_hash(u["password_hash"], password) and u["role"] == "customer":
            session["user_id"] = u["id"]
            flash("Logged in")
            return redirect(url_for("index"))
        flash("Invalid credentials")
        return redirect(url_for("login"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out")
    return redirect(url_for("index"))

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        identity = request.form.get("identity")
        password = request.form.get("password")
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email=? OR phone=?", (identity, identity))
        u = cur.fetchone()
        conn.close()
        if u and check_password_hash(u["password_hash"], password) and u["role"] == "admin":
            session["user_id"] = u["id"]
            flash("Admin logged in")
            return redirect(url_for("admin_dashboard"))
        flash("Invalid admin credentials")
        return redirect(url_for("admin_login"))
    return render_template("admin_login.html")

@app.route("/admin")
def admin_dashboard():
    if not require_role("admin"):
        return redirect(url_for("admin_login"))
    return render_template("admin_dashboard.html")

@app.route("/admin/products")
def admin_products():
    if not require_role("admin"):
        return redirect(url_for("admin_login"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM products ORDER BY id DESC")
    products = cur.fetchall()
    conn.close()
    return render_template("products_list.html", products=products)

@app.route("/admin/products/new", methods=["GET", "POST"])
def admin_products_new():
    if not require_role("admin"):
        return redirect(url_for("admin_login"))
    if request.method == "POST":
        name = request.form.get("name")
        description = request.form.get("description")
        price = float(request.form.get("price"))
        stock = int(request.form.get("stock"))
        image_url = request.form.get("image_url")
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO products (name, description, price, stock, created_at, image_url) VALUES (?, ?, ?, ?, ?, ?)",
            (name, description, price, stock, datetime.utcnow().isoformat(), image_url),
        )
        conn.commit()
        conn.close()
        sync_excel_all()
        flash("Product created")
        return redirect(url_for("admin_products"))
    return render_template("product_form.html", product=None)

@app.route("/admin/products/<int:pid>/edit", methods=["GET", "POST"])
def admin_products_edit(pid):
    if not require_role("admin"):
        return redirect(url_for("admin_login"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM products WHERE id=?", (pid,))
    product = cur.fetchone()
    if request.method == "POST":
        name = request.form.get("name")
        description = request.form.get("description")
        price = float(request.form.get("price"))
        stock = int(request.form.get("stock"))
        image_url = request.form.get("image_url")
        cur.execute(
            "UPDATE products SET name=?, description=?, price=?, stock=?, image_url=? WHERE id=?",
            (name, description, price, stock, image_url, pid),
        )
        conn.commit()
        conn.close()
        sync_excel_all()
        flash("Product updated")
        return redirect(url_for("admin_products"))
    conn.close()
    return render_template("product_form.html", product=product)

@app.route("/admin/products/<int:pid>/delete", methods=["POST"])
def admin_products_delete(pid):
    if not require_role("admin"):
        return redirect(url_for("admin_login"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    sync_excel_all()
    flash("Product deleted")
    return redirect(url_for("admin_products"))

@app.route("/admin/customers")
def admin_customers():
    if not require_role("admin"):
        return redirect(url_for("admin_login"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE role='customer' ORDER BY id DESC")
    customers = cur.fetchall()
    conn.close()
    return render_template("customers_list.html", customers=customers)

@app.route("/admin/customers/new", methods=["GET", "POST"])
def admin_customers_new():
    if not require_role("admin"):
        return redirect(url_for("admin_login"))
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        password = request.form.get("password")
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO users (name, email, phone, password_hash, role, created_at) VALUES (?, ?, ?, ?, 'customer', ?)",
                (name, email, phone, generate_password_hash(password), datetime.utcnow().isoformat()),
            )
            conn.commit()
            sync_excel_all()
            flash("Customer created")
        except sqlite3.IntegrityError:
            flash("Email or phone already exists")
        finally:
            conn.close()
        return redirect(url_for("admin_customers"))
    return render_template("customer_form.html", customer=None)

@app.route("/admin/customers/<int:cid>/edit", methods=["GET", "POST"])
def admin_customers_edit(cid):
    if not require_role("admin"):
        return redirect(url_for("admin_login"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id=?", (cid,))
    customer = cur.fetchone()
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        cur.execute(
            "UPDATE users SET name=?, email=?, phone=? WHERE id=?",
            (name, email, phone, cid),
        )
        conn.commit()
        conn.close()
        sync_excel_all()
        flash("Customer updated")
        return redirect(url_for("admin_customers"))
    conn.close()
    return render_template("customer_form.html", customer=customer)

@app.route("/admin/customers/<int:cid>/delete", methods=["POST"])
def admin_customers_delete(cid):
    if not require_role("admin"):
        return redirect(url_for("admin_login"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    sync_excel_all()
    flash("Customer deleted")
    return redirect(url_for("admin_customers"))

@app.route("/admin/orders")
def admin_orders():
    if not require_role("admin"):
        return redirect(url_for("admin_login"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT o.*, u.name as customer_name, p.transaction_id as payment_txn, p.status as payment_status
        FROM orders o
        LEFT JOIN users u ON u.id = o.customer_id
        LEFT JOIN payments p ON p.order_id = o.id AND p.id = (
            SELECT MAX(id) FROM payments WHERE order_id = o.id
        )
        ORDER BY o.id DESC
    """)
    orders = cur.fetchall()
    conn.close()
    return render_template("orders_list.html", orders=orders)

@app.route("/admin/orders/<int:oid>/dispatch", methods=["POST"])
def admin_order_dispatch(oid):
    if not require_role("admin"):
        return redirect(url_for("admin_login"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE orders SET status='dispatched' WHERE id=?", (oid,))
    conn.commit()
    conn.close()
    flash("Order dispatched")
    return redirect(url_for("admin_orders"))

@app.route("/admin/orders/<int:oid>/confirm", methods=["POST"])
def admin_order_confirm(oid):
    if not require_role("admin"):
        return redirect(url_for("admin_login"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE id=?", (oid,))
    order = cur.fetchone()
    cur.execute("SELECT * FROM payments WHERE order_id=? ORDER BY id DESC", (oid,))
    payment = cur.fetchone()
    if payment:
        cur.execute("UPDATE payments SET status='success', paid_at=? WHERE id=?", (datetime.utcnow().isoformat(), payment["id"]))
    else:
        cur.execute(
            "INSERT INTO payments (order_id, amount, method, status, transaction_id, paid_at) VALUES (?, ?, 'upi', 'success', ?, ?)",
            (oid, order["total"], f"ADMINCONF{int(datetime.utcnow().timestamp())}{oid}", datetime.utcnow().isoformat()),
        )
    cur.execute("UPDATE orders SET status='confirmed' WHERE id=?", (oid,))
    conn.commit()
    conn.close()
    sync_excel_all()
    flash("Order confirmed")
    return redirect(url_for("admin_orders"))

@app.route("/admin/orders/<int:oid>/reject", methods=["POST"])
def admin_order_reject(oid):
    if not require_role("admin"):
        return redirect(url_for("admin_login"))
    notes = request.form.get("notes") or ""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE id=?", (oid,))
    order = cur.fetchone()
    cur.execute("SELECT * FROM payments WHERE order_id=? ORDER BY id DESC", (oid,))
    payment = cur.fetchone()
    if payment:
        cur.execute("UPDATE payments SET status='failed', notes=?, paid_at=? WHERE id=?", (notes, datetime.utcnow().isoformat(), payment["id"]))
    else:
        cur.execute(
            "INSERT INTO payments (order_id, amount, method, status, transaction_id, paid_at, notes) VALUES (?, ?, 'upi', 'failed', ?, ?, ?)",
            (oid, order["total"], f"ADMINREJ{int(datetime.utcnow().timestamp())}{oid}", datetime.utcnow().isoformat(), notes),
        )
    cur.execute("UPDATE orders SET status='cancelled' WHERE id=?", (oid,))
    conn.commit()
    conn.close()
    sync_excel_all()
    flash("Order rejected")
    return redirect(url_for("admin_orders"))

@app.route("/admin/orders/new", methods=["GET", "POST"])
def admin_orders_new():
    if not require_role("admin"):
        return redirect(url_for("admin_login"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM users WHERE role='customer'")
    customers = cur.fetchall()
    cur.execute("SELECT * FROM products")
    products = cur.fetchall()
    if request.method == "POST":
        customer_id = int(request.form.get("customer_id"))
        door_no = request.form.get("door_no")
        street = request.form.get("street")
        landmark = request.form.get("landmark")
        place = request.form.get("place")
        district = request.form.get("district")
        state = request.form.get("state")
        alt_mobile = request.form.get("alt_mobile")
        pincode = request.form.get("pincode")
        shipping_address = ", ".join(filter(None, [door_no, street, landmark, place, district, state])) + (f" - {pincode}" if pincode else "")
        items = []
        for p in products:
            q = request.form.get(f"qty_{p['id']}")
            if q and int(q) > 0:
                items.append((p["id"], int(q), p["price"]))
        if not items:
            flash("Add at least one item")
            return redirect(url_for("admin_orders_new"))
        total = sum(q * price for _, q, price in items)
        cur.execute(
            "INSERT INTO orders (customer_id, status, total, created_at, shipping_address, door_no, street, landmark, place, district, state, alt_mobile, pincode) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (customer_id, "pending", total, datetime.utcnow().isoformat(), shipping_address, door_no, street, landmark, place, district, state, alt_mobile, pincode),
        )
        oid = cur.lastrowid
        for pid, qty, price in items:
            cur.execute(
                "INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
                (oid, pid, qty, price),
            )
            cur.execute("UPDATE products SET stock = stock - ? WHERE id=?", (qty, pid))
        conn.commit()
        conn.close()
        sync_excel_all()
        flash("Order created")
        return redirect(url_for("admin_orders"))
    conn.close()
    return render_template("order_create.html", customers=customers, products=products)

@app.route("/product/<int:pid>")
def product_detail(pid):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM products WHERE id=?", (pid,))
    product = cur.fetchone()
    conn.close()
    return render_template("product_detail.html", product=product)

@app.route("/order/create", methods=["POST"])
def create_order():
    u = current_user()
    if not u:
        flash("Please signup to place an order")
        return redirect(url_for("signup"))
    pid = int(request.form.get("product_id"))
    qty = int(request.form.get("quantity"))
    door_no = request.form.get("door_no")
    street = request.form.get("street")
    landmark = request.form.get("landmark")
    place = request.form.get("place")
    district = request.form.get("district")
    state = request.form.get("state")
    alt_mobile = request.form.get("alt_mobile")
    pincode = request.form.get("pincode")
    shipping_address = ", ".join(filter(None, [door_no, street, landmark, place, district, state])) + (f" - {pincode}" if pincode else "")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM products WHERE id=?", (pid,))
    p = cur.fetchone()
    if not p or qty <= 0 or p["stock"] < qty:
        flash("Invalid quantity")
        conn.close()
        return redirect(url_for("product_detail", pid=pid))
    total = p["price"] * qty
    cur.execute(
        "INSERT INTO orders (customer_id, status, total, created_at, shipping_address, door_no, street, landmark, place, district, state, alt_mobile, pincode) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (u["id"], "pending", total, datetime.utcnow().isoformat(), shipping_address, door_no, street, landmark, place, district, state, alt_mobile, pincode),
    )
    oid = cur.lastrowid
    cur.execute(
        "INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
        (oid, pid, qty, p["price"]),
    )
    cur.execute("UPDATE products SET stock = stock - ? WHERE id=?", (qty, pid))
    conn.commit()
    conn.close()
    sync_excel_all()
    flash("Order created")
    return redirect(url_for("invoice", oid=oid))

@app.route("/order/<int:oid>/invoice")
def invoice(oid):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE id=?", (oid,))
    order = cur.fetchone()
    cur.execute("SELECT * FROM users WHERE id=?", (order["customer_id"],))
    customer = cur.fetchone()
    cur.execute("""
        SELECT oi.*, p.name FROM order_items oi
        LEFT JOIN products p ON p.id = oi.product_id
        WHERE oi.order_id=?
    """, (oid,))
    items = cur.fetchall()
    conn.close()
    return render_template("invoice.html", order=order, customer=customer, items=items)

@app.route("/order/<int:oid>/invoice/download")
def invoice_download(oid):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE id=?", (oid,))
    order = cur.fetchone()
    cur.execute("SELECT * FROM users WHERE id=?", (order["customer_id"],))
    customer = cur.fetchone()
    cur.execute("""
        SELECT oi.*, p.name FROM order_items oi
        LEFT JOIN products p ON p.id = oi.product_id
        WHERE oi.order_id=?
    """, (oid,))
    items = cur.fetchall()
    conn.close()
    html = render_template("invoice.html", order=order, customer=customer, items=items)
    resp = make_response(html)
    resp.headers["Content-Type"] = "text/html"
    resp.headers["Content-Disposition"] = f"attachment; filename=invoice-{oid}.html"
    return resp

@app.route("/order/<int:oid>/pay", methods=["GET", "POST"])
def pay_order(oid):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE id=?", (oid,))
    order = cur.fetchone()
    if request.method == "POST":
        method = "upi"
        transaction_ref = request.form.get("transaction_ref")
        if not transaction_ref:
            conn.close()
            flash("Enter transaction reference")
            return redirect(url_for("pay_order", oid=oid))
        cur.execute(
            "INSERT INTO payments (order_id, amount, method, status, transaction_id, paid_at) VALUES (?, ?, ?, ?, ?, ?)",
            (oid, order["total"], method, "submitted", transaction_ref, datetime.utcnow().isoformat()),
        )
        cur.execute("UPDATE orders SET status='pending' WHERE id=?", (oid,))
        msg = "Payment submitted. Pending admin confirmation."
        conn.commit()
        conn.close()
        sync_excel_all()
        flash(msg)
        return redirect(url_for("invoice", oid=oid))
    upi_uri = f"upi://pay?pa=7418304663@upi&pn=MGM%20Cloths&am={order['total']}&cu=INR&tn=Order%20{oid}"
    qr_data = quote(upi_uri, safe="")
    conn.close()
    return render_template("pay.html", order=order, upi_uri=upi_uri, qr_data=qr_data)


@app.route("/admin/sales-report")
def sales_report():
    if not require_role("admin"):
        return redirect(url_for("admin_login"))
    d = request.args.get("date")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT date(created_at) as d, COUNT(*) as orders, SUM(total) as revenue FROM orders GROUP BY date(created_at) ORDER BY d DESC LIMIT 7")
    summary = cur.fetchall()
    selected = d or (summary[0]["d"] if summary else None)
    orders = []
    if selected:
        cur.execute(
            """
            SELECT o.*, u.name AS customer_name,
                   (
                     SELECT GROUP_CONCAT(p.name, ', ')
                     FROM order_items oi
                     LEFT JOIN products p ON p.id = oi.product_id
                     WHERE oi.order_id = o.id
                   ) AS product_names
            FROM orders o
            LEFT JOIN users u ON u.id = o.customer_id
            WHERE date(o.created_at) = ?
            ORDER BY o.id DESC
            """,
            (selected,),
        )
        orders = cur.fetchall()
    conn.close()
    return render_template("sales_report.html", summary=summary, selected=selected, orders=orders)

@app.route("/excel/export/all")
def export_all_excel():
    if not require_role("admin"):
        return redirect(url_for("admin_login"))
    sync_excel_all()
    flash("Excel files updated")
    return redirect(url_for("admin_dashboard"))

@app.route("/cart")
def view_cart():
    cart = get_cart()
    if not cart:
        return render_template("cart.html", items=[], total=0)
    conn = get_db()
    cur = conn.cursor()
    items = []
    total = 0
    for pid, qty in cart.items():
        cur.execute("SELECT id, name, price, stock FROM products WHERE id=?", (pid,))
        p = cur.fetchone()
        if p:
            subtotal = p["price"] * qty
            total += subtotal
            items.append({"id": p["id"], "name": p["name"], "price": p["price"], "stock": p["stock"], "qty": qty, "subtotal": subtotal})
    conn.close()
    return render_template("cart.html", items=items, total=total)

@app.route("/cart/add", methods=["POST"])
def cart_add():
    pid = int(request.form.get("product_id"))
    qty = int(request.form.get("quantity") or 1)
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, stock FROM products WHERE id=?", (pid,))
    p = cur.fetchone()
    conn.close()
    if not p or qty <= 0:
        flash("Invalid product")
        return redirect(url_for("index"))
    cart = get_cart()
    new_qty = qty + cart.get(pid, 0)
    cart[pid] = new_qty
    save_cart(cart)
    flash("Added to cart")
    return redirect(url_for("view_cart"))

@app.route("/cart/remove", methods=["POST"])
def cart_remove():
    pid = int(request.form.get("product_id"))
    cart = get_cart()
    if pid in cart:
        del cart[pid]
        save_cart(cart)
        flash("Removed from cart")
    return redirect(url_for("view_cart"))

@app.route("/cart/clear", methods=["POST"])
def cart_clear():
    clear_cart()
    flash("Cart cleared")
    return redirect(url_for("view_cart"))

@app.route("/cart/checkout", methods=["POST"])
def cart_checkout():
    u = current_user()
    cart = get_cart()
    if not cart:
        flash("Cart is empty")
        return redirect(url_for("view_cart"))
    if not u:
        flash("Please signup to checkout")
        return redirect(url_for("signup"))
    door_no = request.form.get("door_no")
    street = request.form.get("street")
    landmark = request.form.get("landmark")
    place = request.form.get("place")
    district = request.form.get("district")
    state = request.form.get("state")
    alt_mobile = request.form.get("alt_mobile")
    pincode = request.form.get("pincode")
    shipping_address = ", ".join(filter(None, [door_no, street, landmark, place, district, state])) + (f" - {pincode}" if pincode else "")
    conn = get_db()
    cur = conn.cursor()
    items = []
    total = 0
    for pid, qty in cart.items():
        cur.execute("SELECT id, price, stock FROM products WHERE id=?", (pid,))
        p = cur.fetchone()
        if not p or p["stock"] < qty:
            conn.close()
            flash("Insufficient stock for some items")
            return redirect(url_for("view_cart"))
        subtotal = p["price"] * qty
        total += subtotal
        items.append((pid, qty, p["price"]))
    cur.execute(
        "INSERT INTO orders (customer_id, status, total, created_at, shipping_address, door_no, street, landmark, place, district, state, alt_mobile, pincode) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (u["id"], "pending", total, datetime.utcnow().isoformat(), shipping_address, door_no, street, landmark, place, district, state, alt_mobile, pincode),
    )
    oid = cur.lastrowid
    for pid, qty, price in items:
        cur.execute(
            "INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
            (oid, pid, qty, price),
        )
        cur.execute("UPDATE products SET stock = stock - ? WHERE id=?", (qty, pid))
    conn.commit()
    conn.close()
    clear_cart()
    sync_excel_all()
    flash("Order placed. Please complete payment.")
    return redirect(url_for("pay_order", oid=oid))

@app.route("/my-orders")
def my_orders():
    u = current_user()
    if not u:
        flash("Login required")
        return redirect(url_for("login"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE customer_id=? ORDER BY id DESC", (u["id"],))
    orders = cur.fetchall()
    conn.close()
    return render_template("my_orders.html", orders=orders)

@app.route("/contact")
def contact():
    return render_template("contact.html")

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
@app.route("/admin/orders/<int:oid>/verify", methods=["POST"])
def admin_order_verify(oid):
    if not require_role("admin"):
        return redirect(url_for("admin_login"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE id=?", (oid,))
    order = cur.fetchone()
    cur.execute("SELECT * FROM payments WHERE order_id=? ORDER BY id DESC", (oid,))
    payment = cur.fetchone()
    action = request.form.get("action")
    notes = request.form.get("notes") or ""
    if action == "confirm":
        cur.execute("UPDATE payments SET status='success', paid_at=?, notes=? WHERE id=?", (datetime.utcnow().isoformat(), notes, payment["id"]))
        cur.execute("UPDATE orders SET status='confirmed' WHERE id=?", (oid,))
        flash("Payment confirmed. Order marked as confirmed.")
    elif action == "reject":
        cur.execute("UPDATE payments SET status='failed', paid_at=?, notes=? WHERE id=?", (datetime.utcnow().isoformat(), notes, payment["id"]))
        cur.execute("UPDATE orders SET status='cancelled' WHERE id=?", (oid,))
        flash("Payment rejected. Order cancelled.")
    conn.commit()
    txn = payment["transaction_id"] if payment else None
    status = "confirmed" if action == "confirm" else "cancelled"
    conn.close()
    sync_excel_all()
    if "application/json" in (request.headers.get("Accept") or ""):
        return jsonify({"ok": True, "status": status, "txn": txn})
    return redirect(url_for("admin_orders"))
