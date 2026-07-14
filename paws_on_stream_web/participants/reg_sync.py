"""Registration system synchronization helpers for participants."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from core.models import Settings
from django.db.models import Q
from django.utils import timezone

from participants.models import Participant


class RegSyncError(Exception):
    """Raised when syncing participant status from registration API fails."""


@dataclass(frozen=True)
class RegStatus:
    checked_in: bool
    reg_id: int | None
    display_name: str | None = None


def _resolve_payload(payload: dict) -> dict:
    if "participant" in payload and isinstance(payload["participant"], dict):
        return payload["participant"]
    if "data" in payload and isinstance(payload["data"], dict):
        return payload["data"]
    return payload


def _parse_checked_in(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        return normalized in {
            "checked_in",
            "checkedin",
            "present",
            "active",
            "true",
            "1",
        }
    if isinstance(value, int):
        return value == 1
    raise RegSyncError("Registration API returned invalid checked_in value.")


def parse_reg_status(payload: dict) -> RegStatus:
    data = _resolve_payload(payload)
    if "checked_in" not in data and "status" not in data:
        raise RegSyncError(
            "Registration API response must contain checked_in or status."
        )

    checked_in_source = data["checked_in"] if "checked_in" in data else data["status"]
    checked_in = _parse_checked_in(checked_in_source)

    reg_id = data.get("reg_id")
    if reg_id is None and "id" in data:
        reg_id = data["id"]
    if reg_id is not None and not isinstance(reg_id, int):
        raise RegSyncError("Registration API returned invalid reg_id type.")

    display_name = data.get("display_name")
    if display_name is not None and not isinstance(display_name, str):
        raise RegSyncError("Registration API returned invalid display_name type.")

    return RegStatus(checked_in=checked_in, reg_id=reg_id, display_name=display_name)


def fetch_reg_status(telegram_id: int, *, timeout: int = 5) -> RegStatus:
    settings = Settings.get_settings()
    base_url = settings.reg_api_url.strip()
    if not base_url:
        raise RegSyncError("Registration API URL is not configured.")

    query = urlencode({"telegram_id": telegram_id})
    separator = "&" if "?" in base_url else "?"
    url = f"{base_url}{separator}{query}"

    headers = {"Accept": "application/json"}
    if settings.reg_api_key.strip():
        headers["X-API-Token"] = settings.reg_api_key.strip()

    request = Request(url=url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        raise RegSyncError(f"Registration API returned HTTP {exc.code}.") from exc
    except URLError as exc:
        raise RegSyncError("Registration API is unreachable.") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RegSyncError("Registration API returned invalid JSON.") from exc

    if not isinstance(payload, dict):
        raise RegSyncError("Registration API response must be a JSON object.")
    return parse_reg_status(payload)


def sync_participant_status(participant: Participant) -> bool:
    status = fetch_reg_status(participant.telegram_id)
    now = timezone.now()

    changed = False
    update_fields = ["last_status_check"]

    if participant.checked_in != status.checked_in:
        participant.checked_in = status.checked_in
        update_fields.append("checked_in")
        changed = True

    if participant.reg_id != status.reg_id:
        participant.reg_id = status.reg_id
        update_fields.append("reg_id")
        changed = True

    if status.display_name and status.display_name.strip():
        normalized_name = status.display_name.strip()
        if participant.display_name != normalized_name:
            participant.display_name = normalized_name
            update_fields.append("display_name")
            changed = True

    participant.last_status_check = now
    participant.save(update_fields=update_fields)
    return changed


def sync_due_participants() -> tuple[int, int]:
    settings = Settings.get_settings()
    interval_seconds = max(settings.status_check_interval, 1)
    threshold = timezone.now() - timedelta(seconds=interval_seconds)

    due_participants = Participant.objects.filter(
        Q(last_status_check__isnull=True) | Q(last_status_check__lte=threshold)
    ).order_by("last_status_check", "id")

    synced = 0
    changed = 0
    for participant in due_participants:
        was_changed = sync_participant_status(participant)
        synced += 1
        if was_changed:
            changed += 1
    return synced, changed
