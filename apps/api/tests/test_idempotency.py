import pytest

from app.application.idempotency import IdempotencyStore, request_fingerprint
from app.errors import AppError


def test_lookup_returns_none_when_key_is_new(db_session):
    store = IdempotencyStore(db_session)

    assert store.lookup("k1", "/api/v1/tasks", "hash-a") is None


def test_lookup_returns_first_response_for_same_key_and_body(db_session):
    store = IdempotencyStore(db_session)
    store.remember("k1", "/api/v1/tasks", "hash-a", 201, {"id": "abc"})

    assert store.lookup("k1", "/api/v1/tasks", "hash-a") == {"id": "abc"}


def test_lookup_rejects_same_key_with_different_body(db_session):
    store = IdempotencyStore(db_session)
    store.remember("k1", "/api/v1/tasks", "hash-a", 201, {"id": "abc"})

    with pytest.raises(AppError) as exc:
        store.lookup("k1", "/api/v1/tasks", "hash-b")

    assert exc.value.code == "IDEMPOTENCY_KEY_REUSED"
    assert exc.value.status_code == 409


def test_same_key_on_different_endpoint_is_independent(db_session):
    store = IdempotencyStore(db_session)
    store.remember("k1", "/api/v1/tasks", "hash-a", 201, {"id": "abc"})

    assert store.lookup("k1", "/api/v1/exports", "hash-b") is None


def test_fingerprint_changes_with_body():
    assert request_fingerprint("/x", b"{}") != request_fingerprint("/x", b"{'a':1}")
