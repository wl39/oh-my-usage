"""Explicit startup only: open OpenUsage and tolerate its short API startup delay."""

import http.client
import os
import subprocess
import time
from pathlib import Path

from . import cache, config, source


def start():
    if config.source() == "direct":
        return cache.refresh(force=True)
    app_dir = os.environ.get("OH_MY_USAGE_APP_DIR")
    directories = [Path(app_dir).expanduser()] if app_dir else [
        Path("/Applications"), Path.home() / "Applications"]
    app = next((p / "OpenUsage.app" for p in directories if (p / "OpenUsage.app").is_dir()), None)
    if app is None:
        raise ValueError("OpenUsage was not found. Run ./install.sh from your clone first.")
    subprocess.run(["/usr/bin/open", "-g", str(app)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=10)

    def ready():
        for attempt in range(5):
            try:
                return source.fetch()
            except (OSError, ValueError, http.client.HTTPException):
                if attempt == 4:
                    raise
                time.sleep(0.2)

    return cache.refresh(force=True, fetch=ready)
