"""Persistencia compartida. Sin diccionarios ni fallbacks locales en producción."""

import os
from functools import lru_cache
from uuid import uuid4

from google.cloud import firestore


class NotFound(Exception):
    pass


class InvalidState(Exception):
    def __init__(self, order):
        self.order = order
        super().__init__("El pedido ya está cancelado")


class FirestoreRepository:
    def __init__(self, client=None):
        self.client = client or firestore.Client(
            project=os.getenv("FIRESTORE_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT"),
            database=os.getenv("FIRESTORE_DATABASE", "lab-orders"),
        )

    def orders(self, run_id):
        return self.client.collection("lab_runs").document(run_id).collection("orders")

    def create(self, run_id, attributes):
        order = {**attributes, "id": uuid4().hex, "status": "created", "run_id": run_id}
        self.orders(run_id).document(order["id"]).create(order)
        return order

    def get(self, run_id, order_id):
        snapshot = self.orders(run_id).document(order_id).get()
        if not snapshot.exists:
            raise NotFound()
        return snapshot.to_dict()

    def cancel(self, run_id, order_id):
        ref = self.orders(run_id).document(order_id)

        @firestore.transactional
        def transition(transaction):
            snapshot = ref.get(transaction=transaction)
            if not snapshot.exists:
                raise NotFound()
            order = snapshot.to_dict()
            if order["status"] != "created":
                raise InvalidState(order)
            transaction.update(ref, {"status": "cancelled"})
            return {**order, "status": "cancelled"}

        return transition(self.client.transaction())


@lru_cache(maxsize=1)
def get_repository():
    return FirestoreRepository()
