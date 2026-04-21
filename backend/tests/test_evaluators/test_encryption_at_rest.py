from app.evaluators.encryption_at_rest import EncryptionAtRestEvaluator

evaluator = EncryptionAtRestEvaluator()


def test_all_encrypted():
    data = {"buckets": [
        {"name": "a", "encryption_enabled": True, "encryption_type": "aws:kms"},
        {"name": "b", "encryption_enabled": True, "encryption_type": "AES256"},
    ]}
    r = evaluator.evaluate(data, {})
    assert r.status == "pass"


def test_unencrypted_fails():
    data = {"buckets": [
        {"name": "enc", "encryption_enabled": True},
        {"name": "open", "encryption_enabled": False},
    ]}
    r = evaluator.evaluate(data, {})
    assert r.status == "fail"
    assert len(r.failures) == 1
    assert r.failures[0].resource_identifier == "open"


def test_no_buckets_passes():
    r = evaluator.evaluate({"buckets": []}, {})
    assert r.status == "pass"


def test_no_data():
    r = evaluator.evaluate({}, {})
    assert r.status == "error"


def test_evidence_details():
    data = {"buckets": [
        {"name": "a", "encryption_enabled": True, "encryption_type": "aws:kms"},
        {"name": "b", "encryption_enabled": False},
    ]}
    r = evaluator.evaluate(data, {})
    assert r.evidence["total_buckets"] == 2
    assert r.evidence["encrypted"] == 1
    assert r.evidence["unencrypted"] == 1
