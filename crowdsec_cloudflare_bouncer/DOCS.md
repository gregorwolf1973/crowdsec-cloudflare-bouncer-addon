# CrowdSec Cloudflare Bouncer

Enforces CrowdSec decisions at Cloudflare's edge. The add-on runs the official
`crowdsec-cloudflare-worker-bouncer`: it deploys a small Cloudflare Worker in
front of your zones, keeps a KV store in sync with the decisions of your
CrowdSec Security Engine, and the Worker blocks (or challenges) matching
visitors before a request ever reaches your tunnel or your host.

That is the piece a host firewall cannot provide when traffic arrives through a
Cloudflare tunnel: the host only ever sees the tunnel container, never the
attacker. The bouncer does.

## What you need

1. **The CrowdSec add-on** running, with its LAPI reachable from other add-ons
   (default `http://424ccef4-crowdsec:8080`).
2. **A bouncer key** from that engine. Easiest with the SSH add-on
   (protection mode off; use `sudo` if your SSH user is not root):
   ```
   docker exec app_424ccef4_crowdsec cscli -c /config/.storage/crowdsec/config/config.yaml bouncers add cloudflare-bouncer
   ```
   Copy the printed key into `lapi_key`.

   Two details matter here. Recent Home Assistant versions name add-on
   containers `app_<slug>`; older ones used `addon_<slug>`. And the `-c` is
   not optional: without it `cscli` writes to a default database the running
   engine never reads, the bouncer shows up in `cscli bouncers list`, and the
   LAPI still answers every request with "API key not found".
3. **A Cloudflare API token** (user token, not account-scoped) with exactly
   these permissions. [This link](https://dash.cloudflare.com/profile/api-tokens?permissionGroupKeys=%5B%7B%22key%22%3A%22account_settings%22%2C%22type%22%3A%22read%22%7D%2C%7B%22key%22%3A%22challenge_widgets%22%2C%22type%22%3A%22edit%22%7D%2C%7B%22key%22%3A%22user_details%22%2C%22type%22%3A%22read%22%7D%2C%7B%22key%22%3A%22workers_kv_storage%22%2C%22type%22%3A%22edit%22%7D%2C%7B%22key%22%3A%22workers_routes%22%2C%22type%22%3A%22edit%22%7D%2C%7B%22key%22%3A%22workers_scripts%22%2C%22type%22%3A%22edit%22%7D%2C%7B%22key%22%3A%22zone%22%2C%22type%22%3A%22read%22%7D%2C%7B%22key%22%3A%22dns%22%2C%22type%22%3A%22read%22%7D%2C%7B%22key%22%3A%22account_analytics%22%2C%22type%22%3A%22read%22%7D%5D&name=)
   opens the token form with them pre-selected:

   | Scope   | Item               | Permission |
   |---------|--------------------|------------|
   | Account | Account Settings   | Read       |
   | Account | Turnstile          | Edit       |
   | Account | Workers KV Storage | Edit       |
   | Account | Workers Scripts    | Edit       |
   | Account | Account Analytics  | Read       |
   | User    | User Details       | Read       |
   | Zone    | DNS                | Read       |
   | Zone    | Workers Routes     | Edit       |
   | Zone    | Zone               | Read       |

   Put the token into `cloudflare_tokens` (one entry; more than one only if
   you have several Cloudflare accounts).

## Options

| Option | Meaning |
|---|---|
| `cloudflare_tokens` | One API token per Cloudflare account. The add-on discovers the accounts and zones behind them on every start. |
| `lapi_url` / `lapi_key` | Where the CrowdSec Security Engine is and the bouncer key from `cscli bouncers add`. |
| `default_action` | What the Worker does with a listed address: `ban` (block page), `captcha` (Turnstile challenge) or `none`. |
| `captcha_enabled` / `captcha_mode` | Enable Turnstile challenges; `managed` is the usual choice. |
| `update_frequency` | How often decisions are pulled from the engine (`10s`). |
| `only_local_decisions` | On (recommended on the free plan): only decisions from *your* engine and `cscli`, not the community blocklist. The community list has tens of thousands of addresses and would exhaust the free KV write quota on the first sync. |
| `zones` | Optional list of zone IDs. Empty = every zone the token can see. |
| `remove_infrastructure` | Set to `true` once and start the add-on: it removes the Worker, routes and KV namespace from Cloudflare, then stops. Switch it back off afterwards. |

## After the first start: set the routes to Fail Open

Cloudflare creates worker routes in **Fail Closed** mode. If the Worker ever
errors - including when a free-plan quota is exhausted - every visitor gets a
Cloudflare error page instead of your site. There is no API for this setting,
so do it once by hand:

1. Cloudflare dashboard → your zone → **Workers Routes** (or Workers & Pages →
   the `crowdsec-...` worker → Settings → Domains & Routes).
2. Open each route the bouncer created.
3. **Request limit failure mode** → **Fail open**.

The add-on reminds you of this in its log on every start.

## Free plan

Works, with limits: 1,000 KV writes per day and 100,000 Worker requests per
day (1,000 per minute). Keep `only_local_decisions` on, set Fail Open, and
expect the first sync of a large list to be truncated to about a thousand
addresses. A paid Workers plan removes the ceiling.

## How it fits with Simple NAS

Simple NAS ships CrowdSec scenarios for its share site (password guessing,
link scanning, self-inflicted lockouts). Those produce decisions in the same
engine this add-on reads from, so an address that hammers a share link is
blocked at Cloudflare for every service behind that account - including the
share site itself, Home Assistant, Nextcloud and the rest.

## Testing

```
docker exec app_424ccef4_crowdsec cscli -c /config/.storage/crowdsec/config/config.yaml decisions add -i <your public IP> -d 2m
```
Within `update_frequency` the Worker starts answering your requests with the
block page. The same command with `decisions delete -i <ip>` lifts it early.
