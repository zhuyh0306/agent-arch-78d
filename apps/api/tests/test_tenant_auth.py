"""Tenant and auth: the boundary must be closed by default.

Every test here is written as an attack that must fail. A test that only proves
"a valid key works" would pass just as well if auth were disabled.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dataagent.api.app import create_app
from dataagent.domain.auth import ApiKey, ApiKeyStore, AuthenticationError
from dataagent.domain.tenant import TenantContext, TenantResolutionError
from dataagent.infra.container import Container, build_container
from dataagent.infra.settings import Settings

DICTIONARY = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "metrics_dictionary.yaml"
KEY_A = "key-tenant-a-0123456789abcdef"
KEY_B = "key-tenant-b-0123456789abcdef"


def make_client(keys: ApiKeyStore | None = None) -> TestClient:
    base = build_container(Settings(metrics_dictionary=DICTIONARY))
    store = keys if keys is not None else ApiKeyStore(
        keys=(
            ApiKey(KEY_A, "tenant-a", "alice"),
            ApiKey(KEY_B, "tenant-b", "bob"),
        )
    )
    container = Container(
        settings=base.settings,
        llm=base.llm,
        tools=base.tools,
        metrics=base.metrics,
        agent=base.agent,
        api_keys=store,
    )
    return TestClient(create_app(container))


# ---------------------------------------------------------------- auth gate


def test_request_without_key_is_rejected() -> None:
    response = make_client().get("/metrics/gmv")
    assert response.status_code == 401
    assert response.json()["detail"]["failure_code"] == "GUARDRAIL_BLOCKED"


def test_wrong_key_is_rejected() -> None:
    response = make_client().get("/metrics/gmv", headers={"X-API-Key": "not-a-real-key"})
    assert response.status_code == 401


def test_empty_key_store_rejects_everything() -> None:
    """Fail closed: an unset DATAAGENT_API_KEYS must never mean 'auth off'."""
    response = make_client(ApiKeyStore()).get("/metrics/gmv", headers={"X-API-Key": KEY_A})
    assert response.status_code == 401


def test_valid_key_identifies_its_own_tenant() -> None:
    response = make_client().get("/metrics/gmv", headers={"X-API-Key": KEY_A})
    assert response.status_code == 200
    assert response.json()["tenant_id"] == "tenant-a"


def test_each_key_maps_to_exactly_one_tenant() -> None:
    client = make_client()
    assert client.get("/metrics/gmv", headers={"X-API-Key": KEY_A}).json()["tenant_id"] == "tenant-a"
    assert client.get("/metrics/gmv", headers={"X-API-Key": KEY_B}).json()["tenant_id"] == "tenant-b"


def test_caller_cannot_choose_tenant_via_header() -> None:
    """The classic attack: a valid key plus a self-declared tenant header."""
    response = make_client().get(
        "/metrics/gmv",
        headers={"X-API-Key": KEY_A, "X-Tenant-Id": "tenant-b"},
    )
    assert response.status_code == 200
    assert response.json()["tenant_id"] == "tenant-a", "caller must not be able to override its tenant"


def test_caller_cannot_choose_tenant_via_query_param() -> None:
    response = make_client().get("/metrics/gmv?tenant_id=tenant-b", headers={"X-API-Key": KEY_A})
    assert response.status_code == 200
    assert response.json()["tenant_id"] == "tenant-a"


def test_healthz_needs_no_key_but_leaks_nothing() -> None:
    response = make_client().get("/healthz")
    assert response.status_code == 200
    body = response.text
    assert KEY_A not in body
    assert "tenant" not in body.lower()


def test_error_response_does_not_echo_the_key() -> None:
    bogus = "leaky-probe-key-should-not-appear"
    response = make_client().get("/metrics/gmv", headers={"X-API-Key": bogus})
    assert response.status_code == 401
    assert bogus not in response.text


# ------------------------------------------------------------- auth units


def test_key_repr_never_shows_the_secret() -> None:
    key = ApiKey(KEY_A, "tenant-a", "alice")
    assert KEY_A not in repr(key)
    assert "tenant-a" in repr(key)


def test_missing_credential_raises() -> None:
    with pytest.raises(AuthenticationError):
        ApiKeyStore(keys=(ApiKey(KEY_A, "tenant-a", "alice"),)).authenticate(None)


def test_key_bound_to_invalid_tenant_fails_closed() -> None:
    store = ApiKeyStore(keys=(ApiKey("k", "TENANT_UPPER", "x"),))
    with pytest.raises(AuthenticationError):
        store.authenticate("k")


def test_store_from_env_parses_three_fields() -> None:
    store = ApiKeyStore.from_env({"DATAAGENT_API_KEYS": f"{KEY_A}:tenant-a:alice"})
    assert store.authenticate(KEY_A).tenant_id == "tenant-a"


def test_store_from_env_rejects_malformed_entry() -> None:
    with pytest.raises(ValueError, match="key:tenant:principal"):
        ApiKeyStore.from_env({"DATAAGENT_API_KEYS": "just-a-key"})


def test_store_from_env_absent_is_empty_not_open() -> None:
    assert ApiKeyStore.from_env({}).keys == ()


# ----------------------------------------------------------- tenant domain


@pytest.mark.parametrize("bad", ["", "UPPER", "has space", "-leadingdash", "x", "a" * 40])
def test_invalid_tenant_ids_are_rejected(bad: str) -> None:
    with pytest.raises(TenantResolutionError):
        TenantContext(tenant_id=bad, principal="alice")


def test_tenant_context_is_immutable() -> None:
    context = TenantContext(tenant_id="tenant-a", principal="alice")
    with pytest.raises(dataclasses.FrozenInstanceError):
        context.tenant_id = "tenant-b"  # type: ignore[misc]


def test_tenant_context_authorizes_its_own_data() -> None:
    context = TenantContext(tenant_id="tenant-a", principal="alice")
    decision = context.authorize("db")
    assert decision.allow is True


def test_tenant_context_refuses_another_tenant() -> None:
    context = TenantContext(tenant_id="tenant-a", principal="alice")
    decision = context.authorize("db", "tenant-b")
    assert decision.allow is False
    assert decision.reason.value == "TENANT_MISMATCH"


def test_vector_hop_without_tenant_filter_is_denied() -> None:
    """The vector hop's specific failure mode: right tenant, missing filter."""
    from dataagent.domain.tenant_policy import authorize_hop

    with_filter = authorize_hop("vector", "tenant-a", "tenant-a", tenant_in_filter=True)
    without_filter = authorize_hop("vector", "tenant-a", "tenant-a", tenant_in_filter=False)

    assert with_filter.allow is True
    assert without_filter.allow is False
    assert without_filter.reason.value == "FILTER_MISSING"


def test_log_fields_carry_the_tenant() -> None:
    fields = TenantContext(tenant_id="tenant-a", principal="alice").as_log_fields()
    assert fields == {"tenant_id": "tenant-a", "principal": "alice"}