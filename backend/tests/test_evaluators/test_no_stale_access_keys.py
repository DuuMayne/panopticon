from app.evaluators.no_stale_access_keys import NoStaleAccessKeysEvaluator

evaluator = NoStaleAccessKeysEvaluator()


def make_key(user, key_id, age, status="Active"):
    return {"user_name": user, "access_key_id": key_id, "status": status, "created_days_ago": age}


def test_all_within_threshold():
    data = {"access_keys": [make_key("svc1", "AK1", 30), make_key("svc2", "AK2", 60)]}
    r = evaluator.evaluate(data, {"max_key_age_days": 90})
    assert r.status == "pass"


def test_stale_key_fails():
    data = {"access_keys": [make_key("svc1", "AK1", 30), make_key("old", "AK2", 200)]}
    r = evaluator.evaluate(data, {"max_key_age_days": 90})
    assert r.status == "fail"
    assert len(r.failures) == 1
    assert "old/AK2" in r.failures[0].resource_identifier


def test_inactive_keys_ignored():
    data = {"access_keys": [make_key("old", "AK1", 500, status="Inactive")]}
    r = evaluator.evaluate(data, {"max_key_age_days": 90})
    assert r.status == "pass"


def test_custom_threshold():
    data = {"access_keys": [make_key("svc", "AK1", 50)]}
    r1 = evaluator.evaluate(data, {"max_key_age_days": 60})
    assert r1.status == "pass"
    r2 = evaluator.evaluate(data, {"max_key_age_days": 30})
    assert r2.status == "fail"


def test_no_data():
    r = evaluator.evaluate({}, {})
    assert r.status == "error"


def test_empty_keys_passes():
    r = evaluator.evaluate({"access_keys": []}, {})
    assert r.status == "pass"
