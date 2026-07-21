# Paws on Stream — Web Backend

Django-Webbackend für **Paws on Stream** mit:
- REST API für Messages, Participants, Events, Settings und Devices
- Custom Dashboard (Django Templates + django-tables2)
- Moderations-Workflow (`pending` → `approved`/`rejected`) mit separatem
  gerätespezifischem Display-Feedback

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
- `BOT_API_AUTH_TOKEN` – optionaler, auf Bot-Endpunkte begrenzter Token
- `DISPLAY_API_AUTH_TOKEN` – optionaler, auf Display-Endpunkte begrenzter Token
- `TELEGRAM_OIDC_CLIENT_ID` / `TELEGRAM_OIDC_CLIENT_SECRET` – von BotFather
  ausgestellte Zugangsdaten für den Dashboard-Login
- `TELEGRAM_AUTH_BOOTSTRAP_IDS` – kommaseparierte Telegram-IDs der initialen
  Administratoren; nach dem ersten Login wird die Freigabe in der Datenbank geführt

## API-Überblick

Basis: `/api/v1/`

- `messages/` + Actions: `pending`, `display` (Display-Polling), `{id}/approve`,
  `{id}/reject`, `{id}/displayed` (gerätespezifisches Ack)
- `message/` (Bot-Kompatibilitäts-Alias für `POST`)
- `health/` (`GET`, public, für Bot-/Probe-Checks)
- `media/upload/` (`POST`, multipart Upload für Bot-Media)
- `events/killswitch/` (`POST`, persistente Display-/Regie-Events)
- `participants/` + Action: `participants/{telegram_id}/check_status/`
- `participant/{telegram_id}/ban/`, `participant/{telegram_id}/mute/` (Bot-Aliase)
- `events/`
- `settings/`
- `devices/` + Action: `register`
- `logs/`

Media-Uploads akzeptieren ausschließlich validiertes `image/webp` (statisch oder
animiert), maximal 10 MB, 1280×1280 Pixel, 150 Frames und 10 Sekunden. Die API
liefert eine stabile Asset-ID/URL sowie Format-, Animations-, Größen-, Dauer-,
Frame-, Alpha- und SHA-256-Metadaten. Mediennachrichten referenzieren das Asset
über `media_asset_id`; direkte externe Medien- oder Video-URLs werden abgelehnt.

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

Alle Dashboard-Ansichten einschließlich lesender Seiten erfordern eine aktive
Staff-Sitzung. Die gemeinsame Login-Seite unter `/auth/login/` unterstützt
klassische Django-Staff-Konten und Telegram OpenID Connect.

Telegram-Benutzer starten den OIDC-Flow über die gemeinsame Login-Seite. Beim
ersten Versuch wird automatisch ein inaktiver Zugangsantrag mit der numerischen
Telegram-ID angelegt; der Benutzer bleibt bis zur Freigabe ausgesperrt. Aktive
Admins verwalten die Anträge unter **Dashboard → Zugänge** und vergeben dort die
Rolle Staff oder Admin. Staff erhält Zugriff auf die Moderationsfunktionen, Admin
darf zusätzlich Zugänge freigeben und Rollen ändern. Die numerische Telegram-ID
ist die Identität; der Telegram-Benutzername dient nicht zur Autorisierung. Eine
Deaktivierung beendet eine vorhandene Sitzung bei der nächsten Anfrage. Bot und
Display verwenden weiterhin ihre separaten API-Tokens.

## Reg-System Sync

Es gibt zwei Wege für den Check-in Sync:

1. Einzelner Participant per API:
   - `POST /api/v1/participants/{telegram_id}/check_status/`
2. Periodischer Batch-Sync per Management Command:

```bash
poetry run python paws_on_stream_web/manage.py sync_reg_status
```

Der Batch-Sync berücksichtigt `status_check_interval` aus den Settings und synchronisiert nur fällige Teilnehmer.

Der verbindliche Einzelcheck ist ein mutierender `POST`. Ist die Telegram-ID
lokal unbekannt, fragt das Backend zuerst das Reg-System ab und legt den
Participant bei einer gültigen Antwort an (`201 Created`). `GET` ist für diesen
Endpoint nicht erlaubt.

Fehler einzelner Teilnehmer brechen den Batch nicht ab. Der Command verarbeitet
bis zu 16 Teilnehmer parallel (`--workers`, Standard: 8) und schützt sich über
eine Datenbank-Lease gegen überlappende Läufe.

## Display-Status

Der Nachrichtenstatus bildet ausschließlich die Moderation ab: `pending`,
`approved` oder `rejected`. Ein Display-Ack ändert `approved` nicht, damit weitere
Displays dieselbe Nachricht weiterhin pollen können. `Message.displayed_at`
enthält den Zeitpunkt des ersten Acks; `DisplayLog` ist die maßgebliche
gerätespezifische Historie. Dashboard-Filter für „Shown“ und „Approved, not shown“
werden daraus abgeleitet.

## Web-Display

Staff und Admins öffnen die passive Browser-Vorschau über **Web Display öffnen**
oben rechts im Dashboard. Die Vorschau übernimmt Chat-/Crawling-Modus,
Anzeigedauer, Schriftgröße und Scrollgeschwindigkeit aus den Settings und zeigt
dieselben statischen oder animierten WebP-Assets. Sie registriert kein Device und
erzeugt weder DisplayLogs noch Display-Acknowledgements.

Admins können unter **Web-Display-Link** einen gemeinsamen öffentlichen
Monitoring-Link erzeugen, rotieren oder widerrufen. Der Link wird nur direkt nach
der Erzeugung im Klartext angezeigt. Eine Rotation widerruft auch bereits
geöffnete öffentliche Monitor-Sitzungen.

Das Web-Display verwendet standardmäßig das zentrale Theme `east13`. Es enthält
dieselben drei PNG-Rahmen, dasselbe geordnete Pygame-Template und dieselben
Gestaltungswerte wie das bisher lokal auf dem Pi installierte EAST-Theme. Die
Browserdarstellung bleibt eine bestmögliche Monitoring-Vorschau; Pygame ist der
verbindliche Referenz-Renderer für die 1920×1080-Ausgabe.
`overlay_theme` ist der gemeinsame Theme-Schalter für Pi und Web-Vorschau, damit
das Monitoring nicht unbemerkt von der Live-Darstellung abweicht.

Display-Clients mit Display-Token laden das validierte Manifest und die darin
deklarierten Assets über:

```text
GET /api/v1/themes/east13/
GET /api/v1/themes/east13/3.0.0/assets/chat_top/
GET /api/v1/themes/east13/3.0.0/assets/chat_middle/
GET /api/v1/themes/east13/3.0.0/assets/chat_bottom/
```

Jedes Asset enthält Maße, Alpha-Metadatum und SHA-256. Das Backend prüft beim
Laden außerdem tatsächliches PNG-Format, Abmessungen, Prüfsumme, sichere relative
Pfade und die erlaubten Template-Felder. Details zum Vertrag stehen in
[`docs/theme-schema-v3.md`](docs/theme-schema-v3.md). Die Raspberry-Pi-Clients
verwenden weiterhin ihre lokalen Themes, bis dort Download, atomare Aktivierung
und lokaler Fallback-Cache umgesetzt sind.

Admins verwalten Themes unter `/core/themes/`. Dort können vollständige
Schema-v3-Pakete als ZIP importiert, versioniert, für Pi und Web gemeinsam
aktiviert und wieder gelöscht werden. Aktive Versionen sind gegen Löschen
geschützt. Hochgeladene Assets liegen in der persistenten Media-Storage; diese
muss im Deployment ebenso dauerhaft eingebunden sein wie Nachrichtenmedien.

## Event-Sync

Die externe Event-API und ein jq-Filter werden in den Settings konfiguriert.
Der Filter muss eine JSON-Liste zurückgeben. Events werden über ihre externe ID
idempotent angelegt beziehungsweise aktualisiert:

```bash
poetry run python paws_on_stream_web/manage.py sync_events
```

Die Synchronisierung ändert Name, Start und Ende. Lokale Moderationsfelder wie
Aktivstatus, Display-Modus und `allow_messages` bleiben bei Updates erhalten.
Beide Sync-Commands besitzen ein Datenbank-Lock. Beispiel-CronJobs für Kubernetes
liegen unter `deploy/k8s/sync-cronjobs.yaml`.

## Entwicklung

## Container-Image

Der Workflow `.github/workflows/container-image.yml` baut das Produktionsimage
bei Pull Requests ohne Push. Pushes auf den Default-Branch und Tags mit Präfix
`v` veröffentlichen es unter:

```text
ghcr.io/paws-on-stream/web
```

Der Default-Branch erhält `latest`, jeder veröffentlichte Build zusätzlich einen
unveränderlichen `sha-<commit>`-Tag. Versionstags wie `v1.2.3` erzeugen außerdem
`1.2.3` und `1.2`. Für ein reproduzierbares Deployment sollte in den Kubernetes-
Manifesten ein `sha-…`-Tag statt `latest` verwendet werden. Private GHCR-Pakete
benötigen im Cluster ein `imagePullSecret`; alternativ kann das Paket in GitHub
öffentlich geschaltet werden.

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
