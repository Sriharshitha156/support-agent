"""Structured audit logging to a local JSON file."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_AUDIT_PATH = Path(__file__).resolve().parents[2] / "data" / "audit_log.json"


def _audit_path() -> Path:
    configured = os.getenv("AUDIT_LOG_PATH")
    return Path(configured) if configured else DEFAULT_AUDIT_PATH


def _read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _write_events(path: Path, events: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(events, handle, indent=2)


def log_event(event_type: str, details: dict[str, Any], risk_level: str = "low") -> dict[str, Any]:
    """
    Append an audit event to `data/audit_log.json`.

    Args:
        event_type: Category such as intent_detection, tool_call, escalation.
        details: Structured payload for the event.
        risk_level: low | medium | high
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "details": details,
        "risk_level": risk_level,
    }

    path = _audit_path()
    events = _read_events(path)
    events.append(entry)
    _write_events(path, events)
    return entry


def get_recent_audit_logs(limit: int = 10) -> list[dict[str, Any]]:
    """Return the most recent audit events for demo / governance views."""
    events = _read_events(_audit_path())
    if limit <= 0:
        return []
    return events[-limit:]
