# Paws on Stream — Web Backend

Django-Webbackend für **Paws on Stream** mit:
- REST API für Messages, Participants, Events, Settings und Devices
- Custom Dashboard (Django Templates + django-tables2)
- Moderations-Workflow (pending → approved/rejected → displayed)

## Voraussetzungen

- Python 3.12+
- Poetry
- Node.js + npm (für CSS/JS-Build)
- PostgreSQL (optional in Dev; SQLite ist als Fallback konfiguriert)

## Lokales Setup

```bash
cp .env_example .env
poetry install
npm ci
npm run build
poetry run python paws_on_stream_web/manage.py migrate
poetry run python paws_on_stream_web/manage.py runserver
```

App läuft dann unter `http://127.0.0.1:8000/`.

## Wichtige Umgebungsvariablen

In `.env`:

- `SECRET_KEY` – Django Secret
- `DEBUG` – `True` oder `False`
- `DATABASE_URL` – z. B. `postgres://...` oder `sqlite:///db.sqlite3`
- `API_AUTH_TOKEN` – Token für alle `/api/` Requests (`X-API-Token` Header)

## API-Überblick

Basis: `/api/v1/`

- `messages/` + Actions: `pending`, `display`, `displayed`, `{id}/approve`, `{id}/reject`, `{id}/displayed`
- `participants/` + Action: `participants/{telegram_id}/check_status/`
- `events/`
- `settings/`
- `devices/` + Action: `register`
- `logs/`

Beispiel:

```bash
curl -H "X-API-Token: $API_AUTH_TOKEN" http://127.0.0.1:8000/api/v1/messages/pending/
```

## Dashboard & UI

- Dashboard Startseite: `/`
- Messages UI: `/streaming/messages/`
- Participants UI: `/participants/participants/`
- Events UI: `/streaming/events/`
- Settings UI: `/core/settings/`

## Reg-System Sync

Es gibt zwei Wege für den Check-in Sync:

1. Einzelner Participant per API:
   - `GET /api/v1/participants/{telegram_id}/check_status/`
2. Periodischer Batch-Sync per Management Command:

```bash
poetry run python paws_on_stream_web/manage.py sync_reg_status
```

Der Batch-Sync berücksichtigt `status_check_interval` aus den Settings und synchronisiert nur fällige Teilnehmer.

## Entwicklung

### Tests

```bash
poetry run python paws_on_stream_web/manage.py test
```

### Linting

```bash
poetry run ruff check paws_on_stream_web
```

### Frontend Assets neu bauen

```bash
npm run build
```

## Nützliche Scripts

- `paws_on_stream_web/scripts/paws-bot-sim.sh`  
  Simuliert Bot→API-Flows (send, approve, reject, pending, settings, devices, logs).

## Projektstruktur (kurz)

- `paws_on_stream_web/streaming/` – Message/Event-Modelle + API
- `paws_on_stream_web/participants/` – Participant-Modelle + API + Reg-Sync
- `paws_on_stream_web/core/` – Settings, DisplayDevice, DisplayLog
- `paws_on_stream_web/dashboard/` – Dashboard Views/Templates
- `frontend_src/` – SCSS/JS Quellcode
- `paws_on_stream_web/static/` – gebaute Assets
