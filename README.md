# CrowdSec Cloudflare Bouncer – Home Assistant Add-on

Packages the official [crowdsec-cloudflare-worker-bouncer](https://github.com/crowdsecurity/cs-cloudflare-worker-bouncer)
as a Home Assistant add-on. It deploys a Cloudflare Worker in front of your
zones and keeps it in sync with the decisions of your CrowdSec Security Engine,
so attackers are stopped at Cloudflare's edge – before a request reaches your
tunnel or your host.

Why an extra bouncer when the firewall bouncer already runs on the host? With a
Cloudflare tunnel the host never sees the attacker's address, only the tunnel
container. Decisions must be enforced where the address is still known: at
Cloudflare.

## Install

[![Add repository](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fgregorwolf1973%2Fcrowdsec-cloudflare-bouncer-addon)

Settings → Add-ons → Add-on Store → ⋮ → Repositories → add
`https://github.com/gregorwolf1973/crowdsec-cloudflare-bouncer-addon`.

Then read the add-on's **Documentation** tab: you need a Cloudflare API token
with nine specific permissions, a bouncer key from the CrowdSec add-on, and one
manual step at Cloudflare afterwards (setting the worker routes to *Fail open*).

## Files

- `crowdsec_cloudflare_bouncer/` – the add-on (Dockerfile downloads the pinned
  upstream release for the target architecture; `run.sh` discovers your zones
  from the token and merges the add-on options into the bouncer config)
- `tests/` – `python -m unittest discover -s tests`
