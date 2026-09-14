# EvanaEval/app.py
"""Main Flask application for Personal Finance Dashboard."""

import os
import sqlite3
from datetime import datetime

from flask import (
    Flask,
    g,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    abort,
)

# Configuration
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "finance.db")
DEBUG = True
SECRET_KEY = "dev"  # In production use a random secret key

app = Flask(__name__)
app.config["DATABASE"] = DATABASE
app.config["DEBUG"] = DEBUG
app.config["SECRET_KEY"] = SECRET_KEY

# ---------- Database helpers ----------

def get_db():
    """Opens a new database connection if there is none yet for the
    current application context."""
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(app.config["DATABASE"])
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

# ---------- Schema initialization ----------

def init_db():
    """Create tables if they do not exist."""
    db = get_db()
    with app.open_resource("schema.sql", mode="r") as f:
        db.executescript(f.read())

# Create schema file
schema_sql = """
-- Categories table
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

-- Transactions table
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    amount REAL NOT NULL,
    description TEXT,
    category_id INTEGER,
    date TEXT NOT NULL,
    FOREIGN KEY (category_id) REFERENCES categories(id)
);
"""

schema_path = os.path.join(BASE_DIR, "schema.sql")
if not os.path.exists(schema_path):
    with open(schema_path, "w") as f:
        f.write(schema_sql)

# Ensure database exists
if not os.path.exists(DATABASE):
    init_db()

# ---------- Helper functions ----------

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

# ---------- Routes ----------

@app.route("/")
@app.route("/dashboard")
def dashboard():
    # Get filter parameters
    category_id = request.args.get("category", type=int)
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    # Build query
    conditions = []
    params = []
    if category_id:
        conditions.append("category_id = ?")
        params.append(category_id)
    if start_date:
        conditions.append("date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("date <= ?")
        params.append(end_date)

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    transactions = query_db(
        f"SELECT t.*, c.name as category_name FROM transactions t LEFT JOIN categories c ON t.category_id = c.id {where_clause} ORDER BY date DESC", params
    )

    # Totals
    income = sum(t["amount"] for t in transactions if t["amount"] > 0)
    expenses = sum(t["amount"] for t in transactions if t["amount"] < 0)
    balance = income + expenses

    categories = query_db("SELECT * FROM categories ORDER BY name")

    return render_template(
        "dashboard.html",
        transactions=transactions,
        categories=categories,
        selected_category=category_id,
        start_date=start_date,
        end_date=end_date,
        income=income,
        expenses=expenses,
        balance=balance,
    )

@app.route("/transaction/add", methods=["GET", "POST"])
def add_transaction():
    if request.method == "POST":
        try:
            amount = float(request.form["amount"])
        except (ValueError, KeyError):
            flash("Invalid amount.")
            return redirect(url_for("add_transaction"))
        description = request.form.get("description", "")
        category_id = request.form.get("category_id", type=int)
        date_str = request.form.get("date")
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            flash("Invalid date.")
            return redirect(url_for("add_transaction"))
        db = get_db()
        db.execute(
            "INSERT INTO transactions (amount, description, category_id, date) VALUES (?, ?, ?, ?)",
            (amount, description, category_id, date_str),
        )
        db.commit()
        flash("Transaction added.")
        return redirect(url_for("dashboard"))
    categories = query_db("SELECT * FROM categories ORDER BY name")
    return render_template("transaction_form.html", categories=categories, action="Add", transaction=None)

@app.route("/transaction/edit/<int:id>", methods=["GET", "POST"])
def edit_transaction(id):
    transaction = query_db("SELECT * FROM transactions WHERE id = ?", (id,), one=True)
    if not transaction:
        abort(404)
    if request.method == "POST":
        try:
            amount = float(request.form["amount"])
        except (ValueError, KeyError):
            flash("Invalid amount.")
            return redirect(url_for("edit_transaction", id=id))
        description = request.form.get("description", "")
        category_id = request.form.get("category_id", type=int)
        date_str = request.form.get("date")
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            flash("Invalid date.")
            return redirect(url_for("edit_transaction", id=id))
        db = get_db()
        db.execute(
            "UPDATE transactions SET amount = ?, description = ?, category_id = ?, date = ? WHERE id = ?",
            (amount, description, category_id, date_str, id),
        )
        db.commit()
        flash("Transaction updated.")
        return redirect(url_for("dashboard"))
    categories = query_db("SELECT * FROM categories ORDER BY name")
    return render_template("transaction_form.html", categories=categories, action="Edit", transaction=transaction)

@app.route("/transaction/delete/<int:id>", methods=["POST"])
def delete_transaction(id):
    db = get_db()
    db.execute("DELETE FROM transactions WHERE id = ?", (id,))
    db.commit()
    flash("Transaction deleted.")
    return redirect(url_for("dashboard"))

@app.route("/category/add", methods=["GET", "POST"])
def add_category():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Category name cannot be empty.")
            return redirect(url_for("add_category"))
        db = get_db()
        try:
            db.execute("INSERT INTO categories (name) VALUES (?)", (name,))
            db.commit()
            flash("Category added.")
        except sqlite3.IntegrityError:
            flash("Category already exists.")
        return redirect(url_for("dashboard"))
    return render_template("category_form.html", action="Add")

@app.route("/category/edit/<int:id>", methods=["GET", "POST"])
def edit_category(id):
    category = query_db("SELECT * FROM categories WHERE id = ?", (id,), one=True)
    if not category:
        abort(404)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Category name cannot be empty.")
            return redirect(url_for("edit_category", id=id))
        db = get_db()
        try:
            db.execute("UPDATE categories SET name = ? WHERE id = ?", (name, id))
            db.commit()
            flash("Category updated.")
        except sqlite3.IntegrityError:
            flash("Category name already exists.")
        return redirect(url_for("dashboard"))
    return render_template("category_form.html", action="Edit", category=category)

@app.route("/category/delete/<int:id>", methods=["POST"])
def delete_category(id):
    db = get_db()
    db.execute("DELETE FROM categories WHERE id = ?", (id,))
    db.commit()
    flash("Category deleted.")
    return redirect(url_for("dashboard"))

# ---------- Error handlers ----------

@app.errorhandler(404)
def not_found_error(error):
    return render_template("404.html"), 404

@app.errorhandler(500)
def internal_error(error):
    get_db().rollback()
    return render_template("500.html"), 500

# ---------- Run ----------

if __name__ == "__main__":
    app.run(debug=True)
