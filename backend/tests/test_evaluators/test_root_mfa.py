from app.evaluators.root_mfa import RootMfaEvaluator

evaluator = RootMfaEvaluator()


def test_mfa_enabled():
    r = evaluator.evaluate({"root_account": {"account_id": "111", "mfa_enabled": True}}, {})
    assert r.status == "pass"
    assert len(r.failures) == 0


def test_mfa_disabled():
    r = evaluator.evaluate({"root_account": {"account_id": "111", "mfa_enabled": False}}, {})
    assert r.status == "fail"
    assert r.failures[0].resource_identifier == "111"


def test_no_data():
    r = evaluator.evaluate({}, {})
    assert r.status == "error"


def test_api_error():
    r = evaluator.evaluate({"root_account": {"account_id": "111", "error": "access denied"}}, {})
    assert r.status == "error"
    assert "access denied" in r.summary
