from app.evaluators.no_public_s3 import NoPublicS3Evaluator

evaluator = NoPublicS3Evaluator()


def test_all_private():
    data = {"buckets": [
        {"name": "a", "public_access_blocked": True},
        {"name": "b", "public_access_blocked": True},
    ]}
    r = evaluator.evaluate(data, {})
    assert r.status == "pass"


def test_public_bucket_fails():
    data = {"buckets": [
        {"name": "private", "public_access_blocked": True},
        {"name": "public", "public_access_blocked": False},
    ]}
    r = evaluator.evaluate(data, {})
    assert r.status == "fail"
    assert len(r.failures) == 1
    assert r.failures[0].resource_identifier == "public"


def test_no_buckets_passes():
    r = evaluator.evaluate({"buckets": []}, {})
    assert r.status == "pass"


def test_no_data():
    r = evaluator.evaluate({}, {})
    assert r.status == "error"


def test_all_public():
    data = {"buckets": [
        {"name": "a", "public_access_blocked": False},
        {"name": "b", "public_access_blocked": False},
    ]}
    r = evaluator.evaluate(data, {})
    assert r.status == "fail"
    assert len(r.failures) == 2
