from app.evaluators.secret_scanning import SecretScanningEvaluator

evaluator = SecretScanningEvaluator()


def test_all_enabled():
    data = {"repos": [
        {"full_name": "org/a", "security_settings": {"secret_scanning": True, "secret_scanning_push_protection": True}},
        {"full_name": "org/b", "security_settings": {"secret_scanning": True, "secret_scanning_push_protection": False}},
    ]}
    r = evaluator.evaluate(data, {})
    assert r.status == "pass"


def test_disabled_fails():
    data = {"repos": [
        {"full_name": "org/a", "security_settings": {"secret_scanning": True}},
        {"full_name": "org/b", "security_settings": {"secret_scanning": False}},
    ]}
    r = evaluator.evaluate(data, {})
    assert r.status == "fail"
    assert len(r.failures) == 1
    assert r.failures[0].resource_identifier == "org/b"


def test_missing_security_settings_fails():
    data = {"repos": [{"full_name": "org/a"}]}
    r = evaluator.evaluate(data, {})
    assert r.status == "fail"


def test_no_repos():
    r = evaluator.evaluate({"repos": []}, {})
    assert r.status == "error"


def test_no_data():
    r = evaluator.evaluate({}, {})
    assert r.status == "error"


def test_evidence_details():
    data = {"repos": [
        {"full_name": "org/a", "security_settings": {"secret_scanning": True, "secret_scanning_push_protection": True}},
        {"full_name": "org/b", "security_settings": {"secret_scanning": False, "secret_scanning_push_protection": False}},
    ]}
    r = evaluator.evaluate(data, {})
    assert r.evidence["total_repos"] == 2
    assert r.evidence["scanning_enabled"] == 1
    assert r.evidence["scanning_disabled"] == 1
