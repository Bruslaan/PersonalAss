# Teststatus – 14.10.2026

## Lokal geprüft

- Docker Desktop 4.95.0 installiert; CLI und Linux-Engine 29.8.2 funktionieren.
- Debian-Container für ARM64 erfolgreich gebaut. Chromium und der sichtbare X11-Desktop starten mit 1 vCPU und 2 GB RAM.
- Nginx als Benutzer browser geprüft. Fehler bei temporären Verzeichnissen und stderr-Zugriff korrigiert.
- Smoke-Test erfolgreich: UI-Authentifizierung, fremde WebSocket-Origin abweisen, Healthcheck, echter WebSocket-Upgrade und VNC-RFB-Begrüßung.
- Vier Python-Unittests, Python-/Shell-Syntax und Railway-TOML bestanden. Compose-YAML manuell geprüft.
- Erster lokaler Leerlauf-Messwert: circa 842 MiB RAM; keine Aussage über Lastspitzen. Lokaler Testcontainer danach gestoppt.

## Railway

Das bestehende Projekt precious-cat mit Service PersonalAss ist mit Bruslaan/PersonalAss verbunden. HTTPS-Domain personalass-production.up.railway.app auf Zielport 8080 eingerichtet. PORT=8080, Healthcheck /healthz mit 120 Sekunden und Restart ON_FAILURE mit 3 Versuchen konfiguriert. Vorhandene Limits von 1 vCPU und 3 GB RAM sowie eine Replica in EU West beibehalten. Passwort vom Nutzer korrigiert. Nginx-Fix in Commit 5724ba2 gespeichert.

- Deployment `211a006d-4053-43b5-8581-172aebe4e79b` steht auf Active/Online.
- Öffentlicher HTTPS-Healthcheck `/healthz`: 200 mit Inhalt `ready`.
- Liveansicht `/vnc.html` ohne Zugangsdaten: 401.
- Nach Anmeldung noVNC im lokalen Safari verbunden. Screenshot zeigt Chromium auf dem Cloud-Rechner mit geladener `example.com`-Seite. Keine lokale Anmeldung bei dieser Webseite erforderlich.

## Noch offen

- Langzeittest der Bildqualität, Latenz und Wiederverbindung.
- Vollständiger automatisierter Cloud-Smoke-Test mit den persönlichen Zugangsdaten. Cloud-Anmeldung und Livebild wurden manuell geprüft; der vollständige Smoke-Test lief lokal.
- Profilpersistenz mit Volume und Neustart (Etappe 2).
- Browser Use, Sprache und Kleinanzeigen-Ablauf.

Die lokale Prüfung lief mit dem gebündelten Codex-Python. Das macOS-System-Python ist weiterhin durch die Xcode-Lizenz blockiert; diese wurde nicht geändert.
