"""Read only OpenUsage's display preferences; never read authentication stores."""

import json
import os
import plistlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

LAYOUT = "openusage.layout.v1"
DOMAIN = "com.robinebers.openusage"
# OpenUsage DefaultLayout / LayoutBootstrap: absent pins use the defaults; [] is intentional.
DEFAULT_PINS = (
    "antigravity.geminiPro", "antigravity.geminiWeekly",
    "claude.session", "claude.weekly", "codex.session", "codex.weekly",
    "cursor.auto", "cursor.api", "copilot.premium",
    "ollama.session", "ollama.weekly", "openrouter.credits", "zai.session", "zai.weekly",
)


class SettingsError(ValueError):
    def __init__(self, summary, detail):
        self.summary = summary
        super().__init__(detail)


def preferences_path():
    return Path(os.environ.get("OH_MY_USAGE_PREFERENCES",
                str(Path.home() / "Library/Preferences" / (DOMAIN + ".plist")))).expanduser()


def read_preferences(path=None):
    # macOS may not have flushed the app's latest preferences to its plist yet.
    # Ask the preferences service first; never print or persist the exported domain.
    if path is None and not os.environ.get("OH_MY_USAGE_PREFERENCES"):
        try:
            result = subprocess.run(["/usr/bin/defaults", "export", DOMAIN, "-"],
                                    capture_output=True, timeout=2)
            if result.returncode == 0:
                return plistlib.loads(result.stdout)
        except (OSError, ValueError, plistlib.InvalidFileException, subprocess.TimeoutExpired):
            pass
    with Path(path or preferences_path()).open("rb") as stream:
        return plistlib.load(stream)


@dataclass(frozen=True)
class Settings:
    pins: tuple
    enabled: tuple
    providers: tuple
    metric_order: dict
    expanded: tuple
    remaining: bool = False
    bars: bool = False
    pins_from_defaults: bool = False

    def ordered_pins(self, provider, limit=2):
        prefix = provider + "."
        pins = [p for p in self.pins if p.startswith(prefix)]
        order = self.metric_order.get(provider, [])
        ordered = [p for p in order if p in pins]
        ordered += [p for p in pins if p not in ordered]
        return sorted(ordered, key=lambda p: p in self.expanded)[:limit]


def strings(value):
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueError("Invalid OpenUsage display settings")
    return tuple(value)


def load(path=None):
    try:
        prefs = read_preferences(path)
        return parse(prefs)
    except FileNotFoundError as error:
        raise SettingsError("settings not found", "OpenUsage preferences were not found for this macOS user. "
                            "Open the native OpenUsage app in the same account, then retry.") from error
    except PermissionError as error:
        raise SettingsError("settings not readable", "Permission denied reading OpenUsage preferences. "
                            "Check the file's ownership/read permissions; do not run oh-my-usage with sudo.") from error
    except KeyError as error:
        raise SettingsError("menu-bar settings not saved", f"Missing preference: {error.args[0]}. "
                            "In OpenUsage Customize, toggle a metric star off/on and the provider on, "
                            "then quit/reopen OpenUsage and run oh-my-usage refresh.") from error
    except (ValueError, TypeError, OSError, plistlib.InvalidFileException) as error:
        raise SettingsError("unsupported settings format", "OpenUsage preferences could not be decoded. "
                            "Run oh-my-usage doctor and check the installed app version and preference format.") from error


def direct(providers):
    """Every successfully discovered service is enabled; prefer its first two live meters."""
    ids = tuple(p["providerId"] for p in providers)
    order = {p["providerId"]: tuple(p["providerId"] + "." + line["id"] for line in p["lines"] if "id" in line)
             for p in providers}
    pins = tuple(pin for values in order.values() for pin in values)
    return Settings(pins, ids, ids, order, ())


def parse(prefs):
    if not isinstance(prefs, dict):
        raise ValueError("Preferences must be a dictionary")

    def decoded(key, default):
        value = prefs.get(key, default)
        return json.loads(value) if isinstance(value, (bytes, str)) else value

    # The app can display default stars without ever writing menuBarPins to disk.
    # Only absence uses defaults; an explicit empty or malformed value must not.
    pins_key = LAYOUT + ".menuBarPins"
    pins = strings(prefs.get(pins_key, list(DEFAULT_PINS)))
    enabled = strings(prefs["openusage.enabledProviders.v1"])
    providers = strings(decoded(LAYOUT + ".providerOrder", []))
    metric_order = decoded(LAYOUT + ".metricOrderByProvider", {})
    if not isinstance(metric_order, dict):
        raise ValueError("Invalid OpenUsage metric order")
    metric_order = {k: strings(v) for k, v in metric_order.items()}
    return Settings(pins, enabled, providers, metric_order,
                    strings(prefs.get(LAYOUT + ".expandedMetrics", [])),
                    prefs.get("meterStyle", "used") == "remaining",
                    prefs.get(LAYOUT + ".menuBarStyle") == "bars", pins_key not in prefs)
