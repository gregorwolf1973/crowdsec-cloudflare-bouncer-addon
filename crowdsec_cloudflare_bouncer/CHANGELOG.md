# Changelog

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
