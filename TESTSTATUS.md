# Teststatus – 14.10.2026

## Lokal geprüft

- Vier Python-Unittests bestanden: ungültige Zugangsdaten abweisen, ungültige/reservierte Ports abweisen, Zugangsdaten aus der Umgebung eines tatsächlich gestarteten Kindprozesses entfernen und ihn beenden, ausgefallene Prozesse als ungesund erkennen.
- Shell-Syntax von `app/entrypoint.sh` mit `sh -n` geprüft.
- Python-Dateien auf Syntax geprüft; Railway-TOML lokal geparst. Compose-YAML manuell geprüft; kein YAML-Parser verfügbar.
- Offizielle Railway-Dokumentation zu Dockerfiles, HTTPS, Healthchecks, Volumes, Konfiguration und Kosten sowie Browser-Use-Parameter und Selenium-Desktop-Beispiel gelesen. Quellen stehen in der README.

Die Tests liefen mit dem von Codex bereitgestellten Python unter `/Users/bruslan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`. Das macOS-Systemkommando `/usr/bin/python3` scheitert hier an einer noch nicht angenommenen Xcode-Lizenz. Die Lizenz wurde nicht verändert. Für eigene lokale Tests einen funktionierenden Python-Interpreter verwenden.

## Noch nicht geprüft

Docker und Railway-CLI sind auf diesem Rechner nicht vorhanden. Es wurde **kein Container gebaut oder gestartet**, kein Repository auf GitHub erstellt und kein Railway-Deployment angelegt. Nginx-Syntax, Debian-Paketinstallation, Chromium-Start und noVNC-Version wurden deshalb nicht im Linux-Container ausgeführt. Der bereitgestellte Netzwerk-Smoke-Test wurde noch nicht gegen einen laufenden Service ausgeführt.

## Abnahme im tatsächlichen Deployment

| Prüfung | Erwartung | Status |
|---|---|---|
| Docker-Build | Alle Pakete installierbar, Entrypoint ausführbar | Offen |
| Start und Healthcheck | Chromium-Fenster sichtbar, `/healthz` → 200 | Offen |
| Authentifizierung | Ohne/falsches Passwort 401 auf UI und WebSocket | Offen |
| WebSocket-Origin | Fremde Origin mit korrekter Anmeldung → 403 | Offen |
| VNC-Verbindung | Smoke-Test: 101-Upgrade und RFB-Begrüßung | Offen |
| Livebild | Chromium klar sichtbar; Scroll/Tabwechsel sichtbar | Offen |
| Wiederverbinden | Derselbe laufende Desktop | Offen |
| SIGTERM/Restart | Profil sauber schließen, Desktop erneut starten | Offen |
| Persistenz, Etappe 2 | Mit `/data`-Volume Lesezeichen nach Restart erhalten | Offen |
| Fehlerbehandlung | Prozessausfall beendet Container; Neustart begrenzt | Offen |
| Ressourcenkosten | RAM/CPU/Traffic nach 15–30 Minuten messen | Offen |

Die README beschreibt das Vorgehen und Fehlersuche. Ein erfolgreicher Healthcheck bestätigt eine sichtbare Chromium-Instanz und erreichbare interne Ports, aber weder Bildqualität noch Loginfähigkeit bei Kleinanzeigen.
