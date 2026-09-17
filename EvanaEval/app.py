"""Flask application for a simple task manager.

The application is intentionally minimal and self‑contained.  It uses
SQLite for persistence and creates the database file on first run.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Tuple

from flask import (
    Flask,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "tasks.db"

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev"  # not used but required by Flask


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db() -> sqlite3.Connection:
    """Return a SQLite connection stored in the Flask ``g`` object.

    The connection is created lazily and closed automatically when the
    application context ends.
    """

    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


def init_db() -> None:
    """Create the tasks table if it does not already exist.

    This function is idempotent and safe to call on every request.
    """

    db = get_db()
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            created TIMESTAMP NOT NULL
        );
        """
    )
    db.commit()


@app.before_request
def before_request() -> None:
    """Ensure the database is initialised before handling a request."""
    init_db()


@app.teardown_appcontext
def close_db(error: Any) -> None:  # pragma: no cover - trivial
    db = g.pop("db", None)
    if db is not None:
        db.close()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index() -> str:
    """Display all tasks sorted by creation time."""
    db = get_db()
    tasks: Iterable[sqlite3.Row] = db.execute(
        "SELECT id, title, completed, created FROM tasks ORDER BY created DESC"
    ).fetchall()
    return render_template("index.html", tasks=tasks)


@app.route("/create", methods=["POST"])
def create_task() -> str:
    title = request.form.get("title", "").strip()
    if not title:
        # Ignore empty titles – redirect back to index.
        return redirect(url_for("index"))
    db = get_db()
    db.execute(
        "INSERT INTO tasks (title, completed, created) VALUES (?, 0, ?)",
        (title, datetime.utcnow()),
    )
    db.commit()
    return redirect(url_for("index"))


@app.route("/complete/<int:task_id>", methods=["POST"])
def complete_task(task_id: int) -> str:
    db = get_db()
    cur = db.execute("SELECT id FROM tasks WHERE id = ?", (task_id,))
    if cur.fetchone() is None:
        return "Task not found", 404
    db.execute("UPDATE tasks SET completed = 1 WHERE id = ?", (task_id,))
    db.commit()
    return redirect(url_for("index"))


@app.route("/delete/<int:task_id>", methods=["POST"])
def delete_task(task_id: int) -> str:
    db = get_db()
    cur = db.execute("SELECT id FROM tasks WHERE id = ?", (task_id,))
    if cur.fetchone() is None:
        return "Task not found", 404
    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Application entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover - manual run
    app.run(debug=True)

