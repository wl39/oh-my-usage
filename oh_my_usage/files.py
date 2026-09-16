"""Private, atomic replacement of small text files."""

import os
import tempfile


def atomic_write(path, text):
    fd, name = tempfile.mkstemp(prefix=".oh-my-usage-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
