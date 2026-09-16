"""Read-only checks that do not expose preference contents or provider credentials."""

import http.client
import os
import plistlib
from pathlib import Path

from . import __version__, settings, source
from .metrics import clean


def doctor():
    print("oh-my-usage: " + __version__)
    for app in (Path("/Applications/OpenUsage.app"), Path.home() / "Applications/OpenUsage.app"):
        try:
            with (app / "Contents/Info.plist").open("rb") as stream:
                info = plistlib.load(stream)
            bundle = info.get("CFBundleIdentifier", "unknown")
            print("Installed OpenUsage: " + clean(info.get("CFBundleShortVersionString", "unknown"))
                  + " (" + clean(bundle) + ")")
            if bundle != settings.DOMAIN:
                print("Compatibility: this reader supports native com.robinebers.openusage; "
                      "older Tauri builds are not supported.")
            break
        except (OSError, ValueError, plistlib.InvalidFileException):
            continue
    print("Preference file: " + clean(settings.preferences_path(), 500))
    print("Preference lookup: " + ("custom file" if os.environ.get("OH_MY_USAGE_PREFERENCES")
                                    else "macOS preferences service, then file fallback"))
    ok = True
    try:
        prefs = settings.load()
        print(f"Settings: OK; enabled providers: {len(prefs.enabled)}; stars: {len(prefs.pins)}")
        if prefs.pins_from_defaults:
            print("Stars: OpenUsage defaults (no saved overrides; this is normal).")
        if not prefs.pins:
            print("No stars selected. Select a metric star in OpenUsage Customize to display it.")
    except settings.SettingsError as error:
        print("Settings: ERROR; " + str(error))
        ok = False
    # Probe independently: an unavailable settings file need not mean the API is down.
    try:
        data = source.fetch()
        print(f"Local API: OK; snapshots: {len(data)}")
    except (OSError, ValueError, http.client.HTTPException):
        print("Local API: unavailable or unsupported. Open OpenUsage in this account and retry.")
        ok = False
    return 0 if ok else 1
