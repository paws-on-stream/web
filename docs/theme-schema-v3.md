# Display-Theme-Schema v3

Schema v3 zentralisiert Pygame-Themes ohne die lokale EAST-Darstellung zu
vereinfachen. Pygame bleibt Referenz-Renderer; das Web Display interpretiert
dasselbe Manifest ausschließlich als Monitoring-Vorschau.

## Paket und API

Ein Theme liegt serverseitig in einem abgeschlossenen Ordner:

```text
core/themes/east13/
├── theme.json
├── chat-top.png
├── chat-middle.png
└── chat-bottom.png
```

Das Manifest wird über `GET /api/v1/themes/{theme}/` ausgeliefert. Die Antwort
ergänzt jedes Asset um eine absolute, authentifizierte `url`. Der Client lädt nur
die im Manifest aufgeführten Assets und prüft deren SHA-256 vor der Aktivierung.

## Referenzprofil

`broadcast-1080p50` beschreibt die logische Renderfläche 1920×1080 und die
erwartete Bildwiederholrate von 50 Hz. Der tatsächliche HDMI-Modus wird vom Pi
konfiguriert und kann nicht durch ein Theme umgeschaltet werden.

## EAST-Frame

EAST verwendet `segmented_vertical`:

1. Top und Bottom behalten ihre native Höhe und werden horizontal skaliert.
2. Middle wird horizontal skaliert und vertikal gekachelt.
3. Der Content wird mit dem im Theme definierten Padding eingesetzt.
4. Danach wird die zusammengesetzte Bubble mit `chat.scale` skaliert.

Dies ist bewusst kein Nine-Slice-Verfahren.

## Template

`chat.template.elements` ist eine geordnete Liste. Erlaubt sind ausschließlich:

- `display_name`
- `content`
- `media`
- `sticker_emoji`

Jedes Element referenziert einen Eintrag aus `chat.styles`. Leere Felder werden
nicht gerendert. Freies HTML, Jinja, Python, JSONQ oder andere ausführbare
Ausdrücke sind nicht erlaubt.

Die v2-Kurzform `margin_bottom` bleibt in v3 erhalten. Clients dürfen sie intern
in ein vollständiges Margin-Modell normalisieren.

## Sicherheit

- Theme- und Asset-IDs sind auf kleine ASCII-Slugs begrenzt.
- Asset-Pfade müssen einfache Dateinamen im Theme-Ordner sein.
- Zunächst werden ausschließlich PNG-Theme-Assets akzeptiert.
- Tatsächliches Format, Maße, Alpha und SHA-256 werden geprüft.
- Ein Manifest ist auf 256 KiB, ein Asset auf 5 MiB und ein Theme auf 32 Assets
  begrenzt.
- Ein Template darf höchstens 16 Elemente enthalten.
- Eine unbekannte Schema-Hauptversion wird nicht aktiviert.

Nachrichtenmedien gehören nicht zum Theme-Paket. Sie werden weiterhin über die
separate, ausschließlich WebP-basierte Medienpipeline ausgeliefert.

## Cache-Verhalten des Display-Clients

Der Client soll eine neue Version zunächst vollständig in ein separates
Verzeichnis laden und validieren. Erst danach wird sie atomar aktiviert. Die
Fallback-Reihenfolge lautet:

1. vollständig validierte zentrale Version,
2. zuletzt gültige gecachte Version,
3. mitgeliefertes lokales `east13`,
4. mitgeliefertes `east-default`.

Ein Download- oder Validierungsfehler darf das aktive Theme nicht verändern.

## Dashboard-Verwaltung

Nur Admins können `/core/themes/` öffnen. Die Verwaltung unterstützt:

- Import eines vollständigen ZIP-Pakets,
- mehrere unveränderliche Versionen pro Theme-Slug,
- Aktivierung einer hochgeladenen oder eingebauten Version,
- gemeinsame Aktivierung für Pygame und Web-Vorschau,
- Löschen nicht aktiver hochgeladener Versionen,
- unveränderliche eingebaute Fallback-Themes.

Das ZIP enthält `theme.json` und exakt die dort deklarierten Dateien direkt im
Wurzelverzeichnis. Verzeichnisse, Symlinks, verschlüsselte Einträge, doppelte
Dateinamen und nicht deklarierte Dateien werden abgelehnt. Das Paket ist auf
10 MiB komprimiert und 24 MiB entpackt begrenzt.
