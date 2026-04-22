from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger("oculus.alerting")


def send_slack_alert(message: str, control_name: str, status: str) -> None:
    """Send alert to Slack webhook. Fails silently with logging."""
    if not settings.slack_webhook_url:
        logger.debug("Slack webhook not configured, skipping alert")
        return

    color = "#dc2626" if status == "fail" else "#f59e0b" if status == "error" else "#10b981"

    payload = {
        "attachments": [
            {
                "color": color,
                "blocks": [
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"*OCULUS Alert*\n*Control:* {control_name}\n{message}"},
                    }
                ],
            }
        ]
    }

    try:
        resp = httpx.post(settings.slack_webhook_url, json=payload, timeout=10)
        if resp.status_code != 200:
            logger.warning(f"Slack webhook returned {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.error(f"Failed to send Slack alert: {e}")


def check_and_alert(
    control_name: str,
    previous_status: str | None,
    new_status: str,
    consecutive_failures: int,
    summary: str,
    failing_count: int,
    error_message: str | None = None,
) -> None:
    """Determine if an alert should fire and send it."""
    # pass -> fail transition
    if previous_status == "pass" and new_status == "fail":
        send_slack_alert(
            f"Status changed: *PASS → FAIL*\n{summary}\n_{failing_count} failing resource(s)_",
            control_name,
            "fail",
        )
        return

    # Persistent failure (every 3 consecutive)
    if new_status == "fail" and consecutive_failures > 0 and consecutive_failures % 3 == 0:
        send_slack_alert(
            f"Persistent failure: *{consecutive_failures} consecutive runs*\n{summary}\n_{failing_count} failing resource(s)_",
            control_name,
            "fail",
        )
        return

    # Error
    if new_status == "error":
        send_slack_alert(
            f"Evaluation *error*: {error_message or 'Unknown error'}",
            control_name,
            "error",
        )
