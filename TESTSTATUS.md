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

## Erweiterung: Volume und Browser Use

- Railway-Volume `personalass-volume` am Service PersonalAss auf `/data` aktiv. Kapazität 5 GB, EU West; berechnet wird die gespeicherte Datenmenge.
- Browser Use 0.13.11 im Linux-Container installiert. Verbindungsprobe verbindet sich ohne Modellaufruf mit dem bereits sichtbaren Chromium auf Loopback-CDP 9222.
- Lokaler Profiltest erfolgreich: localStorage-Testwert auf example.com mit Browser Use gesetzt, Container mit benanntem Volume neu gestartet, Wert erfolgreich gelesen.
- Erweiterter Smoke-Test besteht: Authentifizierung inklusive `/api/status`, WebSocket-Origin-Schutz, Healthcheck, echte VNC-Verbindung; öffentliche CDP-Routen bleiben 404.
- Neun Unittests bestanden: CSRF-Schutz, ungültige Eingaben, fehlender Schlüssel, Doppelauftrag, tatsächliches Beenden eines Worker-Prozesses, Portprüfung und Ausschluss des API-Schlüssels aus Desktop-Prozessen.
- `OPENAI_API_KEY` ist noch nicht hinterlegt. Daher kein kostenpflichtiger LLM-Recherchetest durchgeführt. Keine Aussage über Qualität der Kleinanzeigen-Recherche oder API-Kontozugriff.
- Die Browser-Use-Erweiterung wird nach dem Push auf Railway deployt. Der Cloud-Neustarttest des Profils und die vollständige KI-Recherche bleiben getrennt von den lokalen Nachweisen.

## Erweiterung: fortlaufende Unterhaltung

- Persistenter Worker und Browser-Use-Agent mit Folgeaufträgen über `add_new_task`; Schrittgrenze wird für jeden Folgeauftrag weitergezählt.
- Verlauf auf `/data/assistant/conversation.json`; Wiederherstellung nach Neustart, Modellwechsel und Stopp sowie „Neue Unterhaltung“ implementiert.
- Lokale Tests mit simuliertem Modell prüfen Agent-/Worker-Wiederverwendung, Kontextübergabe, Modellwechsel, Wiederherstellung von Kriterien/Angebots-URL/Zwischenschritt, Stopp und CSRF-Schutz. Container-Build erfolgreich.
- Keine kostenpflichtigen Modellaufrufe und keine automatisierte Browserprüfung dieser Erweiterung. Nutzer übernimmt den vollständigen Recherche- und Bezugstest nach dem Push.

## Erweiterung: Sprachaufträge und Stopp

- Browserseitige deutsche Spracherkennung mit sichtbarem Mikrofonstatus, vorläufigem Transkript und automatischem Senden nach kurzer Pause.
- Stopp-Erkennung während laufender Aufträge; neue Anweisungen stoppen zuerst den alten Auftrag. Reihenfolge von Start/Stopp wird auch bei einem verzögerten Start eingehalten.
- Elf lokale JavaScript-Tests mit simulierter Spracherkennung bestanden: vorläufig/final, Duplikate, mehrteilige Aufträge, Stopp, Mikrofon aus, Wiederverbindung, verweigerte Berechtigung, fehlende Unterstützung, Start/Stopp-Rennen und Fehler.
- Tatsächliches Mikrofon, Spracherkennungsdienst, Safari/Chrome und Cloud-Reaktion nicht automatisch geprüft; Nutzer übernimmt diese Tests nach Deployment. Keine kostenpflichtige Sprach-/Modellanfrage für diese Prüfung.

- Docker-Build und lokaler Smoke-Test erfolgreich: Sprachmodule ohne Anmeldung 401, nach Anmeldung mit JavaScript-MIME-Typ 200; Hauptseite DENY und noVNC SAMEORIGIN; Origin-Schutz, Healthcheck und echter VNC-WebSocket bestehen. Testcontainer anschließend gestoppt.
