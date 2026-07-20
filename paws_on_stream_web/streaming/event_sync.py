"""Synchronization of externally managed convention events."""

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import jq
from core.models import Settings
from core.outbound import UnsafeOutboundUrlError, validate_public_https_url
from django.db import transaction
from django.utils.dateparse import parse_datetime

from streaming.models import Event

MAX_RESPONSE_BYTES = 5 * 1024 * 1024


class EventSyncError(RuntimeError):
    pass


@dataclass(frozen=True)
class EventSyncSummary:
    received: int
    created: int
    updated: int
    skipped: int


def fetch_event_payload(*, timeout: int = 10):
    settings = Settings.get_settings()
    url = settings.event_api_url.strip()
    if not url:
        raise EventSyncError("Event API URL is not configured.")
    try:
        validate_public_https_url(url)
    except UnsafeOutboundUrlError as exc:
        raise EventSyncError(str(exc)) from exc
    request = Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        raise EventSyncError(f"Event API returned HTTP {exc.code}.") from exc
    except URLError as exc:
        raise EventSyncError("Event API is unreachable.") from exc
    if len(raw) > MAX_RESPONSE_BYTES:
        raise EventSyncError("Event API response exceeds 5 MB.")
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EventSyncError("Event API returned invalid JSON.") from exc


def apply_event_filter(payload, expression: str):
    expression = expression.strip() or "."
    try:
        result = jq.compile(expression).input(payload).first()
    except (ValueError, StopIteration) as exc:
        raise EventSyncError(f"Event jq filter failed: {exc}") from exc
    if not isinstance(result, list):
        raise EventSyncError("Event jq filter must return a JSON array.")
    return result


def _parse_event(item: object):
    if not isinstance(item, dict):
        return None
    external_id = item.get("id")
    name = item.get("name")
    starts_at = parse_datetime(str(item.get("start", "")))
    ends_at = parse_datetime(str(item.get("end", "")))
    if external_id is None or not isinstance(name, str) or not name.strip():
        return None
    if starts_at is None or ends_at is None:
        return None
    if starts_at.tzinfo is None or ends_at.tzinfo is None:
        return None
    if ends_at <= starts_at:
        return None
    return str(external_id), name.strip(), starts_at, ends_at


def sync_events() -> EventSyncSummary:
    settings = Settings.get_settings()
    payload = fetch_event_payload()
    filtered = apply_event_filter(payload, settings.event_api_jsonq_filter)
    created = updated = skipped = 0
    seen_ids: set[str] = set()

    with transaction.atomic():
        for item in filtered:
            parsed = _parse_event(item)
            if parsed is None:
                skipped += 1
                continue
            external_id, name, starts_at, ends_at = parsed
            if external_id in seen_ids:
                skipped += 1
                continue
            seen_ids.add(external_id)
            event, was_created = Event.objects.update_or_create(
                external_id=external_id,
                defaults={"name": name, "starts_at": starts_at, "ends_at": ends_at},
            )
            if was_created:
                created += 1
            else:
                updated += 1

    return EventSyncSummary(
        received=len(filtered), created=created, updated=updated, skipped=skipped
    )
