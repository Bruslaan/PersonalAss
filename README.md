# Persönlicher Cloud-Assistent – Etappen 1–3

Sichtbarer Chromium-Browser auf Railway, mit passwortgeschützter Liveansicht im lokalen Browser. Alle besuchten Webseiten und deren Logins laufen im Container. Browser Use ist für Rechercheaufträge per Text angeschlossen. Sprachsteuerung und Nachrichtenversand folgen später.

**Status:** Etappe 1 läuft auf Railway. Die passwortgeschützte [Liveansicht](https://personalass-production.up.railway.app/) zeigt den echten Chromium-Browser; `/healthz` liefert 200 und ohne Anmeldung ist `/vnc.html` mit 401 gesperrt. Der lokale Smoke-Test für Authentifizierung, Origin-Schutz und VNC-WebSocket besteht. Das Volume ist auf /data aktiv und Browser Use lokal getestet; siehe [Teststatus](TESTSTATUS.md).

## Aufbau

```text
Lokaler Browser → Railway HTTPS → Nginx :PORT (Basic Auth)
                                 ├─ noVNC-Dateien
                                 └─ /websockify → 127.0.0.1:6080
                                                   → x11vnc 127.0.0.1:5900
                                                   → Xvfb :99 + Openbox + Chromium
Chromium-Profil → /data/profile (optional Railway Volume)
```

Ein eigener Debian-Container vermeidet den für diesen Test unnötigen Selenium Grid. Das Desktop-Prinzip entspricht dem [Selenium-Docker-Beispiel](https://github.com/SeleniumHQ/docker-selenium#debugging): Xvfb, x11vnc und noVNC. Pakete kommen aus Debian-Repositories; keine Installationsskripte fremder Anbieter. Der Basis-Tag und Paketversionen sind nicht unveränderlich gepinnt, damit neue Builds Sicherheitsupdates aufnehmen; für spätere reproduzierbare Releases Image-Digest und Paketstand festhalten.

Nur Nginx lauscht öffentlich. VNC, Websockify und der interne Healthserver lauschen ausschließlich auf Loopback. CDP und die Steuerungs-API sind ausschließlich auf Loopback (9222 bzw. 8092) erreichbar. Basic Auth schützt HTML, JavaScript und WebSocket-Upgrade; der WebSocket akzeptiert nur die Origin der aufgerufenen Domain. `/healthz` ist bewusst öffentlich und liefert ausschließlich einen Bereitschaftsstatus.

Die Prozesse laufen als Benutzer `browser`. Der Entrypoint startet als root, bereitet das Profilverzeichnis vor und wechselt sofort den Benutzer. Chromium nutzt für diesen Prototyp `--no-sandbox`, weil Unterstützung seiner Sandbox auf Railway noch ungeprüft ist. Das schwächt die Isolation gegenüber Webseiten: Ein einzelner privater Testcontainer, keine weiteren Dienste oder KI-Schlüssel darin. `--password-store=basic` vermeidet einen nicht eingerichteten Desktop-Schlüsselbund; gespeicherte Browserdaten sind nicht durch einen lokalen Schlüsselbund geschützt. Der Railway-Account und das Volume müssen entsprechend geschützt sein.

## Railway über GitHub einrichten

1. Auf GitHub ein **privates**, leeres Repository erstellen, etwa `personal-cloud-browser`. Alle Dateien dieses Ordners einschließlich `app/`, `scripts/`, `tests/`, `Dockerfile` und `railway.toml` hochladen. `.env` und Browserprofile niemals hochladen. Alternativ Git verwenden:

   ```sh
   git init
   git add .
   git commit -m "Add protected visible cloud browser prototype"
   git branch -M main
   git remote add origin https://github.com/DEIN-ACCOUNT/personal-cloud-browser.git
   git push -u origin main
   ```

2. In Railway: **New Project → Deploy from GitHub repo**. GitHub verbinden und genau dieses Repository freigeben. Root Directory bleibt das Repository-Hauptverzeichnis. Railway erkennt den [Dockerfile](https://docs.railway.com/builds/dockerfiles); im Build-Log dessen Verwendung kontrollieren. Start Command leer lassen, damit der Docker-Entrypoint verwendet wird.
3. Unter **Variables** die folgenden Werte setzen, dann die ausstehenden Änderungen deployen. Ein erster Start ohne Zugangsdaten schlägt absichtlich fehl.

   | Variable | Wert |
   |---|---|
   | `VIEW_USERNAME` | z. B. `owner` |
   | `VIEW_PASSWORD` | Eigener zufälliger Wert, 20–72 UTF-8-Bytes, keine Zeilenumbrüche |
   | `PORT` | `8080` |

   Passwort z. B. lokal mit `openssl rand -hex 24` erzeugen und in Railway eintragen. Es gehört nicht ins Repository und muss mir nicht mitgeteilt werden. Kein VNC-Standardpasswort vorhanden.

4. Unter **Settings**: genau **eine Replica**, wenn möglich zunächst Ressourcenobergrenzen von **1 vCPU und 2 GB RAM**, eine nahe europäische Region. Das sind Startwerte, keine gemessenen Mindestanforderungen. Serverless/App Sleeping für den Desktop-Test deaktiviert lassen. Im Dashboard Healthcheck `/healthz`, 120 Sekunden Startzeit und maximal drei Neustartversuche bei Fehlern setzen. Das aktuelle Railway-Dashboard weist darauf hin, dass neue Services seit 28.08.2026 nicht mehr für Config as Code aktiviert werden können; `railway.toml` ist daher nur eine Legacy-Referenz und reicht für einen neuen Service nicht aus. Das Standard-Railway-[Healthcheck-Verhalten](https://docs.railway.com/deployments/healthchecks) prüft die Bereitschaft beim Deployment; der eigene Supervisor beendet den Container bei einem ausgefallenen Hauptprozess.
5. Für den reinen Bildschirmtest ist ein Volume optional. Sobald Logins erhalten bleiben sollen: ein kleines [Volume](https://docs.railway.com/volumes) mit dem Service verbinden und auf **`/data`** mounten. Es enthält `/data/profile`. Es wird erst beim Start gemountet; der Entrypoint berücksichtigt root-eigene Mounts. Nicht gleichzeitig zwei Container gegen dasselbe Profil starten. Ohne Volume geht das Profil bei Ersatz des Containers verloren. Persistenz ist erst nach dem Neustarttest in Etappe 2 bestätigt.
6. **Settings → Networking → Public Networking → Generate Domain**, Zielport **8080**. Railway stellt dafür [HTTPS mit Zertifikat](https://docs.railway.com/networking/public-networking) bereit. **Keine TCP-Proxys** für 5900/6080/9222 anlegen. Nur den HTTPS-Link öffnen.
7. Benutzername und Passwort in der Browser-Anmeldung eingeben, dann **Liveansicht öffnen**. Chromium sollte `example.com` sichtbar geöffnet haben. Du brauchst keine lokale Anmeldung bei der besuchten Webseite. In Etappe 1 dient Maus-/Tastaturbedienung ausschließlich zum manuellen Funktionstest; der gewünschte Sprachablauf wird erst später ergänzt.

## Kleinen Test durchführen

1. In einem privaten Browserfenster die Domain öffnen: Ohne Zugangsdaten dürfen weder Startseite noch `/vnc.html` zugänglich sein.
2. Mit korrekten Zugangsdaten verbinden: echter Chromium-Bildschirm, Text und Mauszeiger müssen sichtbar sein. Eine harmlose Webseite im Cloud-Browser öffnen, scrollen und einen Tab wechseln. Verbindungsdauer und Verzögerung beobachten.
3. Die Liveansicht schließen und erneut öffnen: derselbe laufende Desktop sollte wieder erscheinen. Zwei Ansichten teilen denselben Browser, sie sind keine getrennten Sitzungen.
4. Automatisierte Zugangskontrolle und echten VNC-WebSocket testen:

   ```sh
   python3 scripts/smoke.py https://DEINE-DOMAIN.up.railway.app
   ```

   Benutzername und Passwort werden abgefragt; das Passwort wird unsichtbar eingegeben. Der Test erwartet 401 ohne/falsche Anmeldung, 403 für fremde WebSocket-Origin, 200 für Bereitschaft, einen 101-Upgrade und die echte RFB-Begrüßung des VNC-Servers. Er prüft keine Bildqualität und keine Webseiten-Logins.

5. Railway-Metriken und Kosten nach **15–30 Minuten** ansehen. Nach dem Test das aktive Deployment über **Remove Deployment** entfernen und prüfen, dass keine laufende Instanz mehr Ressourcen verbraucht. Eine Domain zu löschen oder das Livefenster zu schließen stoppt den Container nicht. Repository und Volume können für den nächsten Test bleiben; das Volume kostet weiterhin Speichergebühren.

Etappe 2: Mit Volume ein Chromium-Lesezeichen anlegen, Browserfenster geöffnet lassen, Railway-Service neu starten und das Lesezeichen kontrollieren. Danach optional einen unkritischen Login testen, erneut starten und Loginstatus prüfen. Ein erhaltenes Profil garantiert nicht, dass jede Webseite ihre Anmeldung weiter akzeptiert. Logs auf sauberes Herunterfahren und erfolgreiches Wiederöffnen prüfen. Stale Chromium-Singleton-Dateien werden beim Start entfernt; das setzt zwingend eine einzige Profilinstanz voraus.

## Aktuelle Kosten und Begrenzung

Offizielle [Railway-Preise](https://railway.com/pricing), geprüft am **14.10.2026**: Hobby mindestens **5 USD/Monat**, inklusive **5 USD Nutzung**. Zusätzlicher Verbrauch wird berechnet. Für Services aktuell RAM **0,00000386 USD/GB-Sekunde**, CPU **0,00000772 USD/vCPU-Sekunde**, Volume **0,00000006 USD/GB-Sekunde**, ausgehender Traffic **0,05 USD/GB**. Keine Sandbox-/VM-Tarife auf dieser Seite mit Service-Tarifen verwechseln.

Beispiel für 30 Minuten bei konstant **1 GB RAM + 1 voll ausgelasteter vCPU**: ungefähr **0,0208 USD** Compute, plus Traffic/Volume. 30 Tage durchgehend unter denselben Annahmen: ungefähr **30 USD** Compute. Das ist ein Rechenbeispiel, keine Verbrauchsmessung oder Preiszusage; Bildschirmauflösung, Tabs und Webseiten beeinflussen den tatsächlichen Verbrauch. Ohne gestarteten KI-Auftrag fallen keine KI- oder Sprachkosten an; Browser-Use-Recherche wird zusätzlich beim Modellanbieter abgerechnet.

Vor dem Start die Preise im Account erneut prüfen. Unter **Workspace Usage → Set Usage Limits → Compute Usage** eine Warnung und bei Bedarf ein hartes Limit setzen; laut [offizieller Anleitung](https://docs.railway.com/pricing/cost-control) stoppt das harte Limit die Workloads des ganzen Workspace. Wenn dort schon andere Anwendungen laufen, deren Bedarf berücksichtigen. Die [CLI-Referenz](https://docs.railway.com/cli/usage) nennt aktuell mindestens 5 USD für eine Warnung und 10 USD für ein nicht-null hartes Compute-Limit. Das Railway-Agent-Limit begrenzt diesen Browser-Service nicht. Nicht automatisch einen Tarif wechseln. Der Free-Tarif mit aktuell 0,5 GB RAM ist für diesen Desktop kein belastbarer Ausgangspunkt; Hobby ist der vorgesehene kleine Test, sofern bereits vorhanden oder von dir gewählt.

## Optional lokal mit Docker testen

Docker Engine bzw. Docker Desktop ist Voraussetzung. Docker Desktop 4.95.0 wurde hier installiert und die Engine erfolgreich geprüft.

```sh
cp .env.example .env
# .env im Editor öffnen und das eigene zufällige Passwort eintragen
docker compose up --build -d
docker compose logs -f
```

`http://127.0.0.1:8080` öffnen. Nur lokal ist HTTP vorgesehen; in Railway immer HTTPS. Dann `python3 scripts/smoke.py http://127.0.0.1:8080` ausführen. Neustarttest mit `docker compose restart`; beenden mit `docker compose down`. Das benannte Volume bleibt bestehen; `down -v` löscht es einschließlich Profil und Logins.

## Fehler eingrenzen

| Symptom | Nächster Check |
|---|---|
| Start schlägt sofort fehl | Variablen vorhanden? Passwort 20–72 Bytes? Build-Log und Runtime-Log lesen. |
| Railway 502 / Healthcheck fehlgeschlagen | Zielport und `PORT` beide 8080? Prozesse gestartet? `xdotool` erkennt sichtbares Chromium? OOM-Meldung in Metriken/Logs? |
| noVNC lädt, Verbindung fehlt | Domain ohne Proxy öffnen, HTTPS verwenden, Browser-Konsole auf WebSocket-Status prüfen; Origin/Host müssen übereinstimmen. |
| Chromium beendet sich | Supervisor beendet Container und Railway versucht Neustart. OOM und RAM-Verbrauch prüfen, Tabs reduzieren. |
| Nach Restart Login verloren | Volume wirklich `/data`? Profil vorhanden? Webseite hat Sitzung widerrufen? |
| Livebild kurz unterbrochen | noVNC erneut verbinden. Redeploys mit Volume können kurze Downtime haben. |

## Browser Use und API-Schlüssel

1. Einen OpenAI-Projektschlüssel in deinem [API-Konto](https://platform.openai.com/api-keys) erstellen. Ein ChatGPT-Abonnement ersetzt die API-Abrechnung nicht.
2. In Railway das Projekt → **PersonalAss → Variables → New Variable** öffnen. Name: **`OPENAI_API_KEY`**, Wert: dein Schlüssel. **Add** und **Deploy**. Der Schlüssel gehört in diese Servicevariable, nicht in GitHub oder den Chat.
3. Auf der Hauptseite das Modell im Dropdown auswählen: **GPT-6.1 Sol** oder **GPT-5.6 Terra**. Die Wahl gilt für den nächsten Auftrag und erfordert kein neues Deployment. Optional setzt `OPENAI_MODEL` die Vorauswahl; ohne diese Variable ist `gpt-6.1-sol` vorausgewählt. Beide nutzen niedrige Reasoning-Einstellung. Die [offizielle Modellseite](https://developers.openai.com/api/docs/models/gpt-6.1-sol) nennt am 14.10.2026 für normalen Kontext 2 USD pro Million Eingabetokens und 10 USD pro Million Ausgabetokens. Bei langen Prompts gelten Zuschläge; vor Aufträgen Preise und API-Budget prüfen. Keine KI-Anfrage wird beim Service-Start automatisch ausgeführt. Ob dein API-Projekt Zugriff auf das ausgewählte Modell hat, zeigt sich erst beim Auftrag. Browser Use sendet strukturierte JSON-Ausgaben über Chat Completions; Browseraktionen werden anschließend lokal ausgeführt, ohne API-Tool-Calling.
4. Die [Startseite](https://personalass-production.up.railway.app/) öffnen und anmelden. Sie zeigt an, ob der Schlüssel hinterlegt und Chromium verbunden ist. **Liveansicht öffnen** startet einen zweiten Tab mit demselben Cloud-Browser.
5. Erster kleiner Auftrag: „Öffne example.com und fasse den Seiteninhalt in einem Satz zusammen.“ Danach Kleinanzeigen-Recherche versuchen. **Stopp** beendet den Agent-Prozess; Chromium und seine Tabs bleiben geöffnet.

Browser Use ist auf Version 0.13.11 festgelegt. Es verbindet sich über `http://127.0.0.1:9222` mit dem sichtbaren Chromium, entsprechend der [CDP-Dokumentation](https://docs.browser-use.com/open-source/customize/browser/remote). Kein Browser-Use-Cloud-Schlüssel erforderlich. Die Steuerungs-API lauscht intern auf 8092 und wird über den bestehenden Passwortschutz unter `/api/` bereitgestellt. POST-Anfragen prüfen Origin und einen eigenen Request-Header. Der Modellschlüssel wird ausschließlich an den Agent-Prozess vererbt; Chromium, noVNC und Nginx erhalten ihn nicht. Telemetrie ist deaktiviert.

Ein Auftrag ist auf 8 Schritte, 3 Aktionen pro Schritt und 4 Minuten begrenzt. Diese Grenzen begrenzen Laufzeit, garantieren aber keinen festen API-Preis. Seiteninhalte und Screenshots werden beim Auftrag an OpenAI übermittelt. Ergebnisse liegen temporär im Container; das Browserprofil dauerhaft unter `/data/profile`. Der Agent bekommt eine Recherche-Anweisung ohne Nachrichtenversand/Käufe; das ist eine Modellanweisung, keine technisch erzwungene Schreibsperre. Bestätigungsabläufe werden vor späteren Schreibfunktionen ergänzt. Jeder neue Auftrag startet einen eigenen Agenten im bestehenden Browser; vollständiges Fortsetzen und Gesprächsgedächtnis folgen später.

Für einen Test der Browser-Use-Verbindung ohne Modellaufruf kann im Container `/opt/agent-venv/bin/python /app/scripts/probe_browser.py` ausgeführt werden. `write` setzt einen harmlosen Profil-Testwert auf example.com; `read` prüft ihn nach einem Neustart. Der vollständige LLM-Recherchetest ist erst mit einem gültigen API-Schlüssel möglich.
