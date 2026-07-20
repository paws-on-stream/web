# Paws on Stream — Betriebs-Runbook

## Deployment

1. Image unveränderlich taggen und Registry-Push durchführen.
2. Image-Tags in `deploy/k8s/*.yaml` aktualisieren; kein `latest` in Produktion.
3. Datenbank-Backup erstellen.
4. `migrate-job.yaml` anwenden und erfolgreichen Abschluss prüfen.
5. Web-Deployment und anschließend CronJobs anwenden.
6. `/api/v1/health/`, `/api/v1/readiness/` und `/metrics/` prüfen.
7. Bot- und Display-Token getrennt als Secret setzen.
8. Telegram OIDC bei BotFather konfigurieren, die öffentliche Callback-URL
   `https://<domain>/auth/callback/` freigeben und Client-ID/-Secret als
   `TELEGRAM_OIDC_CLIENT_ID` und `TELEGRAM_OIDC_CLIENT_SECRET` setzen.
9. Die numerische Telegram-ID mindestens eines Administrators einmalig über
   `TELEGRAM_AUTH_BOOTSTRAP_IDS` bereitstellen. Nach dessen erstem Login kann
   die Whitelist unter Django Admin → Telegram access gepflegt werden; danach
   kann die Bootstrap-Variable wieder geleert werden.

## Sync-Betrieb

```bash
python paws_on_stream_web/manage.py sync_reg_status --workers 8
python paws_on_stream_web/manage.py sync_events
```

Überlappende Läufe werden durch Kubernetes und eine DB-Lease verhindert. Ein
fehlgeschlagener Reg-Datensatz wird protokolliert, ohne den Batch abzubrechen.

## Backup und Wiederherstellung

- PostgreSQL vor Migrationen und vor der Convention mit `pg_dump` sichern.
- Das Media-PVC zusammen mit der Datenbank sichern; DB und Medien gehören zum
  selben Wiederherstellungspunkt.
- Restore zuerst in einer separaten Datenbank/PVC testen.

## Rollback

- Vorherigen Image-Tag im Deployment und in CronJobs wiederherstellen.
- Datenmigrationen nur zurückrollen, wenn die jeweilige Migration reversibel ist.
- Bei inkompatibler Schemaänderung Datenbank und Media-PVC gemeinsam aus dem
  letzten konsistenten Backup wiederherstellen.

## Störungen

- `health=503`: Datenbankverbindung und Secret `DATABASE_URL` prüfen.
- Event-Sync rot: Event-URL, DNS/HTTPS und jq-Filter prüfen.
- Reg-Sync mit Fehlern: Upstream-Verfügbarkeit prüfen; Einzelfehler stehen im Log.
- Medien fehlen: PVC-Mount und `/media/media_assets/...` prüfen.
- Display erhält 403: `DISPLAY_API_AUTH_TOKEN` auf Backend und Pi abgleichen.
- Telegram-Login liefert 503: OIDC Client-ID und Client-Secret fehlen.
- Telegram lehnt den Callback ab: exakt registrierte HTTPS-Callback-URL und
  Proxy-Header prüfen.
- Nutzer landet auf `/auth/denied/`: numerische Telegram-ID in der Whitelist
  prüfen; Benutzernamen sind für die Freigabe unerheblich.

## Aufbewahrung

Der tägliche Cleanup-CronJob entfernt standardmäßig Nachrichten nach 30 Tagen
und nicht mehr referenzierte Medien nach sieben Tagen. Ein manueller Lauf ist
ohne `--execute` immer nur eine Vorschau.
