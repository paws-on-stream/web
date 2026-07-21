"""Registration system synchronization helpers for participants."""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from core.models import Settings
from core.outbound import UnsafeOutboundUrlError, validate_public_https_url
from django.db import close_old_connections, transaction
from django.db.models import Q
from django.utils import timezone

from participants.models import Participant

LOGGER = logging.getLogger(__name__)


class RegSyncError(Exception):
    """Raised when syncing participant status from registration API fails."""


class RegParticipantNotFound(RegSyncError):
    """Raised when the registration system does not know a Telegram ID."""


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
    if payload.get("error") is True or payload.get("success") is False:
        raise RegParticipantNotFound(
            str(
                payload.get("msg")
                or "Participant was not found in the registration system."
            )
        )

    data = _resolve_payload(payload)
    if "checked_in" not in data and "checkedin" not in data and "status" not in data:
        raise RegSyncError(
            "Registration API response must contain checkedin, checked_in or status."
        )

    if "checkedin" in data:
        checked_in_source = data["checkedin"]
    elif "checked_in" in data:
        checked_in_source = data["checked_in"]
    else:
        checked_in_source = data["status"]
    checked_in = _parse_checked_in(checked_in_source)

    reg_id = data.get("reg_id")
    if reg_id is None and "id" in data:
        reg_id = data["id"]
    if reg_id is not None and not isinstance(reg_id, int):
        raise RegSyncError("Registration API returned invalid reg_id type.")

    display_name = data.get("display_name", data.get("nickname"))
    if display_name is not None and not isinstance(display_name, str):
        raise RegSyncError("Registration API returned invalid display_name type.")

    return RegStatus(checked_in=checked_in, reg_id=reg_id, display_name=display_name)


def fetch_reg_status(telegram_id: int, *, timeout: int = 5) -> RegStatus:
    settings = Settings.get_settings()
    base_url = settings.reg_api_url.strip()
    if not base_url:
        raise RegSyncError("Registration API URL is not configured.")

    api_key = settings.reg_api_key.strip()
    if not api_key:
        raise RegSyncError("Registration API key is not configured.")

    parts = urlsplit(base_url)
    query_params = dict(parse_qsl(parts.query, keep_blank_values=True))
    query_params.update({"tg_user_id": str(telegram_id), "key": api_key})
    url = urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query_params),
            parts.fragment,
        )
    )
    try:
        validate_public_https_url(url)
    except UnsafeOutboundUrlError as exc:
        raise RegSyncError(str(exc)) from exc

    request = Request(url=url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            raw_bytes = response.read(1024 * 1024 + 1)
    except HTTPError as exc:
        if exc.code == 404:
            raise RegParticipantNotFound(
                "Participant was not found in the registration system."
            ) from exc
        raise RegSyncError(f"Registration API returned HTTP {exc.code}.") from exc
    except URLError as exc:
        raise RegSyncError("Registration API is unreachable.") from exc
    if len(raw_bytes) > 1024 * 1024:
        raise RegSyncError("Registration API response exceeds 1 MB.")
    try:
        raw = raw_bytes.decode("utf-8")
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RegSyncError("Registration API returned invalid JSON.") from exc

    if not isinstance(payload, dict):
        raise RegSyncError("Registration API response must be a JSON object.")
    return parse_reg_status(payload)


def _apply_reg_status(participant: Participant, status: RegStatus) -> bool:
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


def sync_participant_status(participant: Participant) -> bool:
    status = fetch_reg_status(participant.telegram_id)
    return _apply_reg_status(participant, status)


def sync_participant_by_telegram_id(
    telegram_id: int,
) -> tuple[Participant, bool, bool]:
    """Fetch and upsert a participant by stable Telegram ID.

    Returns ``(participant, changed, created)``. Unknown local participants are
    only created when the registration system supplies a non-empty display name.
    """

    status = fetch_reg_status(telegram_id)
    with transaction.atomic():
        existing = (
            Participant.objects.select_for_update()
            .filter(telegram_id=telegram_id)
            .first()
        )
        if existing is None:
            display_name = (status.display_name or "").strip()
            if not display_name:
                raise RegSyncError(
                    "Registration API must provide display_name for a new participant."
                )
            participant, created = Participant.objects.update_or_create(
                telegram_id=telegram_id,
                defaults={
                    "display_name": display_name,
                    "checked_in": status.checked_in,
                    "reg_id": status.reg_id,
                    "last_status_check": timezone.now(),
                },
            )
            if created:
                return participant, True, True
            existing = participant

        changed = _apply_reg_status(existing, status)
        return existing, changed, False


def _sync_participant_by_id(participant_id: int) -> bool:
    close_old_connections()
    try:
        return sync_participant_status(Participant.objects.get(pk=participant_id))
    finally:
        close_old_connections()


def sync_due_participants(*, workers: int = 1) -> tuple[int, int, int]:
    settings = Settings.get_settings()
    interval_seconds = max(settings.status_check_interval, 1)
    threshold = timezone.now() - timedelta(seconds=interval_seconds)

    participant_ids = list(
        Participant.objects.filter(
            Q(last_status_check__isnull=True) | Q(last_status_check__lte=threshold)
        )
        .order_by("last_status_check", "id")
        .values_list("id", flat=True)
    )

    synced = 0
    changed = 0
    failed = 0
    if workers <= 1:
        for participant_id in participant_ids:
            try:
                was_changed = sync_participant_status(
                    Participant.objects.get(pk=participant_id)
                )
            except (RegSyncError, Participant.DoesNotExist) as exc:
                failed += 1
                LOGGER.warning(
                    "Registration sync failed for participant_id=%s: %s",
                    participant_id,
                    exc,
                )
                continue
            synced += 1
            changed += int(was_changed)
        return synced, changed, failed

    with ThreadPoolExecutor(max_workers=max(1, min(workers, 16))) as executor:
        futures = {
            executor.submit(_sync_participant_by_id, participant_id): participant_id
            for participant_id in participant_ids
        }
        for future in as_completed(futures):
            try:
                was_changed = future.result()
            except (RegSyncError, Participant.DoesNotExist) as exc:
                failed += 1
                LOGGER.warning(
                    "Registration sync failed for participant_id=%s: %s",
                    futures[future],
                    exc,
                )
                continue
            synced += 1
            changed += int(was_changed)
    return synced, changed, failed
