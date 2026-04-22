# PANOPTICON

*Proof > Posture*

Security control monitoring service. Continuously evaluates critical security and compliance controls across Okta, GitHub, and AWS, producing deterministic pass/fail results with evidence snapshots and Slack alerts on drift.

This is not a GRC platform. It is a narrow, engineer-friendly monitoring and evidence system for high-value controls.

## Why This Exists

Most compliance programs treat control monitoring as a point-in-time exercise: an auditor asks "is MFA enforced?" and someone screenshots the Okta policy page. That evidence is stale the moment it's captured. Between audits, controls drift — someone disables branch protection for a hotfix and forgets to re-enable it, an IAM key ages past rotation policy, a new S3 bucket gets created without encryption.

PANOPTICON was built by a GRC practitioner who wanted continuous proof instead of periodic posture claims. It runs the same checks an auditor would run, on a schedule, and stores the results with timestamps and evidence. When the auditor asks "was this control in place all quarter?", the answer is a time-series of pass/fail results with evidence snapshots — not a screenshot from last Tuesday.

## Controls

| Control | Connector | What it checks | Compliance |
|---------|-----------|----------------|------------|
| MFA Enforced | Okta | All active users have MFA enrolled | SOC 2, PCI DSS, NIST |
| No Inactive Users | Okta | No active users inactive beyond threshold | SOC 2, ISO 27001 |
| Branch Protection | GitHub | Critical repos have branch protection on default branch | SOC 2, NIST |
| No Direct Push | GitHub | Critical repos block direct pushes to main | SOC 2, NIST |
| Secret Scanning | GitHub | Secret scanning enabled on critical repos | SOC 2, ISO 27001, NIST |
| Audit Logging | AWS CloudTrail | CloudTrail enabled in production accounts | SOC 2, PCI DSS, HIPAA |
| Root MFA | AWS IAM | Root account has MFA enabled | SOC 2, PCI DSS, CIS |
| No Stale Access Keys | AWS IAM | No active keys exceed rotation threshold | SOC 2, ISO 27001, PCI DSS |
| Encryption at Rest | AWS S3 | All S3 buckets have default encryption | SOC 2, PCI DSS, HIPAA |
| No Public S3 | AWS S3 | No S3 buckets allow public access | SOC 2, PCI DSS, CIS |

## Quick Start

### With Docker

```bash
cp .env.example .env
# Edit .env with your connector credentials (or leave blank for mock data)

docker compose up
```

### Without Docker

Requires Python 3.12+, Node.js 20+, and Postgres.

```bash
# 1. Database
createdb panopticon
psql -c "CREATE USER panopticon WITH PASSWORD 'panopticon'; GRANT ALL ON DATABASE panopticon TO panopticon;"

# 2. Backend
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql://panopticon:panopticon@localhost:5432/panopticon
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload --port 8000

# 3. Frontend (separate terminal)
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Open:
- **Dashboard:** http://localhost:3000
- **API docs:** http://localhost:8000/docs
- **Health:** http://localhost:8000/api/health

The scheduler runs all controls on startup and every 6 hours (configurable via `DEFAULT_CADENCE_SECONDS`). Without real credentials, controls run against realistic mock data.

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Service health + scheduler status |
| GET | `/api/connectors` | List registered connectors + credential status |
| GET | `/api/controls` | List controls with current state |
| GET | `/api/controls/{id}` | Control detail |
| GET | `/api/controls/{id}/runs` | Run history |
| GET | `/api/controls/{id}/runs/latest` | Latest run with evidence + failures |
| POST | `/api/controls/{id}/run` | Trigger ad-hoc run |
| PATCH | `/api/controls/{id}/cadence` | Update run frequency (body: `{"cadence_seconds": 3600}`) |
| DELETE | `/api/controls/{id}/runs?before=ISO_DATE` | Delete old runs (omit `before` to delete all) |
| GET | `/api/runs/{id}` | Single run detail |
| GET | `/api/failures` | All currently failing resources |

## Architecture

```
Scheduler (APScheduler) -> Connectors (Okta/GitHub/AWS) -> External APIs
                        -> Evaluators (per-control)     -> Results (Postgres)
                        -> Alerting (Slack)
                        -> FastAPI + Next.js (UI/API)
```

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, APScheduler
- **Database:** Postgres 16
- **Frontend:** Next.js, TypeScript, Tailwind CSS
- **Containerized:** Docker Compose

**Key design principle:** Connectors fetch data. Evaluators decide. Evaluators are pure deterministic functions — no API calls, no side effects. This makes them trivially testable.

## Adding a New Connector

Connectors self-register. To add a new one (e.g., Jira, Datadog, Azure):

### 1. Add credentials to `backend/app/config.py`

```python
class Settings(BaseSettings):
    # ...existing fields...
    jira_url: str = ""
    jira_token: str = ""
```

### 2. Create the connector file

Create `backend/app/connectors/jira.py`:

```python
from __future__ import annotations
import logging
import httpx
from app.config import settings
from app.connectors.base import ConnectorBase, register_connector

logger = logging.getLogger("panopticon.connectors.jira")

@register_connector
class JiraConnector(ConnectorBase):
    """Fetches data from Jira REST API."""

    # Required: unique type string, matched by controls.connector_type
    connector_type = "jira"

    # Required: Settings field names — if all are set, the real connector is used.
    # If any are empty, the system falls back to mock_data automatically.
    required_env = ["jira_url", "jira_token"]

    # Required: mock data returned when credentials aren't configured.
    # Should be realistic enough to test evaluators against.
    mock_data = {
        "issues": [
            {"key": "SEC-1", "status": "Open", "priority": "Critical", "age_days": 45},
            {"key": "SEC-2", "status": "Closed", "priority": "High", "age_days": 10},
        ]
    }

    def test_connection(self) -> bool:
        try:
            resp = httpx.get(f"{settings.jira_url}/rest/api/2/myself",
                headers={"Authorization": f"Bearer {settings.jira_token}"}, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Jira connection test failed: {e}")
            return False

    def fetch(self, config: dict) -> dict:
        # Fetch whatever data your evaluators need.
        # The config dict comes from the control's config_json field.
        # Return a normalized dict that evaluators can consume.
        ...
```

### 3. Register the import

Add to `backend/app/connectors/__init__.py`:

```python
from app.connectors.jira import JiraConnector  # noqa: F401
```

### 4. Add to `.env.example`

```
JIRA_URL=https://your-org.atlassian.net
JIRA_TOKEN=your-api-token
```

The connector is now available. Any control with `connector_type: "jira"` will use it when credentials are configured, or fall back to mock data when they're not.

## Adding a New Evaluator

Evaluators are pure functions: they receive data from a connector and return pass/fail with evidence.

### 1. Create the evaluator file

Create `backend/app/evaluators/your_control.py`:

```python
from __future__ import annotations
from app.evaluators.base import EvaluatorBase, EvaluationResult, FailingResource

class YourControlEvaluator(EvaluatorBase):
    """Describe what this control checks.

    Expected data from connector:
        { "items": [{"id": "...", "compliant": true}, ...] }
    """

    def evaluate(self, data: dict, config: dict) -> EvaluationResult:
        items = data.get("items", [])
        if not items:
            return EvaluationResult(
                status="error",
                summary="No data returned from connector",
            )

        non_compliant = [i for i in items if not i.get("compliant")]

        failures = [
            FailingResource(
                resource_type="item",
                resource_identifier=i["id"],
                details={"reason": "Not compliant"},
            )
            for i in non_compliant
        ]

        evidence = {
            "total": len(items),
            "compliant": len(items) - len(non_compliant),
            "non_compliant": len(non_compliant),
        }

        if non_compliant:
            return EvaluationResult(
                status="fail",
                summary=f"{len(non_compliant)} of {len(items)} items are non-compliant",
                evidence=evidence,
                failures=failures,
                metadata={"evaluator": "your_control"},
            )

        return EvaluationResult(
            status="pass",
            summary=f"All {len(items)} items are compliant",
            evidence=evidence,
            metadata={"evaluator": "your_control"},
        )
```

### 2. Register in the evaluator registry

Add to `backend/app/evaluators/registry.py`:

```python
from app.evaluators.your_control import YourControlEvaluator

EVALUATOR_REGISTRY: dict[str, type[EvaluatorBase]] = {
    # ...existing entries...
    "your_control": YourControlEvaluator,
}
```

### 3. Add the control definition

Add to the `CONTROLS` list in `backend/app/seed.py`:

```python
{
    "key": "your_control",
    "name": "Human-Readable Control Name",
    "description": "What this control checks and why it matters.",
    "owner": "Team Name",
    "connector_type": "jira",          # must match a registered connector
    "evaluator_type": "your_control",  # must match the registry key
    "config_json": {},                 # control-specific config passed to connector and evaluator
},
```

Then re-run the seed: `python -m app.seed` (idempotent — skips existing controls).

## Adding and Running Tests

Tests live in `backend/tests/`. The project uses pytest.

### Running tests

```bash
cd backend
source .venv/bin/activate   # or use Docker
python -m pytest tests/ -v
```

### Evaluator tests (unit tests)

Evaluators are pure functions — test them with fixture data, no mocking needed.

Create `backend/tests/test_evaluators/test_your_control.py`:

```python
from app.evaluators.your_control import YourControlEvaluator

evaluator = YourControlEvaluator()


def test_all_compliant():
    data = {"items": [{"id": "a", "compliant": True}]}
    r = evaluator.evaluate(data, {})
    assert r.status == "pass"
    assert len(r.failures) == 0


def test_non_compliant_fails():
    data = {"items": [
        {"id": "a", "compliant": True},
        {"id": "b", "compliant": False},
    ]}
    r = evaluator.evaluate(data, {})
    assert r.status == "fail"
    assert len(r.failures) == 1
    assert r.failures[0].resource_identifier == "b"


def test_no_data_returns_error():
    r = evaluator.evaluate({}, {})
    assert r.status == "error"


def test_evidence_structure():
    data = {"items": [{"id": "a", "compliant": True}, {"id": "b", "compliant": False}]}
    r = evaluator.evaluate(data, {})
    assert r.evidence["total"] == 2
    assert r.evidence["compliant"] == 1
    assert r.evidence["non_compliant"] == 1
```

**Pattern:** Every evaluator should have tests for pass, fail, error, and evidence structure.

### Connector tests (mocked)

Connector tests mock the external API client to verify data normalization.

Create `backend/tests/test_connectors/test_jira.py`:

```python
from unittest.mock import patch, MagicMock
from app.connectors.jira import JiraConnector


@patch("app.connectors.jira.httpx.get")
def test_fetch_normalizes_data(mock_get):
    resp = MagicMock()
    resp.json.return_value = [{"key": "SEC-1", "fields": {"status": {"name": "Open"}}}]
    resp.raise_for_status = MagicMock()
    mock_get.return_value = resp

    connector = JiraConnector()
    data = connector.fetch({"project": "SEC"})
    assert "issues" in data


@patch("app.connectors.jira.httpx.get")
def test_connection_test(mock_get):
    resp = MagicMock()
    resp.status_code = 200
    mock_get.return_value = resp
    assert JiraConnector().test_connection() is True


@patch("app.connectors.jira.httpx.get")
def test_connection_failure(mock_get):
    mock_get.side_effect = Exception("timeout")
    assert JiraConnector().test_connection() is False
```

**Pattern:** Mock the HTTP client (`httpx.get` or `boto3.client`), verify the connector normalizes responses into the expected dict structure.

### Test file naming

```
tests/
  test_evaluators/
    test_mfa_enforced.py        # one file per evaluator
    test_branch_protection.py
    test_your_control.py
  test_connectors/
    test_okta.py                # one file per connector
    test_github.py
    test_your_connector.py
  test_api/
    test_controls.py            # API route tests
```

## Configuration

**Environment variables** (`.env`):

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | Postgres connection string |
| `OKTA_DOMAIN` | No | Okta org domain (e.g., `your-org.okta.com`) |
| `OKTA_API_TOKEN` | No | Okta Admin API token |
| `GITHUB_TOKEN` | No | GitHub PAT with `repo` scope |
| `AWS_ACCESS_KEY_ID` | No | AWS credentials for CloudTrail/IAM/S3 checks |
| `AWS_SECRET_ACCESS_KEY` | No | AWS secret key |
| `AWS_DEFAULT_REGION` | No | AWS region (default: `us-east-1`) |
| `SLACK_WEBHOOK_URL` | No | Slack webhook for alerts |
| `DEFAULT_CADENCE_SECONDS` | No | Global run interval (default: `21600` = 6 hours) |

All connector credentials are optional. Without them, controls run against built-in mock data — useful for development and demos.

**Per-control config** is stored in the `config_json` column and passed to both the connector's `fetch()` and the evaluator's `evaluate()`. Examples:

```json
{"critical_repos": ["org/api-service", "org/web-app"]}
{"inactivity_threshold_days": 90}
{"max_key_age_days": 90}
{"production_accounts": ["123456789012"]}
```

## Alerting

Slack alerts fire on:
- **Pass to fail** transition
- **Persistent failure** (every 3 consecutive failing runs)
- **Evaluator/connector errors**

Configure via `SLACK_WEBHOOK_URL`. Leave empty to disable.

## Development

Designed, spec'd, and directed by a security/compliance practitioner. AI-assisted implementation using [Claude Code](https://claude.ai/code).

The control definitions, evaluator logic, compliance mappings, and alerting thresholds come from real-world audit experience. The architecture — separating connectors (data fetching) from evaluators (pass/fail logic) — exists because that's how you make controls testable and auditable. The implementation was accelerated with AI tooling, but the design decisions reflect what actually matters when an auditor is sitting across the table from you.

## License

Apache 2.0 with Commons Clause — see [LICENSE](LICENSE).
