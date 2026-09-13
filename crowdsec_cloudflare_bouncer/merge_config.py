#!/usr/bin/env python3
"""Merge the Cloudflare config discovered by `bouncer -g` with the add-on options.

Usage: merge_config.py <generated.yaml> <output.yaml>
Options come from environment variables set by run.sh.
"""
import os
import sys

import yaml


def env(name, default=""):
    v = os.environ.get(name, "")
    return v if v not in ("", "null") else default


def truthy(v):
    return str(v).strip().lower() in ("true", "1", "yes", "on")


def build(generated, opts):
    cf = generated.get("cloudflare_config") or {}
    accounts = cf.get("accounts") or []
    wanted = {z.strip() for z in opts["zones"].split(",") if z.strip()}
    captcha = truthy(opts["captcha_enabled"])
    action = opts["default_action"] or "ban"
    actions = ["ban"] + (["captcha"] if captcha else [])
    if action == "captcha" and not captcha:
        captcha = True
        actions.append("captcha")

    kept_accounts = []
    for acc in accounts:
        zones = []
        for z in acc.get("zones") or []:
            zid = str(z.get("zone_id", ""))
            if wanted and zid not in wanted:
                continue
            zones.append({
                "zone_id": zid,
                "actions": actions,
                "default_action": action,
                "routes_to_protect": z.get("routes_to_protect") or [],
                "turnstile": {
                    "enabled": captcha,
                    "rotate_secret_key": True,
                    "rotate_secret_key_every": "168h0m0s",
                    "mode": opts["captcha_mode"] or "managed",
                },
            })
        if zones:
            kept_accounts.append({
                "id": acc.get("id"),
                "token": acc.get("token"),
                "account_name": acc.get("account_name", ""),
                "zones": zones,
            })

    if not kept_accounts:
        raise SystemExit("Keine Zone gefunden, die geschuetzt werden kann. Option 'zones' pruefen "
                         "oder leer lassen, damit alle Zonen des Tokens genommen werden.")

    return {
        "crowdsec_config": {
            "lapi_key": opts["lapi_key"],
            "lapi_url": opts["lapi_url"],
            "update_frequency": opts["update_frequency"] or "10s",
            "include_scenarios_containing": [],
            "exclude_scenarios_containing": [],
            "only_include_decisions_from": ["cscli", "crowdsec"] if truthy(opts["only_local"]) else [],
            "insecure_skip_verify": False,
            "key_path": "", "cert_path": "", "ca_cert_path": "",
        },
        "cloudflare_config": {"accounts": kept_accounts},
        "log_level": opts["log_level"] or "info",
        "log_media": "stdout",
        "log_dir": "/var/log/",
        "ban_template_path": "",
        "prometheus": {"enabled": False, "listen_addr": "127.0.0.1", "listen_port": "2112"},
    }


def summary(cfg):
    lines = []
    for acc in cfg["cloudflare_config"]["accounts"]:
        lines.append(f"Konto {acc.get('account_name') or acc.get('id')}: "
                     + ", ".join(z["zone_id"] for z in acc["zones"]))
    return lines


def main():
    src, dst = sys.argv[1], sys.argv[2]
    with open(src, encoding="utf-8") as f:
        generated = yaml.safe_load(f) or {}
    opts = {
        "lapi_url": env("LAPI_URL", "http://424ccef4-crowdsec:8080"),
        "lapi_key": env("LAPI_KEY"),
        "default_action": env("DEFAULT_ACTION", "ban"),
        "captcha_enabled": env("CAPTCHA_ENABLED", "false"),
        "captcha_mode": env("CAPTCHA_MODE", "managed"),
        "update_frequency": env("UPDATE_FREQUENCY", "10s"),
        "only_local": env("ONLY_LOCAL", "true"),
        "zones": env("ZONES", ""),
        "log_level": env("LOG_LEVEL", "info"),
    }
    cfg = build(generated, opts)
    with open(dst, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)
    for line in summary(cfg):
        print(f"[bouncer] {line}", flush=True)


if __name__ == "__main__":
    main()
