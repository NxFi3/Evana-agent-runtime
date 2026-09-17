"""Pytest test suite for the Flask task manager application.

The tests exercise the main CRUD operations and verify that the
application correctly handles valid and invalid task identifiers.
"""

import os
import tempfile
from pathlib import Path

import pytest

from flask import Flask

# Import the application factory.  The module defines a global ``app``
# instance, but we import it directly to keep the tests simple.
from EvanaEval.app import app as flask_app


@pytest.fixture
def client(tmp_path: Path):
    """Create a test client with a temporary SQLite database.

    The application uses a global ``DB_PATH`` variable pointing to
    ``tasks.db`` in the project root.  For isolation we monkey‑patch
    this path to a temporary file created by the test fixture.
    """

    # Monkey‑patch the database path to a temporary file.
    original_db_path = flask_app.DB_PATH
    tmp_db = tmp_path / "test.db"
    flask_app.DB_PATH = tmp_db

    # Ensure the database is created and tables are initialised.
    with flask_app.app_context():
        flask_app.init_db()

    # Enable testing mode.
    flask_app.config["TESTING"] = True
    client = flask_app.test_client()

    yield client

    # Restore original DB path after the test.
    flask_app.DB_PATH = original_db_path


def test_create_and_list_task(client):
    """Create a task and verify it appears in the list."""
    # Create a new task.
    response = client.post("/create", data={"title": "Test Task"}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Test Task" in response.data

    # Verify that the task is listed.
    response = client.get("/")
    assert response.status_code == 200
    assert b"Test Task" in response.data


def test_complete_task(client):
    """Mark a task as completed and verify the status changes."""
    # Create a task first.
    client.post("/create", data={"title": "Complete Me"}, follow_redirects=True)
    # Retrieve the task ID from the page.
    response = client.get("/")
    assert b"Complete Me" in response.data
    # The task list renders a form with action /complete/<id>.
    # Extract the ID using a simple regex.
    import re

    match = re.search(r'/complete/(\d+)', response.data.decode())
    assert match, "Could not find complete form action"
    task_id = match.group(1)
    # Complete the task.
    response = client.post(f"/complete/{task_id}", follow_redirects=True)
    assert response.status_code == 200
    # The completed button should now be disabled.
    assert f'disabled' in response.data.decode()


def test_delete_task(client):
    """Delete a task and ensure it no longer appears."""
    client.post("/create", data={"title": "Delete Me"}, follow_redirects=True)
    response = client.get("/")
    import re
    match = re.search(r'/delete/(\d+)', response.data.decode())
    assert match
    task_id = match.group(1)
    # Delete the task.
    response = client.post(f"/delete/{task_id}", follow_redirects=True)
    assert response.status_code == 200
    # Verify the task is gone.
    assert b"Delete Me" not in response.data


def test_invalid_task_id(client):
    """Attempt to complete or delete a non‑existent task and expect 404."""
    # Use a high ID that is unlikely to exist.
    invalid_id = 9999
    response = client.post(f"/complete/{invalid_id}")
    assert response.status_code == 404
    response = client.post(f"/delete/{invalid_id}")
    assert response.status_code == 404

