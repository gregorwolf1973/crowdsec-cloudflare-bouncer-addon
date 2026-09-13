# Changelog

## 0.1.0

- Erstes Release. Bringt den offiziellen crowdsec-cloudflare-worker-bouncer v0.0.18 als Home-Assistant-Addon (aarch64, amd64, armv7).
- Konten und Zonen werden bei jedem Start aus dem Cloudflare-Token ermittelt, die Addon-Optionen (LAPI, Aktion, Captcha, Intervall, Zonenfilter) werden in die Bouncer-Konfiguration gemischt.
- Option `only_local_decisions` (Standard an) haelt die Community-Blockliste aus dem Worker-Speicher heraus, damit der kostenlose Cloudflare-Plan nicht am ersten Tag ausgeschoepft ist.
- Option `remove_infrastructure` baut Worker, Routen und KV-Speicher bei Cloudflare wieder ab.
- Das Log erinnert bei jedem Start daran, die Worker-Routen bei Cloudflare auf "Fail open" zu stellen.
