#!/usr/bin/env python3
"""fail_open.py: switch this bouncer's routes to fail open once they exist."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "crowdsec_cloudflare_bouncer"))

import fail_open as fo  # noqa: E402

SCRIPT = "crowdsec-cloudflare-worker-bouncer"
CFG = {"cloudflare_config": {
    "worker": {"script_name": SCRIPT},
    "accounts": [{"id": "acc1", "token": "tok1", "zones": [
        {"zone_id": "zoneA", "routes_to_protect": ["*a.example/*"]},
    ]}],
}}


class FakeCloudflare:
    """Zone route endpoints. `appear_after` GETs until the bouncer's route exists."""

    def __init__(self, appear_after=0, accept_flag=True, put_fails=False):
        self.gets = 0
        self.appear_after = appear_after
        self.accept_flag = accept_flag
        self.put_fails = put_fails
        self.routes = {"r-other": {"id": "r-other", "pattern": "*a.example/other/*", "script": "someone-else",
                                   "request_limit_fail_open": False}}
        self.puts = []

    def __call__(self, method, url, token, body=None, timeout=20):
        assert token == "tok1"
        if method == "GET":
            self.gets += 1
            if self.gets > self.appear_after and "r1" not in self.routes:
                self.routes["r1"] = {"id": "r1", "pattern": "*a.example/*", "script": SCRIPT,
                                     "request_limit_fail_open": False}
            return {"success": True, "result": [dict(r) for r in self.routes.values()]}
        rid = url.rsplit("/", 1)[-1]
        self.puts.append((rid, body))
        if self.put_fails:
            return {"success": False, "errors": [{"message": "Authentication error"}]}
        if self.accept_flag:
            self.routes[rid]["request_limit_fail_open"] = body["request_limit_fail_open"]
        return {"success": True, "result": dict(self.routes[rid])}


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


class FailOpenTest(unittest.TestCase):
    def run_fo(self, cf, timeout=60):
        c = Clock()
        return fo.run(CFG, timeout=timeout, interval=5, call=cf, sleep=c.sleep, clock=c)

    def test_waits_for_the_route_then_opens_only_ours(self):
        cf = FakeCloudflare(appear_after=3)
        self.assertTrue(self.run_fo(cf))
        self.assertEqual([p[0] for p in cf.puts], ["r1"], "fremde Routen bleiben unangetastet")
        self.assertEqual(cf.puts[0][1], {"pattern": "*a.example/*", "script": SCRIPT, "request_limit_fail_open": True})
        self.assertTrue(cf.routes["r1"]["request_limit_fail_open"])
        self.assertFalse(cf.routes["r-other"]["request_limit_fail_open"])

    def test_already_open_needs_no_write(self):
        cf = FakeCloudflare()
        cf.routes["r1"] = {"id": "r1", "pattern": "*a.example/*", "script": SCRIPT, "request_limit_fail_open": True}
        self.assertTrue(self.run_fo(cf))
        self.assertEqual(cf.puts, [])

    def test_gives_up_after_timeout_when_flag_is_ignored_or_refused(self):
        self.assertFalse(self.run_fo(FakeCloudflare(accept_flag=False), timeout=20))
        self.assertFalse(self.run_fo(FakeCloudflare(put_fails=True), timeout=20))
        self.assertFalse(self.run_fo(FakeCloudflare(appear_after=10 ** 6), timeout=20), "Route erscheint nie")

    def test_network_errors_are_retried(self):
        cf = FakeCloudflare()
        calls = {"n": 0}

        def flaky(*a, **k):
            calls["n"] += 1
            if calls["n"] <= 2:
                raise OSError("network is unreachable")
            return cf(*a, **k)
        self.assertTrue(self.run_fo(flaky))

    def test_targets_from_config(self):
        items, script = fo.targets(CFG)
        self.assertEqual(script, SCRIPT)
        self.assertEqual(items, [("tok1", "zoneA", {"*a.example/*"})])
        self.assertTrue(fo.run({}, call=lambda *a, **k: self.fail("kein Aufruf erwartet")))


if __name__ == "__main__":
    unittest.main()
