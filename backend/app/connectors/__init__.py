# Import all connector modules to trigger @register_connector decorators.
# To add a new connector, create a file here and import it below.
from app.connectors.okta import OktaConnector  # noqa: F401
from app.connectors.github import GitHubConnector  # noqa: F401
from app.connectors.aws import AWSConnector  # noqa: F401
