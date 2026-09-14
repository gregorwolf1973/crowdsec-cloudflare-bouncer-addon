# Changelog

## 0.1.4

- **Routen stehen nach jedem Start automatisch auf "Fail open".** Der Bouncer loescht seine Routen bei jedem Start und legt sie neu an - Cloudflare-Standard ist "Fail closed". Eine von Hand umgestellte Route war nach jedem Host-Neustart, Update oder Neustart wieder geschlossen; faellt dann der Worker aus oder ist das Tageslimit erreicht, sehen Besucher nur eine Cloudflare-Fehlerseite.
- Das Addon wartet nach jedem Start, bis die Routen des Bouncers existieren, und setzt `request_limit_fail_open` ueber die Zonen-Routen-API (in der API-Doku nicht aufgefuehrt, von Cloudflare aber geliefert und angenommen - derselbe Schalter wie im Dashboard). Das Ergebnis wird zurueckgelesen und im Log gemeldet. Fremde Routen bleiben unangetastet.
- Neue Option `fail_open` (Standard an). Die Log-Erinnerung, die Routen von Hand umzustellen, entfaellt.

## 0.1.3

- **Fix: Nach einem Neustart des Hosts startete das Addon nicht ("Starten der App beim Systemstart fehlgeschlagen") und Cloudflare stand ohne Schutz da.** Beim Hochfahren starten die Addons gleichzeitig; der Name des CrowdSec-Addons (`424ccef4-crowdsec`) war noch nicht aufloesbar. Der Bouncer richtete trotzdem Worker und KV-Speicher ein, scheiterte am ersten Abruf der Entscheidungen, raeumte beim Beenden alles bei Cloudflare wieder ab und beendete sich mit Code 1.
- Das Addon wartet jetzt vor dem Einrichten, bis die CrowdSec-LAPI mit `lapi_key` antwortet (Pruefung alle 5 s, Hinweis im Log alle 30 s). Ein abgelehnter Schluessel bricht sofort mit einer klaren Meldung ab.
- Beendet sich der Bouncer spaeter (etwa bei einem Neustart oder Update des CrowdSec-Addons), startet das Addon ihn neu, sobald die LAPI wieder antwortet - mit wachsendem Abstand bis 5 Minuten. Vorher war das Addon dann aus und der Schutz weg.
- Die Abfrage der Cloudflare-Konten wird bis zu sechsmal wiederholt, falls Netz oder DNS kurz nach dem Hochfahren noch nicht stehen.

## 0.1.2

- **Fix: Zonen hinter einem Cloudflare-Tunnel wurden nicht geschuetzt.** Der Generator des Bouncers (`-g`) ueberspringt jede Zone ohne A- oder AAAA-Eintrag. Bei Tunnel-Domains zeigen alle Namen per CNAME auf den Tunnel, der Start brach dann mit "Keine Zone gefunden" ab. Das Addon fragt die aktiven Zonen jetzt zusaetzlich direkt bei der Cloudflare-API ab und legt fuer jede die Route `*<zone>/*` an, genau wie der Generator. Ist die API nicht erreichbar, bleibt es bei den Zonen des Generators.
- Die erzeugte Konfiguration bleibt die Grundlage: Neue Schluessel der Bouncer-Version 0.0.18 wie `worker`, `decisions_sync_worker`, `daemon` und `log_mode` gingen vorher beim Zusammenfuehren verloren.
- `default_action: none` erzeugte eine ungueltige Konfiguration. Es bedeutet jetzt Beobachten ohne Sperren (`log_only`).
- Die Option `zones` akzeptiert Zonen-IDs und Zonennamen.

## 0.1.1

- Doku und Fehlermeldungen korrigiert: Der Bouncer-Schluessel muss mit `cscli -c /config/.storage/crowdsec/config/config.yaml` erzeugt werden. Ohne `-c` schreibt cscli in eine Standard-Datenbank, die der laufende CrowdSec-Dienst nicht liest; der Bouncer steht dann in der Liste, die LAPI antwortet aber mit "API key not found".
- Aktuelle Home-Assistant-Versionen nennen Addon-Container `app_<slug>` statt `addon_<slug>`; alle Beispiele nutzen jetzt den neuen Namen.
- Der Build ruft das Programm nicht mehr mit dem unbekannten Schalter `-V` auf.

## 0.1.0

- Erstes Release. Bringt den offiziellen crowdsec-cloudflare-worker-bouncer v0.0.18 als Home-Assistant-Addon (aarch64, amd64, armv7).
- Konten und Zonen werden bei jedem Start aus dem Cloudflare-Token ermittelt, die Addon-Optionen (LAPI, Aktion, Captcha, Intervall, Zonenfilter) werden in die Bouncer-Konfiguration gemischt.
- Option `only_local_decisions` (Standard an) haelt die Community-Blockliste aus dem Worker-Speicher heraus, damit der kostenlose Cloudflare-Plan nicht am ersten Tag ausgeschoepft ist.
- Option `remove_infrastructure` baut Worker, Routen und KV-Speicher bei Cloudflare wieder ab.
- Das Log erinnert bei jedem Start daran, die Worker-Routen bei Cloudflare auf "Fail open" zu stellen.
