#!/usr/bin/env python3
"""merge_config.py: options must land in the right places of the bouncer config."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "crowdsec_cloudflare_bouncer"))

import merge_config as mc  # noqa: E402

# what `bouncer -g <token>` writes (shape from the upstream template)
GENERATED = {
    "cloudflare_config": {
        "accounts": [
            {"id": "acc1", "token": "tok1", "account_name": "owner@example.com",
             "zones": [
                 {"zone_id": "zoneA", "actions": ["captcha"], "default_action": "captcha", "routes_to_protect": [],
                  "turnstile": {"enabled": True, "mode": "managed"}},
                 {"zone_id": "zoneB", "actions": ["captcha"], "default_action": "captcha", "routes_to_protect": []},
             ]},
        ]
    }
}


def opts(**over):
    base = {"lapi_url": "http://424ccef4-crowdsec:8080", "lapi_key": "KEY", "default_action": "ban",
            "captcha_enabled": "false", "captcha_mode": "managed", "update_frequency": "10s",
            "only_local": "true", "zones": "", "log_level": "info"}
    base.update(over)
    return base


class MergeTest(unittest.TestCase):
    def test_lapi_and_defaults(self):
        cfg = mc.build(GENERATED, opts())
        cs = cfg["crowdsec_config"]
        self.assertEqual(cs["lapi_url"], "http://424ccef4-crowdsec:8080")
        self.assertEqual(cs["lapi_key"], "KEY")
        self.assertEqual(cs["only_include_decisions_from"], ["cscli", "crowdsec"])
        self.assertFalse(cfg["prometheus"]["enabled"])
        self.assertEqual(cfg["log_media"], "stdout")
        zones = cfg["cloudflare_config"]["accounts"][0]["zones"]
        self.assertEqual([z["zone_id"] for z in zones], ["zoneA", "zoneB"])
        for z in zones:
            self.assertEqual(z["default_action"], "ban")
            self.assertEqual(z["actions"], ["ban"])
            self.assertFalse(z["turnstile"]["enabled"])
        self.assertEqual(cfg["cloudflare_config"]["accounts"][0]["token"], "tok1")

    def test_captcha(self):
        cfg = mc.build(GENERATED, opts(captcha_enabled="true", default_action="captcha", captcha_mode="invisible"))
        z = cfg["cloudflare_config"]["accounts"][0]["zones"][0]
        self.assertEqual(z["actions"], ["ban", "captcha"])
        self.assertEqual(z["default_action"], "captcha")
        self.assertTrue(z["turnstile"]["enabled"])
        self.assertEqual(z["turnstile"]["mode"], "invisible")

    def test_captcha_action_implies_turnstile(self):
        cfg = mc.build(GENERATED, opts(default_action="captcha"))
        z = cfg["cloudflare_config"]["accounts"][0]["zones"][0]
        self.assertTrue(z["turnstile"]["enabled"])
        self.assertIn("captcha", z["actions"])

    def test_zone_filter(self):
        cfg = mc.build(GENERATED, opts(zones="zoneB"))
        zones = cfg["cloudflare_config"]["accounts"][0]["zones"]
        self.assertEqual([z["zone_id"] for z in zones], ["zoneB"])
        with self.assertRaises(SystemExit):
            mc.build(GENERATED, opts(zones="nope"))

    def test_community_list_allowed_when_asked(self):
        cfg = mc.build(GENERATED, opts(only_local="false"))
        self.assertEqual(cfg["crowdsec_config"]["only_include_decisions_from"], [])

    def test_empty_generation_fails_loudly(self):
        with self.assertRaises(SystemExit):
            mc.build({}, opts())

    def test_summary_names_zones_not_tokens(self):
        cfg = mc.build(GENERATED, opts())
        text = " ".join(mc.summary(cfg))
        self.assertIn("zoneA", text)
        self.assertNotIn("tok1", text)


if __name__ == "__main__":
    unittest.main()
