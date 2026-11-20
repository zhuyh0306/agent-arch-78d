from dataagent.domain.tenant_policy import Reason, authorize_hop, load_cases


def test_fixture_cases_match_expectations():
    for case in load_cases():
        decision = authorize_hop(
            case["hop"],
            case.get("auth_tenant"),
            case.get("target_tenant"),
            tenant_in_filter=case.get("tenant_in_filter", True),
        )
        got = "ALLOW" if decision.allow else f"DENY:{decision.reason.value}"
        assert got == case["expect"], f"{case['id']}: expected {case['expect']}, got {got}"


def test_missing_auth_tenant_is_denied():
    decision = authorize_hop("db", None, "tenant-a")
    assert decision.allow is False
    assert decision.reason is Reason.TENANT_MISSING


def test_missing_target_on_data_hop_is_denied():
    decision = authorize_hop("vector", "tenant-a", None)
    assert decision.allow is False
    assert decision.reason is Reason.TENANT_MISSING


def test_request_hop_without_override_uses_session_tenant():
    decision = authorize_hop("request", "tenant-a", None)
    assert decision.allow is True
    assert decision.reason is Reason.OK


def test_unknown_hop_is_denied():
    decision = authorize_hop("cache", "tenant-a", "tenant-a")
    assert decision.allow is False
    assert decision.reason is Reason.UNKNOWN_HOP