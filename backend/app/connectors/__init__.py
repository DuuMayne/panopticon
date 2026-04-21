# Import all connector modules to trigger @register_connector decorators.
# To add a new connector, create a file here and import it below.
from app.connectors.okta import OktaConnector  # noqa: F401
from app.connectors.github import GitHubConnector  # noqa: F401
from app.connectors.aws import AWSConnector  # noqa: F401
from app.connectors.aws_iam import AWSIAMConnector  # noqa: F401
from app.connectors.aws_s3 import AWSS3Connector  # noqa: F401
