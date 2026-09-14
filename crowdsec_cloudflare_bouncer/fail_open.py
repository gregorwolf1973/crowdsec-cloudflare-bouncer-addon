#!/usr/bin/env python3
"""Switch the bouncer's Worker routes to "fail open" after every deployment.

Usage: fail_open.py <bouncer.yaml> [timeout_seconds]

Cloudflare creates Worker routes "fail closed": if the Worker errors or a
free-plan quota runs out, every visitor gets a Cloudflare error page instead
of the site. The bouncer deletes and recreates its routes on every start, so
a route switched to "fail open" by hand is closed again after each host
reboot, add-on update or bouncer restart.

The public API documents only `pattern` and `script` for a route, but the
zone route endpoints return and accept `request_limit_fail_open` - the very
setting the dashboard toggles. This script waits for the routes of this
bouncer to appear (the bouncer deploys them asynchronously after its start),
sets the flag and reads it back.
"""
import json
import sys
import time
import urllib.error
import urllib.request

import yaml

CF_API = "https://api.cloudflare.com/client/v4"


def log(msg):
    print(f"[bouncer] {msg}", flush=True)


def _call(method, url, token, body=None, timeout=20):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        try:
            return json.load(e)
        except ValueError:
            return {"success": False, "errors": [{"message": f"HTTP {e.code}"}]}


def _errors(data):
    return "; ".join(str(e.get("message")) for e in (data.get("errors") or [])) or "unbekannter Fehler"


def targets(cfg):
    """[(token, zone_id, set(patterns))] and the Worker script name."""
    ccf = (cfg or {}).get("cloudflare_config") or {}
    script = ((ccf.get("worker") or {}).get("script_name")) or "crowdsec-cloudflare-worker-bouncer"
    out = []
    for acc in ccf.get("accounts") or []:
        token = acc.get("token")
        for z in acc.get("zones") or []:
            if token and z.get("zone_id"):
                out.append((token, str(z["zone_id"]), set(z.get("routes_to_protect") or [])))
    return out, script


def pass_once(items, script, call=_call):
    """One round over all zones. Returns (done, changed, problems)."""
    done, changed, problems = True, [], []
    for token, zone_id, patterns in items:
        data = call("GET", f"{CF_API}/zones/{zone_id}/workers/routes", token)
        if not data.get("success"):
            problems.append(f"Routen der Zone {zone_id} nicht lesbar: {_errors(data)}")
            done = False
            continue
        mine = [r for r in data.get("result") or [] if r.get("script") == script
                and (not patterns or r.get("pattern") in patterns)]
        if patterns and {r.get("pattern") for r in mine} != patterns:
            done = False                    # not deployed yet
        for r in mine:
            if r.get("request_limit_fail_open") is True:
                continue
            body = {"pattern": r["pattern"], "script": script, "request_limit_fail_open": True}
            res = call("PUT", f"{CF_API}/zones/{zone_id}/workers/routes/{r['id']}", token, body)
            if not res.get("success"):
                problems.append(f"Route {r['pattern']}: Fail open nicht setzbar: {_errors(res)}")
                done = False
            elif (res.get("result") or {}).get("request_limit_fail_open") is not True:
                problems.append(f"Route {r['pattern']}: Cloudflare hat Fail open nicht uebernommen")
                done = False
            else:
                changed.append(r["pattern"])
    return done, changed, problems


def run(cfg, timeout=240, interval=5, call=_call, sleep=time.sleep, clock=time.monotonic):
    items, script = targets(cfg)
    if not items:
        log("Fail open: keine Zonen in der Konfiguration - nichts zu tun.")
        return True
    end = clock() + timeout
    last_problems = []
    while True:
        try:
            done, changed, problems = pass_once(items, script, call)
        except (urllib.error.URLError, OSError, ValueError) as e:
            done, changed, problems = False, [], [f"Cloudflare nicht erreichbar: {type(e).__name__}: {e}"]
        for p in changed:
            log(f"Route {p} auf 'Fail open' gestellt.")
        if done and not problems:
            log("Fail open: alle Routen des Bouncers stehen auf 'Fail open'.")
            return True
        if problems and problems != last_problems:
            for p in problems:
                log(f"Fail open: {p}")
            last_problems = problems
        if clock() >= end:
            log("Fail open: Zeitlimit erreicht. Routen bei Cloudflare von Hand pruefen "
                "(Workers & Pages -> Worker -> Domains -> Route bearbeiten -> Oeffnen bei Fehler).")
            return False
        sleep(interval)


def main():
    path = sys.argv[1]
    timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 240
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    sys.exit(0 if run(cfg, timeout=timeout) else 1)


if __name__ == "__main__":
    main()
