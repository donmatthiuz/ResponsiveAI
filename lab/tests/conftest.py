import threading
from copy import deepcopy
from uuid import uuid4

import pytest
from flask import Flask

from backend import main
from backend.repository import InvalidState, NotFound


class MemoryRepository:
    """Solo sustituto de pruebas unitarias; las integraciones usan Firestore real emulado."""

    def __init__(self):
        self.items = {}
        self.lock = threading.Lock()

    def create(self, run_id, attributes):
        with self.lock:
            order = {**attributes, "id": uuid4().hex, "status": "created", "run_id": run_id}
            self.items[run_id, order["id"]] = order
            return deepcopy(order)

    def get(self, run_id, order_id):
        with self.lock:
            if (run_id, order_id) not in self.items:
                raise NotFound()
            return deepcopy(self.items[run_id, order_id])

    def cancel(self, run_id, order_id):
        with self.lock:
            order = self.items.get((run_id, order_id))
            if not order:
                raise NotFound()
            if order["status"] != "created":
                raise InvalidState(deepcopy(order))
            order["status"] = "cancelled"
            return deepcopy(order)


@pytest.fixture
def api(monkeypatch):
    repository = MemoryRepository()
    monkeypatch.setattr(main, "get_repository", lambda: repository)
    monkeypatch.setattr(main, "SETTINGS", main.Settings(0, 0))
    app = Flask(__name__)
    app.testing = True

    def call(path="/orders", method="POST", **kwargs):
        with app.test_request_context(path, method=method, **kwargs):
            return main.handle(__import__("flask").request)

    return call, repository


@pytest.fixture
def payload():
    return {"category": "books", "customer_tier": "premium", "amount": 12.5}
