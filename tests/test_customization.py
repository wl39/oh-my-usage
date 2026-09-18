import contextlib
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from oh_my_usage import cache, config, customize, preview, settings
from oh_my_usage.__main__ import main
from oh_my_usage.terminal import Console
from test_oh_my_usage import NOW, ROOT, prefs, usage, write_prefs


class CustomizationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.env = patch.dict(os.environ, {"OH_MY_USAGE_CONFIG_DIR": str(self.root / "config"),
            "OH_MY_USAGE_CACHE_DIR": str(self.root / "cache"),
            "OH_MY_USAGE_PREFERENCES": str(self.root / "prefs.plist"), "OH_MY_USAGE_INLINE_WIDTH": ""})
        self.env.start()
        self.addCleanup(self.env.stop)
        config.save("style", "icons")
        config.save("mode", "left")

    def render(self, data=None, preferences=None):
        return customize.render_inline(data or usage(), config.apply(preferences or prefs()), NOW)

    def test_individual_metric_switches_and_all_hidden(self):
        customize.save("metric", "codex.weekly", "off")
        self.assertEqual(self.render(), "◇ 58% (left)")
        customize.save("metric", "codex.session", "off")
        self.assertEqual(self.render(), "")
        customize.save("metric", "codex.weekly", "auto")
        self.assertEqual(self.render(), "◇ 90% (left)")
        customize.save("provider", "codex", "off")
        self.assertEqual(self.render(), "")
        # An enabled upstream provider without data must not leave an error hint
        # behind after all actual readings have been deliberately hidden.
        self.assertEqual(self.render(preferences=replace(prefs(), enabled=("codex", "other"),
                         pins=(*prefs().pins, "other.session"))), "")
        customize.save("provider", "codex", "on")
        self.assertEqual(self.render(), "◇ 90% (left)")

    def test_enable_unstarred_metrics_and_more_than_two_explicit_choices(self):
        data = usage()
        data[0]["lines"].append({"type": "progress", "label": "Monthly", "used": 20, "limit": 100,
                                 "format": {"kind": "percent"}})
        customize.save("metric", "codex.monthly", "on")
        self.assertEqual(self.render(data), "◇ W:90%/S:58%/Monthly:80% (left)")
        p = replace(prefs(), enabled=(), pins=())
        self.assertEqual(self.render(data, p), "")
        customize.save("provider", "codex", "on")
        self.assertEqual(self.render(data, p), "◇ 80% (left)")

    def test_custom_icons_casing_none_details_and_original_units(self):
        customize.save("icon", "codex", "MyBot")
        config.save("metric-labels", "off")
        config.save("mode-label", "off")
        self.assertEqual(self.render(), "MyBot 90%/58%")
        customize.save("icon", "codex", "none")
        self.assertEqual(self.render(), "90%/58%")
        customize.save("icon", "codex", "auto")
        self.assertEqual(self.render(), "◇ 90%/58%")
        config.save("metric-labels", "on")
        self.assertEqual(self.render(preferences=replace(prefs(), pins=("codex.session",))), "◇ S:58%")

    def test_provider_separator_and_unknown_provider_custom_icon(self):
        data = usage()
        data += [{**data[0], "providerId": "other", "displayName": "Other"}]
        p = replace(prefs(), enabled=("codex", "other"), pins=("codex.session", "other.session"))
        customize.save("icon", "other", "O")
        config.save("separator", "dot")
        self.assertEqual(self.render(data, p), "◇ 58% · O 58% (left)")
        config.save("separator", "space")
        self.assertEqual(self.render(data, p), "◇ 58%  O 58% (left)")

    def test_available_metrics_resolve_aliases_and_preserve_account_ids(self):
        provider = {"providerId": "antigravity:work", "lines": [
            {"type": "progress", "label": label, "used": 10, "limit": 100, "format": {"kind": "percent"}}
            for label in ("Session", "Weekly", "New Metric")]}
        self.assertEqual(customize.available(provider), [("antigravity:work.geminiPro", "Session"),
            ("antigravity:work.geminiWeekly", "Weekly"), ("antigravity:work.newMetric", "New Metric")])

    def test_invalid_settings_are_rejected_and_damaged_files_are_ignored(self):
        for kind, key, value in (("icon", "codex", "x\nBAD"), ("icon", "codex", "\x1b[31m"),
                ("icon", "codex", "x" * 13), ("icon", "../../bad", "X"),
                ("provider", "codex", "yes"), ("metric", "codex", "off")):
            with self.subTest(kind=kind, value=value), self.assertRaises(ValueError):
                customize.save(kind, key, value)
        for name, value in (("gap", "9"), ("indent", "21"), ("width", "0"),
                            ("width", "241"), ("width", "$(id)"), ("mode-label", "maybe")):
            with self.assertRaises(ValueError):
                config.save(name, value)
        path = config.directory() / "icon-map"
        for text in ("bad", "[]", '{"codex": [1]}', '{"codex": "\\u001b"}'):
            path.write_text(text)
            self.assertEqual(customize.mapping("icon"), {})

    def test_cli_persistence_auto_reset_and_permissions(self):
        with patch("oh_my_usage.cache.refresh"), contextlib.redirect_stdout(io.StringIO()):
            for args in (("icon", "codex", "C>"), ("provider", "claude", "off"),
                         ("metric", "codex.weekly", "off"), ("position", "after"),
                         ("gap", "3"), ("indent", "4"), ("width", "24")):
                self.assertEqual(main(["config", *args]), 0)
            result = subprocess.run(["python3", "-c", "from oh_my_usage import customize; "
                "print(customize.mapping('icon')['codex'])"], cwd=ROOT, capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout.strip(), "C>")
            for name in customize.MAPS.values():
                self.assertEqual((config.directory() / name).stat().st_mode & 0o777, 0o600)
            config.save_inline("on")
            main(["config", "reset"])
        self.assertEqual(config.inline(), ("on", "saved"))
        self.assertEqual(config.view_key(), "auto|auto")
        self.assertTrue(all(not customize.mapping(kind) for kind in customize.MAPS))

    def test_fresh_cache_reformats_inline_only_and_matches_shell_view_key(self):
        write_prefs(self.root / "prefs.plist")
        fetch = Mock(return_value=usage())
        original = cache.refresh(fetch=fetch, now=NOW)
        customize.save("metric", "codex.weekly", "off")
        customize.save("icon", "codex", "$(touch X)")
        config.save("mode-label", "off")
        self.assertEqual(cache.refresh(fetch=fetch, now=NOW + 1), original)
        self.assertEqual(fetch.call_count, 1)
        lines = (self.root / "cache/display").read_text().splitlines()
        self.assertEqual(lines[4], "$(touch X) 58%")
        self.assertEqual(lines[0], str(NOW))
        result = subprocess.run(["zsh", "-dfc", 'source "$CONFIG_SCRIPT"; _OH_MY_USAGE_CONFIG=$OH_MY_USAGE_CONFIG_DIR; '
            '_oh_my_usage_view_load; print -r -- "$_OH_MY_USAGE_VIEW_KEY"'], capture_output=True, text=True,
            env=dict(os.environ, CONFIG_SCRIPT=str(ROOT / "zsh/config.zsh")), check=True)
        self.assertEqual(result.stdout.rstrip("\n"), config.view_key())
        self.assertFalse((self.root / "X").exists())
        customize.save("provider", "codex", "off")
        cache.refresh(fetch=fetch, now=NOW + 2)
        self.assertEqual((self.root / "cache/display").read_text().splitlines()[4], "")

    def test_preview_shows_hidden_selection_and_custom_placement_with_limits(self):
        for position in ("left", "after", "above"):
            config.save("position", position)
            config.save("indent", "4")
            config.save("gap", "3")
            config.save("width", "12")
            output = io.StringIO()
            console = Console(output)
            console.width = 80
            preview.show(console)
            rows = [line for line in output.getvalue().splitlines() if line.startswith("  |")]
            self.assertTrue(all(preview.cells(line) <= 80 for line in rows))
            self.assertEqual(len(rows), 2 if position == "above" else 1)
            if position == "after":
                self.assertLess(rows[0].index("~/project"), rows[0].index("✳"))
        customize.save("provider", "codex", "off")
        customize.save("provider", "claude", "off")
        output = io.StringIO()
        preview.show(Console(output))
        self.assertIn("no inline hint", output.getvalue())

    def test_interactive_detail_editors_and_cancel_preserve_changes(self):
        # Provider 2 = Codex in the sample; metric 3 = its unstarred Weekly.
        inputs = ["10", "2", "3", "1", "", "11", "2", "C>",
                  "12", "1", "3", "2", "4", "3", "24", "",
                  "13", "2", "2", "3", "3", "", "0"]
        with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", side_effect=inputs), \
             patch("oh_my_usage.cache.refresh"), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["config"]), 0)
        self.assertEqual(customize.mapping("metric"), {"codex.weekly": "on"})
        self.assertEqual(customize.mapping("icon"), {"codex": "C>"})
        self.assertEqual(config.value("gap"), "3")
        self.assertEqual(config.value("indent"), "4")
        self.assertEqual(config.value("width"), "24")
        self.assertEqual(config.value("mode-label"), "off")
        self.assertEqual(config.value("separator"), "space")
        self.assertIn("C>", output.getvalue())


if __name__ == "__main__":
    unittest.main()
