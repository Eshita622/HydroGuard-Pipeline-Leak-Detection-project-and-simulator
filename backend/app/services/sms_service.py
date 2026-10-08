"""Process-local mock SMS delivery. This module never contacts an SMS provider."""

from datetime import datetime, timezone
from threading import Lock
from typing import Any

_messages: list[dict[str, Any]] = []
_lock = Lock()
_next_id = 1
_MAX_MESSAGES = 200


def send_sms(
    phone: str | None,
    message: str,
    *,
    alert_id: str,
    zone: str,
    risk_level: str,
    source: str,
) -> dict[str, Any]:
    """Record a clearly marked mock message and return its log entry."""
    global _next_id
    with _lock:
        item = {
            "id": _next_id,
            "alertId": alert_id,
            "recipient": phone,
            "message": message,
            "zone": zone,
            "riskLevel": risk_level.lower(),
            "source": source.lower(),
            "simulated": source.upper() in ("SIMULATED", "SIMULATOR"),
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        _next_id += 1
        _messages.append(item)
        del _messages[:-_MAX_MESSAGES]
        return dict(item)


def list_sms() -> list[dict[str, Any]]:
    """Return the newest mock SMS entries first."""
    with _lock:
        return [dict(item) for item in reversed(_messages)]


def sms_for_alert(alert_id: int | str) -> dict[str, Any] | None:
    with _lock:
        return next(
            (dict(item) for item in reversed(_messages) if item["alertId"] == str(alert_id)),
            None,
        )


def clear_sms_log() -> None:
    """Test helper; no production HTTP route exposes this operation."""
    global _next_id
    with _lock:
        _messages.clear()
        _next_id = 1
