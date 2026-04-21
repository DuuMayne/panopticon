from __future__ import annotations

import logging

from app.evaluators.base import EvaluatorBase
from app.evaluators.mfa_enforced import MfaEnforcedEvaluator
from app.evaluators.inactive_users import InactiveUsersEvaluator
from app.evaluators.branch_protection import BranchProtectionEvaluator
from app.evaluators.no_direct_push import NoDirectPushEvaluator
from app.evaluators.audit_logging import AuditLoggingEvaluator
from app.connectors.base import ConnectorBase, MockConnector, get_registered_connectors
from app.config import settings

# Ensure all connectors are imported and registered
import app.connectors  # noqa: F401

logger = logging.getLogger("panopticon.registry")

EVALUATOR_REGISTRY: dict[str, type[EvaluatorBase]] = {
    "mfa_enforced": MfaEnforcedEvaluator,
    "no_inactive_users": InactiveUsersEvaluator,
    "branch_protection": BranchProtectionEvaluator,
    "no_direct_push": NoDirectPushEvaluator,
    "audit_logging": AuditLoggingEvaluator,
}


def get_evaluator(evaluator_type: str) -> EvaluatorBase:
    cls = EVALUATOR_REGISTRY.get(evaluator_type)
    if cls is None:
        raise ValueError(f"Unknown evaluator type: {evaluator_type}")
    return cls()


def get_connector(connector_type: str) -> ConnectorBase:
    """Return a real connector if credentials are configured, otherwise mock.

    Connectors self-register via @register_connector. Each declares its
    required_env fields — if all are set in Settings, the real connector
    is used. Otherwise falls back to the connector's mock_data.
    """
    registry = get_registered_connectors()
    cls = registry.get(connector_type)

    if cls is None:
        logger.warning(f"No connector registered for type '{connector_type}', using empty mock")
        return MockConnector({})

    # Check if required credentials are configured
    if cls.required_env:
        all_configured = all(getattr(settings, env_key, None) for env_key in cls.required_env)
        if all_configured:
            return cls()

    logger.info(f"No credentials for {connector_type}, using mock connector")
    return MockConnector(cls.mock_data)
