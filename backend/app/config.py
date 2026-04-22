from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://oculus:oculus@db:5432/oculus"

    # Connectors
    okta_domain: str = ""
    okta_api_token: str = ""
    github_token: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_default_region: str = "us-east-1"

    # Alerting
    slack_webhook_url: str = ""

    # Scheduler
    default_cadence_seconds: int = 21600  # 6 hours

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
