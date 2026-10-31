import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from google.cloud import firestore

from backend.repository import FirestoreRepository, InvalidState, NotFound

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("FIRESTORE_EMULATOR_HOST"), reason="FIRESTORE_EMULATOR_HOST no configurado"
    ),
]


def repository():
    return FirestoreRepository(
        firestore.Client(project="demo-observable-lab", database="lab-orders")
    )


def test_shared_clients_process_and_atomic_transition():
    first, second = repository(), repository()
    run_id = "integration-" + uuid4().hex
    order = first.create(run_id, {"category": "books", "customer_tier": "premium", "amount": 10})
    try:
        assert second.get(run_id, order["id"]) == order
        program = """
import sys
from google.cloud import firestore
from backend.repository import FirestoreRepository
repo = FirestoreRepository(firestore.Client(project='demo-observable-lab', database='lab-orders'))
assert repo.get(sys.argv[1], sys.argv[2])['status'] == 'created'
print('shared-process-ok')
"""
        result = subprocess.run(
            [sys.executable, "-c", program, run_id, order["id"]],
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        )
        assert result.stdout.strip() == "shared-process-ok"

        def cancel(repo):
            try:
                repo.cancel(run_id, order["id"])
                return "changed"
            except InvalidState:
                return "conflict"

        with ThreadPoolExecutor(2) as pool:
            assert sorted(pool.map(cancel, [first, second])) == ["changed", "conflict"]
        assert first.get(run_id, order["id"])["status"] == "cancelled"
        with pytest.raises(NotFound):
            second.get("another-run", order["id"])
    finally:
        first.orders(run_id).document(order["id"]).delete()
        first.client.close()
        second.client.close()
