# Telegram Bot Component — Implementation Plan

> Based on Obsidian notes: `Streaming Bot EAST.md` + Web component repo structure.
> Goal: Build the Telegram Bot as a **standalone repo** managed with **Poetry** + **Ruff** (same conventions as the Web component).

---

## 1. Repo Setup

**Repository:** `paws-on-stream/bot` (separate from `paws-on-stream/web`)

**Directory structure:**
```
bot/
├── pyproject.toml
├── .ruff.toml
├── .github/
│   └── workflows/
│       ├── ruff.yml
│       └── django-tests.yml
├── paws_bot/
│   ├── __init__.py
│   ├── bot.py                # Bot API wrapper
│   ├── handlers.py           # Message dispatch + pipeline
│   ├── converters.py         # Sticker → GIF conversion
│   ├── reg_sync.py           # Reg-System status check
│   ├── settings.py           # Bot config (tokens, admin IDs)
│   ├── main.py               # Entry point (webhook + polling modes)
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_handlers.py
│   │   ├── test_converters.py
│   │   ├── test_reg_sync.py
│   │   └── test_bot.py
│   └── management/
│       ├── __init__.py
│       └── commands/
│           ├── __init__.py
│           └── run_bot.py    # Management command
└── Dockerfile
```

---

## 2. Dependencies (`pyproject.toml`)

Mirror the Web component's structure:

```toml
[project]
name = "paws-on-stream-bot"
version = "0.1.0"
description = "Telegram Bot for Paws on Stream — receives messages, validates, pushes to Django API"
authors = [
  { name = "Daniel Bacher", email = "daniel.bacher@kit.edu" }
]
requires-python = ">=3.12"
dependencies = [
  "python-telegram-bot (>=22.0,<23.0)",
  "httpx (>=0.28.0,<1.0.0)",           # Async HTTP client for API calls
  "python-decouple (>=3.8,<4.0)",        # Env config (same as Web)
  "aiofiles (>=24.1,<25.0)",             # Async file I/O for sticker conversion
]

[build-system]
requires = ["poetry-core>=2.0.0,<3.0.0"]
build-backend = "poetry.core.masonry.api"

[dependency-groups]
dev = [
  "ruff (>=0.15.0,<0.16.0)",
  "coverage (>=7.14.1,<8.0.0)",
  "pytest (>=8.3,<9.0)",
  "pytest-asyncio (>=0.24,<0.26)",
]
```

---

## 3. Ruff Config (`.ruff.toml`)

Identical to Web component:

```toml
target-version = "py312"
line-length = 88
extend-exclude = ["*/migrations/*"]

[lint]
select = [
  "E",   # pycodestyle errors
  "W",   # pycodestyle warnings
  "F",   # Pyflakes
  "I",   # isort
  "UP",  # pyupgrade
  "SIM", # flake8-simplify
  "DJ",  # flake8-django
]
ignore = []
```

---

## 4. Bot Architecture

### 4.1 Transport: **Webhook** (primary)

Per Obsidian §2.1: **Webhook mode** is the transport choice — not long-polling.

- Lower latency, no long-polling overhead
- Easier to deploy in Kubernetes
- Bot exposes `/webhook/<BOT_TOKEN>` endpoint

**Fallback:** `run_bot.py --polling` for local development/testing.

### 4.2 Bot Config (`settings.py`)

```python
# Environment variables (same pattern as Web component)
import decouple

BOT_TOKEN = decouple.config("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = decouple.config("TELEGRAM_WEBHOOK_URL", default="")
API_BASE_URL = decouple.config("API_BASE_URL", default="http://localhost:8000")
API_BOT_TOKEN = decouple.config("API_AUTH_TOKEN", default="")
ADMIN_TELEGRAM_IDS = [int(x) for x in decouple.config("ADMIN_TELEGRAM_IDS", default="").split(",") if x.strip()]

# Sticker conversion
STICKER_MAX_SIZE = (192, 192)
STICKER_MAX_FPS = 10
STICKER_CACHE_DIR = "/tmp/stickers-cache/"

# Reg-System
REG_API_URL = decouple.config("REG_API_URL", default="https://east.sachsenfurs.de/?page=TelegramInfo")
REG_API_KEY = decouple.config("REG_API_KEY", default="")
REG_CHECK_INTERVAL = decouple.config("REG_CHECK_INTERVAL", cast=int, default=300)
```

---

## 5. Message Processing Pipeline (`handlers.py`)

The core pipeline. One function `async def handle_update(update: Update, bot: Bot)`:

### 5a. Command Detection

Check for bot commands first:

| Command | Handler | Description |
|---------|---------|-------------|
| `/start` | `cmd_start` | Welcome message + check Reg-System status |
| `/status` | `cmd_status` | Bot status + current event + participant's Reg-System info |
| `/help` | `cmd_help` | List commands + usage |
| `/events` | `cmd_events` | List active + upcoming events |
| `/ban <tg_id>` | `cmd_ban` | Ban participant (Admin only) |
| `/mute <tg_id> <min>` | `cmd_mute` | Mute participant for N minutes (Admin only) |
| `/online` | `cmd_online` | Set bot status to `online` (Admin only) |
| `/offline` | `cmd_offline` | Set bot status to `offline` (Admin only) |
| `/maintenance` | `cmd_maintenance` | Set bot status to `maintenance` (Admin only) |

### 5b. Pipeline for Messages

Run these checks **in order** (from Obsidian §4.1):

1. **Bot Status** → If `offline` or `maintenance`: reject with reason `offline`
2. **Active Event** → If no event `is_active=True` and `require_event_active=True`: reject with reason `no_event`
3. **Participant Lookup** → `Participant.objects.get_or_create(telegram_id=user.id, defaults={display_name})`
4. **Ban Check** → If `participant.banned`: reject with reason `banned`
5. **Mute Check** → If `participant.muted_until > now`: reject with reason `rate_limit`
6. **Rate Limit** → Count messages in last 60s: if `>= rate_limit_per_minute`: reject with reason `rate_limit`
7. **Content Detection** → Detect media type + extract content (see §5c)
8. **Sanitization** → Use API's sanitization endpoint or local copy (HTML strip, zero-width, emoji limit)
9. **Create Message** → `POST /api/v1/message/` with payload
10. **Reply to User** → Status message based on result

### 5c. Media Type Detection + Content Extraction

From `update.effective_message`:

| Media | Detection | `media_type` | `content` | `media_url` | `sticker_emoji` |
|-------|-----------|-------------|-----------|-------------|-----------------|
| **Text** | `message.text` | `text` | `message.text` | `""` | `""` |
| **Photo** | `message.photo` | `photo` | `message.caption or ""` | URL of largest photo via `bot.get_file_url()` | `""` |
| **GIF** | `message.animation` | `gif` | `""` | URL via `bot.get_file_url()` | `""` |
| **Sticker** | `message.sticker` | `sticker` | `""` | URL via conversion (§5.7) | `message.sticker.emoji or ""` |

### 5d. Sticker Conversion (Bot-Side) — `converters.py`

Per Obsidian §5.7: **All stickers are converted to GIFs by the bot** before pushing to the API.

| Format | Detection | Conversion | Tool |
|--------|-----------|------------|------|
| **TGS** (Telegram Animated) | `sticker.is_animated` | JSON → GIF | `tgs2gif` (Node.js) |
| **WebM** (Video Sticker) | `sticker.is_video` | WebM → GIF | `ffmpeg -i input.webm -vf fps=10 output.gif` |
| **WebP** (Animated) | `sticker.is_animated` | WebP → GIF | `ffmpeg -i input.webp output.gif` |
| **PNG** (Raster) | Default | None needed | Direct PNG URL |

**Workflow:**
1. Bot receives sticker → downloads original from Telegram CDN (`media_url`)
2. Detect format (`sticker.is_animated`, `sticker.is_video`)
3. Convert to GIF (max 192×192px, max 10fps)
4. Cache in `/tmp/stickers-cache/<sticker_file_id>.gif` (or `.png` for raster)
5. Send `POST /api/v1/message/` with `media_type=sticker` + converted URL

**Caching:**
- Cache by `sticker_file_id` — unique per sticker
- Cleared on bot restart (Telegram files expire after 48h anyway)
- Optional: persistent cache via K8s shared volume

**Dependencies in Dockerfile:**
```dockerfile
RUN apt-get update && apt-get install -y ffmpeg
RUN npm install -g tgs2gif
```

### 5e. Reg-System Status Check — `reg_sync.py`

Per Obsidian §5.5: Check-in is automatic via Reg-System API.

**API:**
```
https://east.sachsenfurs.de/?page=TelegramInfo&tg_user_id={telegram_id}&key={API_KEY}
```

**Response (known participant):**
```json
{"success": true, "reg_id": 1, "nickname": "XXXX", "payment_status": "paid", "checkedin": false}
```

**Response (unknown):**
```json
{"error": true, "msg": "invalid telegram id"}
```

**Behavior:**
1. On `/start` or first message → query Reg-System API
2. `success=true` → create/update Participant (`reg_id`, `display_name`, `checked_in`)
3. `error=true` → reject with reason `unknown`
4. Re-check every `REG_CHECK_INTERVAL` seconds (default: 300 = 5min)
5. Only `success=true` **AND** `checkedin=true` → user can send messages

**Implementation:**
- Async HTTP call with `httpx.AsyncClient`
- Cache Reg-System results in-memory with TTL (use `REG_CHECK_INTERVAL` as TTL)
- If API is down → fall back to last known status (don't reject participants)

### 5f. Rejection Replies

Per Obsidian §5.3:

| Reason | Telegram Reply |
|--------|---------------|
| `no_event` | "Aktuell ist kein Event aktiv. Versuche es während eines Events nochmal! 🐾" |
| `unknown` | "👋 Hi! Wir finden dich nicht in der Registrierungsliste. Verknüpfe zuerst deinen Telegram-Account im Reg-System, dann kannst du Nachrichten senden!" |
| `not_checkedin` | "⚠️ Du bist aktuell nicht auf der Convention eingecheckt. Check bitte an der Reg ein!" |
| `offline` | "🔴 Der Bot ist aktuell offline. Versuche es später nochmal!" |
| `banned` | "🚫 Du wurdest von der Moderation gesperrt." |
| `rate_limit` | "⏳ Moment mal! Du schreibst zu schnell. Warte kurz." |
| `content_violation` | "⚠️ Deine Nachricht wurde wegen des Inhalts abgelehnt." |

---

## 6. API Integration

The bot pushes messages to the Django API via `POST /api/v1/message/`:

```json
{
  "telegram_id": 123456789,
  "display_name": "FurryName",
  "content": "Hey everyone! 🐾",
  "media_type": "text",
  "media_url": "",
  "sticker_emoji": ""
}
```

**Auth:** `X-API-Token: {API_AUTH_TOKEN}` header.

**Response 201:**
```json
{"id": 42, "status": "pending", "message": "Nachricht erhalten, wartet auf Review"}
```

**Response 4xx:**
```json
{"status": "rejected", "reason": "not_checkedin", "message": "..."}
```

---

## 7. Management Command (`run_bot.py`)

**Polling Mode (local dev):**
```bash
python -m paws_bot.main --polling
```
Async polling loop with timeout=10s, graceful shutdown on `KeyboardInterrupt`.

**Webhook Mode (production):**
```bash
python -m paws_bot.main --webhook
```
Starts an async HTTP server (e.g., `aiohttp` or `httpx`) that listens on `/webhook/{BOT_TOKEN}`.

**Arguments:**
- `--polling` — Use long-polling mode
- `--webhook` — Use webhook mode (production)
- `--port` — HTTP server port (default: 8000)

---

## 8. Health Checks (K8s Probes)

Per Obsidian §2.0:

| Endpoint | Checks |
|----------|--------|
| `GET /health` | Process alive, DB connection, API responsiveness |
| `GET /readiness` | Bot status, webhook configured, DB reachable, cache connected |

K8s uses `/health` for `livenessProbe` and `/readiness` for `readinessProbe`.

---

## 9. Testing Strategy

**Ziel:** Jede Komponente wird mit **Unit-Tests** abgedeckt. Integration-Tests nur wo externe Abhängigkeiten unvermeidbar sind (API calls, Sticker-Konvertierung).

**Tools:** `pytest` + `pytest-asyncio` + `coverage` (alle in `pyproject.toml` dev-dependencies)
**Coverage-Ziel:** ≥ 80% overall (enforced in CI)

### 9.1 Test-Dateien pro Komponente

| Datei | Komponente | Fokus |
|-------|-----------|-------|
| `test_bot.py` | `bot.py` | Token-Config, Webhook-Setup, Polling-Start/Stop, Health-Endpoints |
| `test_handlers.py` | `handlers.py` | Command-Dispatch, Message-Pipeline, Media-Detection, Rejection-Reasons |
| `test_converters.py` | `converters.py` | TGS→GIF, WebM→GIF, WebP→GIF, PNG pass-through, Cache-Hits/Misses |
| `test_reg_sync.py` | `reg_sync.py` | API-Calls (mocked), Response-Parsing, Cache-TTL, Fallback bei API-Timeout |
| `test_settings.py` | `settings.py` | Env-Var-Loading, Default-Werte, ADMIN_TELEGRAM_IDS Parsing |
| `test_main.py` | `main.py` | CLI-Args (--polling/--webhook/--port), Graceful Shutdown, Signal-Handling |
| `test_pipeline_integration.py` | Full pipeline | End-to-End: Update → Pipeline → API-POST → Reply (mit mocked API) |

### 9.2 Mock-Strategie

| Abhängigkeit | Mock-Tool | Beispiel |
|-------------|-----------|---------|
| **HTTP calls** (API, Reg-System) | `pytest-httpx` / `unittest.mock.AsyncMock` | API `POST /message/` → mock response 201 |
| **Telegram Update-Objekte** | Factory-Funktionen | `build_text_update(telegram_id=123, text="Hello")` |
| **Sticker-Dateien** | `io.BytesIO` mit Test-Assets | Kleine TGS/WebM/WebP/PNG Files im `tests/assets/` |
| **Filesystem** (Cache) | `tmp_path` (pytest fixture) | `/tmp/stickers-cache/` → temp dir pro Test |

### 9.3 Test-Cases pro Datei

#### `test_bot.py` — 6 Tests
| Test | Beschreibung |
|------|-------------|
| `test_bot_token_loaded` | Token aus Env-Var wird korrekt geladen |
| `test_webhook_url_set` | Webhook-URL wird korrekt an Telegram gesendet |
| `test_polling_start_stop` | Polling-Loop startet und stoppt auf Signal |
| `test_health_endpoint_ok` | `GET /health` → 200 OK |
| `test_readiness_endpoint_ok` | `GET /readiness` → 200 OK (API reachable) |
| `test_readiness_endpoint_down` | `GET /readiness` → 503 (API down) |

#### `test_handlers.py` — 18 Tests
| Test | Beschreibung |
|------|-------------|
| `test_dispatch_text_message` | Text-Nachricht → Pipeline aufgerufen |
| `test_dispatch_photo_message` | Foto mit Caption → media_type="photo" |
| `test_dispatch_gif_message` | GIF → media_type="gif" |
| `test_dispatch_sticker_message` | Sticker → media_type="sticker", emoji gesetzt |
| `test_dispatch_command_start` | `/start` → Reg-System Check |
| `test_dispatch_command_status` | `/status` → Bot-Status + Event-Info |
| `test_dispatch_command_help` | `/help` → Hilfe-Text |
| `test_dispatch_command_events` | `/events` → Event-Liste |
| `test_dispatch_command_ban` | `/ban <id>` → Participant gesperrt |
| `test_dispatch_command_mute` | `/mute <id> <min>` → Participant gemuted |
| `test_dispatch_command_online` | `/online` → Bot-Status = online |
| `test_dispatch_command_offline` | `/offline` → Bot-Status = offline |
| `test_dispatch_command_maintenance` | `/maintenance` → Bot-Status = maintenance |
| `test_reject_bot_offline` | Bot offline → Rejection mit Reason "offline" |
| `test_reject_no_event` | Kein Event + require_event_active → Rejection "no_event" |
| `test_reject_banned` | Gebannter Participant → Rejection "banned" |
| `test_reject_muted` | Gemutter Participant → Rejection "rate_limit" |
| `test_reject_rate_limit` | >N Messages in 60s → Rejection "rate_limit" |

#### `test_converters.py` — 8 Tests
| Test | Beschreibung |
|------|-------------|
| `test_convert_tgs_to_gif` | TGS Animated Sticker → GIF, max 192×192 |
| `test_convert_webm_to_gif` | WebM Video Sticker → GIF, max 10fps |
| `test_convert_webp_animated_to_gif` | Animated WebP Sticker → GIF |
| `test_convert_png_sticker` | PNG Sticker → keine Konvertierung, URL direkt |
| `test_cache_hit_same_file_id` | Gleicher Sticker → aus Cache, kein zweiter Konvertierungslauf |
| `test_cache_miss_different_file_id` | Verschiedene Sticker → beide konvertiert |
| `test_fallback_on_conversion_error` | Konvertierungsfehler → Sticker als Photo gesendet |
| `test_sticker_max_dimensions` | Konvertiertes GIF ≤ 192×192px |

#### `test_reg_sync.py` — 7 Tests
| Test | Beschreibung |
|------|-------------|
| `test_reg_known_participant` | Known participant → reg_id, nickname, checked_in gesetzt |
| `test_reg_unknown_participant` | Unknown participant → Rejection "unknown" |
| `test_reg_checkin_true` | `checkedin=true` → Message akzeptiert |
| `test_reg_checkin_false` | `checkedin=false` → Rejection "not_checkedin" |
| `test_reg_cache_ttl_hit` | Zweiter Request innerhalb TTL → Cache-Hit |
| `test_reg_cache_ttl_expired` | Request nach TTL → neuer API-Call |
| `test_reg_api_timeout_fallback` | Reg-System down → letzter Status verwendet |

#### `test_settings.py` — 4 Tests
| Test | Beschreibung |
|------|-------------|
| `test_env_vars_loaded` | Alle Env-Vars werden korrekt geladen |
| `test_default_values` | Missing Env-Vars → Default-Werte verwendet |
| `test_admin_ids_parsed` | `ADMIN_TELEGRAM_IDS` String → List[int] |
| `test_empty_admin_ids` | Leerer String → leere Liste |

#### `test_main.py` — 3 Tests
| Test | Beschreibung |
|------|-------------|
| `test_cli_args_polling` | `--polling` → Polling-Modus gestartet |
| `test_cli_args_webhook` | `--webhook` → Webhook-Modus gestartet |
| `test_graceful_shutdown_signal` | SIGINT/SIGTERM → Polling/Server sauber gestoppt |

#### `test_pipeline_integration.py` — 9 Tests
| Test | Beschreibung |
|------|-------------|
| `test_full_pipeline_text` | Text → Pipeline → API POST → Reply "pending" |
| `test_full_pipeline_photo` | Foto → Pipeline → API POST mit media_url → Reply |
| `test_full_pipeline_auto_approve` | Auto-approve=True → Message direkt approved |
| `test_full_pipeline_sticker` | Sticker → Konvertierung → API POST mit GIF URL → Reply |
| `test_full_pipeline_banned` | Gebannter → API POST mit Ban-Check → Reply "banned" |
| `test_api_timeout` | API timeout → Retry → Reply "offline" |
| `test_message_sanitized` | HTML + zero-width chars → gesäubert vor API POST |
| `test_message_truncated` | >4096 chars → truncated auf max_message_length |
| `test_emoji_count_spam_score` | >10 Emojis → spam_score erhöht |

### 9.4 CI Enforcement

**`.github/workflows/django-tests.yml`:**
```yaml
- name: Run tests
  run: |
    poetry run pytest --asyncio-mode=auto --cov=paws_bot --cov-report=term-missing -v
- name: Check coverage
  run: |
    poetry run coverage report --fail-under=80
```

**`.github/workflows/ruff.yml`:**
```yaml
- name: Run Ruff
  run: |
    poetry run ruff check .
    poetry run ruff format --check .
```

---

## 10. Docker + K8s

### Dockerfile

```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y ffmpeg
RUN npm install -g tgs2gif

WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry install --only=main --no-root
COPY . .

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "-m", "paws_bot.main", "--webhook", "--port", "8000"]
```

### K8s Deployment (conceptual)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: paws-bot
spec:
  replicas: 1
  template:
    spec:
      containers:
        - name: bot
          image: paws-on-stream/bot:latest
          ports:
            - containerPort: 8000
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /readiness
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
          envFrom:
            - secretRef:
                name: paws-bot-secrets
          volumeMounts:
            - name: sticker-cache
              mountPath: /tmp/stickers-cache
      volumes:
        - name: sticker-cache
          emptyDir: {}
```

---

## 11. Implementation Order

> **Jeder Schritt wird parallel mit Unit-Tests entwickelt.** Kein Code ohne Tests ins Repo.
>
> 1. **Repo scaffold** — `pyproject.toml`, `.ruff.toml`, `settings.py`, directory structure + `test_settings.py`
> 2. **`bot.py`** + `test_bot.py` — Token config, Webhook/Polling wrapper, Health-Endpoints
> 3. **`handlers.py`** + `test_handlers.py` — Pipeline, Command-Dispatch, Rejection-Reasons (18 Tests)
> 4. **`converters.py`** + `test_converters.py` — Sticker conversion + Cache (8 Tests)
> 5. **`reg_sync.py`** + `test_reg_sync.py` — Reg-System API + Cache-TTL (7 Tests)
> 6. **`main.py`** + `test_main.py` — Entry point, CLI-Args, Graceful Shutdown (3 Tests)
> 7. **`run_bot.py`** — Management command for local dev
> 8. **Integration Tests** — `test_pipeline_integration.py` (9 Tests, mocked API)
> 9. **Dockerfile + K8s manifests** — Container build + deployment config
> 10. **End-to-end test** — Run bot locally, send messages from test bot, verify API receives them

---

## 12. Constraints

- **Async-first** — `python-telegram-bot` v22+ uses `async/await` throughout
- **Push to API** — Bot does NOT write to DB directly; it pushes via `POST /api/v1/message/`
- **Reuse Web conventions** — Same Poetry version, Ruff rules, Python ≥3.12, `python-decouple`
- **Admin auth** — Static list of Telegram IDs (`ADMIN_TELEGRAM_IDS`)
- **No blocking I/O** in event loop — use `asyncio` for HTTP calls, file reads, sticker conversion
- **Sticker conversion on bot** — Not on the Pi (per Obsidian §5.7)
- **Webhook primary** — Polling only for local dev

---

## Quick Reference: Obsidian Source

All decisions traced back to `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/obisidan/Private/Projekte/Streaming Bot EAST.md`:

| Section | What it covers |
|---------|---------------|
| §2.0 | Docker + K8s deployment, health checks |
| §2.1 | Bot framework choice (python-telegram-bot), Webhook transport |
| §4.1 | API endpoints, validation pipeline, sanitization |
| §5.1 | Bot commands + admin auth |
| §5.3 | Rejection reasons + Telegram replies |
| §5.5 | Check-in flow via Reg-System |
| §5.6 | Supported message types |
| §5.7 | Sticker conversion workflow (TGS/WebM/WebP → GIF) |
| §6.7 | Auto-approve mode |
| §6.8 | Spam filter pipeline |
