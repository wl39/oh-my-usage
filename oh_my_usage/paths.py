"""User-local paths shared by installation, the CLI, and shell integration."""

import os
from pathlib import Path
import sys


def cache_directory(home=None):
    home = Path(home) if home is not None else Path.home()
    default = home / "Library/Caches" if sys.platform == "darwin" else Path(os.environ.get("XDG_CACHE_HOME") or home / ".cache")
    return Path(os.environ.get("OH_MY_USAGE_CACHE_DIR") or default / "oh-my-usage").expanduser()
