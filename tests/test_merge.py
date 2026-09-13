#!/usr/bin/env python3
"""merge_config.py: options must land in the right places of the bouncer config."""
import os
import sys
import unittest
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "crowdsec_cloudflare_bouncer"))

import merge_config as mc  # noqa: E402

# Shape of what `bouncer -g <token>` v0.0.18 writes. acc1 has one zone with an
# A record (zoneA) - the generator lists only that one.
GENERATED = {
    "cloudflare_config": {
        "worker": {"script_name": "crowdsec-cloudflare-worker-bouncer", "log_only": False,
                   "kv_namespace_name": "CROWDSECCFBOUNCERNS"},
        "decisions_sync_worker": {"cron": "*/5 * * * *"},
        "accounts": [
            {"id": "acc1", "token": "tok1", "account_name": "owner@example.com", "ban_template": "",
             "zones": [
                 {"zone_id": "zoneA", "actions": ["captcha"], "default_action": "captcha",
                  "routes_to_protect": ["*a.example/*"], "turnstile": {"enabled": True, "mode": "managed"}},
             ]},
        ],
    },
    "crowdsec_config": {"lapi_url": "http://localhost:8080/", "lapi_key": "", "update_frequency": "10s",
                        "only_include_decisions_from": [], "key_path": ""},
    "daemon": True,
    "log_level": "info",
    "log_mode": "stdout",
    "prometheus": {"enabled": True, "listen_addr": "127.0.0.1", "listen_port": "2112"},
}


def api(zones, success=True):
    """Fake Cloudflare /zones endpoint returning [(id, name)]."""
    calls = []

    def fetch(url, token):
        calls.append((url, token))
        if not success:
            return {"success": False, "errors": [{"message": "Invalid access token"}]}
        return {"success": True, "result": [{"id": i, "name": n} for i, n in zones],
                "result_info": {"total_pages": 1}}
    fetch.calls = calls
    return fetch


def offline(url, token):
    raise urllib.error.URLError("no network")


def opts(**over):
    base = {"lapi_url": "http://424ccef4-crowdsec:8080", "lapi_key": "KEY", "default_action": "ban",
            "captcha_enabled": "false", "captcha_mode": "managed", "update_frequency": "10s",
            "only_local": "true", "zones": "", "log_level": "info"}
    base.update(over)
    return base


def zones_of(cfg):
    return {z["zone_id"]: z for z in cfg["cloudflare_config"]["accounts"][0]["zones"]}


class MergeTest(unittest.TestCase):
    def test_lapi_and_defaults(self):
        cfg = mc.build(GENERATED, opts(), fetch=api([("zoneA", "a.example")]))
        cs = cfg["crowdsec_config"]
        self.assertEqual(cs["lapi_url"], "http://424ccef4-crowdsec:8080")
        self.assertEqual(cs["lapi_key"], "KEY")
        self.assertEqual(cs["only_include_decisions_from"], ["cscli", "crowdsec"])
        self.assertFalse(cfg["prometheus"]["enabled"])
        z = zones_of(cfg)["zoneA"]
        self.assertEqual((z["default_action"], z["actions"]), ("ban", ["ban"]))
        self.assertFalse(z["turnstile"]["enabled"])
        self.assertEqual(cfg["cloudflare_config"]["accounts"][0]["token"], "tok1")

    def test_generated_keys_survive(self):
        cfg = mc.build(GENERATED, opts(), fetch=api([("zoneA", "a.example")]))
        self.assertEqual(cfg["cloudflare_config"]["worker"]["script_name"], "crowdsec-cloudflare-worker-bouncer")
        self.assertEqual(cfg["cloudflare_config"]["decisions_sync_worker"]["cron"], "*/5 * * * *")
        self.assertTrue(cfg["daemon"])
        self.assertEqual(cfg["log_mode"], "stdout")
        self.assertNotIn("log_media", cfg)
        self.assertEqual(cfg["cloudflare_config"]["accounts"][0]["ban_template"], "")
        self.assertIsNot(cfg, GENERATED)
        self.assertEqual(GENERATED["crowdsec_config"]["lapi_key"], "")     # input untouched

    def test_tunnel_zone_without_a_record_is_added(self):
        # the real case: generator returned zones: [] for a CNAME-only zone
        gen = {**GENERATED, "cloudflare_config": {**GENERATED["cloudflare_config"], "accounts": [
            {"id": "acc1", "token": "tok1", "account_name": "me", "zones": []}]}}
        fetch = api([("zoneT", "biker633.org")])
        cfg = mc.build(gen, opts(), fetch=fetch)
        z = zones_of(cfg)["zoneT"]
        self.assertEqual(z["routes_to_protect"], ["*biker633.org/*"])
        self.assertIn("account.id=acc1", fetch.calls[0][0])
        self.assertEqual(fetch.calls[0][1], "tok1")
        self.assertEqual(mc.summary(cfg), ["Konto me: biker633.org"])

    def test_generator_routes_win_for_zones_it_found(self):
        cfg = mc.build(GENERATED, opts(), fetch=api([("zoneA", "a.example"), ("zoneT", "t.example")]))
        z = zones_of(cfg)
        self.assertEqual(z["zoneA"]["routes_to_protect"], ["*a.example/*"])
        self.assertEqual(z["zoneT"]["routes_to_protect"], ["*t.example/*"])

    def test_api_unreachable_falls_back_to_generator(self):
        cfg = mc.build(GENERATED, opts(), fetch=offline)
        self.assertEqual(list(zones_of(cfg)), ["zoneA"])
        cfg = mc.build(GENERATED, opts(), fetch=api([], success=False))
        self.assertEqual(list(zones_of(cfg)), ["zoneA"])

    def test_captcha(self):
        cfg = mc.build(GENERATED, opts(captcha_enabled="true", default_action="captcha", captcha_mode="invisible"),
                       fetch=api([("zoneA", "a.example")]))
        z = zones_of(cfg)["zoneA"]
        self.assertEqual(z["actions"], ["ban", "captcha"])
        self.assertEqual(z["default_action"], "captcha")
        self.assertTrue(z["turnstile"]["enabled"])
        self.assertEqual(z["turnstile"]["mode"], "invisible")

    def test_captcha_action_implies_turnstile(self):
        z = zones_of(mc.build(GENERATED, opts(default_action="captcha"), fetch=api([("zoneA", "a.example")])))["zoneA"]
        self.assertTrue(z["turnstile"]["enabled"])
        self.assertIn("captcha", z["actions"])

    def test_action_none_means_log_only(self):
        cfg = mc.build(GENERATED, opts(default_action="none"), fetch=api([("zoneA", "a.example")]))
        z = zones_of(cfg)["zoneA"]
        self.assertIn(z["default_action"], z["actions"])           # bouncer validation
        self.assertTrue(cfg["cloudflare_config"]["worker"]["log_only"])

    def test_zone_filter_by_id_or_name(self):
        both = api([("zoneA", "a.example"), ("zoneT", "t.example")])
        self.assertEqual(list(zones_of(mc.build(GENERATED, opts(zones="zoneT"), fetch=both))), ["zoneT"])
        self.assertEqual(list(zones_of(mc.build(GENERATED, opts(zones="A.example"), fetch=both))), ["zoneA"])
        with self.assertRaises(SystemExit):
            mc.build(GENERATED, opts(zones="nope"), fetch=both)

    def test_empty_list_option_is_not_a_filter(self):
        os.environ["ZONES"] = "[]"
        try:
            self.assertEqual(mc.env("ZONES", ""), "")
        finally:
            del os.environ["ZONES"]

    def test_community_list_allowed_when_asked(self):
        cfg = mc.build(GENERATED, opts(only_local="false"), fetch=api([("zoneA", "a.example")]))
        self.assertEqual(cfg["crowdsec_config"]["only_include_decisions_from"], [])

    def test_empty_generation_fails_loudly(self):
        with self.assertRaises(SystemExit):
            mc.build({}, opts(), fetch=api([]))

    def test_summary_names_zones_not_tokens(self):
        cfg = mc.build(GENERATED, opts(), fetch=api([("zoneA", "a.example")]))
        text = " ".join(mc.summary(cfg))
        self.assertIn("a.example", text)
        self.assertNotIn("tok1", text)

    def test_pagination(self):
        pages = {1: [("z1", "one.example")], 2: [("z2", "two.example")]}

        def fetch(url, token):
            page = int(url.split("page=")[-1])
            return {"success": True, "result": [{"id": i, "name": n} for i, n in pages[page]],
                    "result_info": {"total_pages": 2}}
        self.assertEqual(mc.list_zones("acc1", "tok", fetch), [("z1", "one.example"), ("z2", "two.example")])


if __name__ == "__main__":
    unittest.main()
