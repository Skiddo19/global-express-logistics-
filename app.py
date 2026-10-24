import os
import secrets
import sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
DATABASE = os.environ.get("DATABASE_PATH", "shipments.db")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH", "")

STATUSES = [
    "Shipment Registered", "Dispatched", "In Transit",
    "Arrived at Facility", "Out for Delivery", "Delivered", "On Hold"
]

def db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS shipments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tracking_number TEXT UNIQUE NOT NULL,
            sender TEXT NOT NULL,
            recipient TEXT NOT NULL,
            origin TEXT NOT NULL,
            destination TEXT NOT NULL,
            goods_description TEXT NOT NULL,
            estimated_delivery TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shipment_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            location TEXT NOT NULL,
            note TEXT NOT NULL,
            event_time TEXT NOT NULL,
            FOREIGN KEY(shipment_id) REFERENCES shipments(id)
        )""")

init_db()

def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapped

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/track", methods=["GET", "POST"])
def track():
    tracking = (request.values.get("tracking_number") or "").strip().upper()
    shipment = None
    events = []
    if tracking:
        with db() as conn:
            shipment = conn.execute(
                "SELECT tracking_number, origin, destination, goods_description, estimated_delivery, status, created_at FROM shipments WHERE tracking_number = ?",
                (tracking,)
            ).fetchone()
            if shipment:
                events = conn.execute(
                    "SELECT status, location, note, event_time FROM events WHERE shipment_id = (SELECT id FROM shipments WHERE tracking_number = ?) ORDER BY id DESC",
                    (tracking,)
                ).fetchall()
    return render_template("track.html", tracking=tracking, shipment=shipment, events=events)

@app.route("/admin/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if not ADMIN_PASSWORD_HASH:
            flash("Admin credentials are not configured. Set ADMIN_USERNAME and ADMIN_PASSWORD_HASH in Render environment variables.", "error")
        elif secrets.compare_digest(username, ADMIN_USERNAME) and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session.clear()
            session["admin_logged_in"] = True
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password.", "error")
    return render_template("login.html")

@app.route("/admin/logout", methods=["POST"])
@admin_required
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/admin")
@admin_required
def dashboard():
    with db() as conn:
        shipments = conn.execute("SELECT * FROM shipments ORDER BY id DESC").fetchall()
    return render_template("dashboard.html", shipments=shipments)

def new_tracking_number():
    while True:
        number = "GEL" + datetime.utcnow().strftime("%y%m%d") + secrets.token_hex(3).upper()
        with db() as conn:
            exists = conn.execute("SELECT 1 FROM shipments WHERE tracking_number = ?", (number,)).fetchone()
        if not exists:
            return number

@app.route("/admin/create", methods=["GET", "POST"])
@admin_required
def create_shipment():
    if request.method == "POST":
        fields = {key: (request.form.get(key) or "").strip() for key in
                  ["sender", "recipient", "origin", "destination", "goods_description", "estimated_delivery"]}
        if not all(fields[k] for k in ["sender", "recipient", "origin", "destination", "goods_description"]):
            flash("Please complete all required fields.", "error")
            return render_template("create.html", fields=fields)
        tracking = new_tracking_number()
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        with db() as conn:
            cur = conn.execute("""INSERT INTO shipments
                (tracking_number, sender, recipient, origin, destination, goods_description, estimated_delivery, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (tracking, fields["sender"], fields["recipient"], fields["origin"], fields["destination"],
                 fields["goods_description"], fields["estimated_delivery"], "Shipment Registered", now))
            conn.execute("""INSERT INTO events (shipment_id, status, location, note, event_time)
                VALUES (?, ?, ?, ?, ?)""",
                (cur.lastrowid, "Shipment Registered", fields["origin"], "Shipment record created.", now))
        flash(f"Shipment created. Tracking number: {tracking}", "success")
        return redirect(url_for("dashboard"))
    return render_template("create.html", fields={})

@app.route("/admin/shipment/<int:shipment_id>/update", methods=["GET", "POST"])
@admin_required
def update_shipment(shipment_id):
    with db() as conn:
        shipment = conn.execute("SELECT * FROM shipments WHERE id = ?", (shipment_id,)).fetchone()
        if not shipment:
            abort(404)
        if request.method == "POST":
            status = request.form.get("status", "")
            location = (request.form.get("location") or "").strip()
            note = (request.form.get("note") or "").strip()
            if status not in STATUSES or not location or not note:
                flash("Choose a valid status and enter the location and update note.", "error")
                return render_template("update.html", shipment=shipment, statuses=STATUSES)
            now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
            conn.execute("UPDATE shipments SET status = ? WHERE id = ?", (status, shipment_id))
            conn.execute("INSERT INTO events (shipment_id, status, location, note, event_time) VALUES (?, ?, ?, ?, ?)",
                         (shipment_id, status, location, note, now))
            flash("Shipment tracking updated.", "success")
            return redirect(url_for("dashboard"))
    return render_template("update.html", shipment=shipment, statuses=STATUSES)

@app.errorhandler(404)
def not_found(_error):
    return render_template("not_found.html"), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
