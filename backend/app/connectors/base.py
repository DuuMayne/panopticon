from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar


# Global connector registry — populated by register_connector()
_CONNECTOR_REGISTRY: dict[str, type[ConnectorBase]] = {}


class ConnectorBase(ABC):
    """Base class for all external system connectors.

    To create a new connector:
    1. Create a new file in app/connectors/ (e.g., jira.py)
    2. Subclass ConnectorBase
    3. Set connector_type to a unique string (e.g., "jira")
    4. Set required_env to the list of Settings fields needed (e.g., ["jira_url", "jira_token"])
    5. Optionally set mock_data to provide development fixtures
    6. Implement fetch() and test_connection()
    7. Call register_connector(YourConnector) at module level
    8. Import the module in app/connectors/__init__.py

    The system will automatically use the real connector when credentials are
    configured, and fall back to mock data when they're not.
    """

    # Override in subclasses
    connector_type: ClassVar[str] = ""
    required_env: ClassVar[list[str]] = []
    mock_data: ClassVar[dict] = {}

    @abstractmethod
    def fetch(self, config: dict) -> dict:
        """Fetch data needed by evaluators. Returns normalized data."""

    @abstractmethod
    def test_connection(self) -> bool:
        """Verify credentials and connectivity."""


class MockConnector(ConnectorBase):
    """Returns static mock data for development and testing."""

    connector_type = "mock"

    def __init__(self, mock_data: dict | None = None):
        self._mock_data = mock_data or {}

    def fetch(self, config: dict) -> dict:
        return self._mock_data

    def test_connection(self) -> bool:
        return True


def register_connector(cls: type[ConnectorBase]) -> type[ConnectorBase]:
    """Register a connector class in the global registry."""
    if cls.connector_type:
        _CONNECTOR_REGISTRY[cls.connector_type] = cls
    return cls


def get_registered_connectors() -> dict[str, type[ConnectorBase]]:
    """Return all registered connector types."""
    return dict(_CONNECTOR_REGISTRY)
