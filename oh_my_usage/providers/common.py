"""Small, explicit contracts shared by the independent usage adapters."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import math
import re


class ProviderError(Exception):
    def __init__(self, code, retry_after=0):
        # Do not pass upstream response text or exception messages to this class.
        self.code = code
        self.retry_after = retry_after
        super().__init__(code)


@dataclass(repr=False)
class Credential:
    source: str
    token: str = field(default="", repr=False)
    data: dict = field(default_factory=dict, repr=False)
    binding: str = ""

    def __repr__(self):
        return "Credential(source=" + repr(self.source) + ", redacted=True)"

    @property
    def fingerprint(self):
        # Access-token rotation is allowed to invalidate a cache; cross-account reuse is not.
        return hashlib.sha256((self.source + "\0" + (self.binding or self.token)).encode()).hexdigest()


@dataclass
class Detection:
    installed: bool = False
    credential: object = field(default=None, repr=False)
    status: str = "not_installed"

    def public(self):
        return {"installed": self.installed, "status": self.status,
                "credentialSource": self.credential.source if self.credential else None}


def number(value):
    if isinstance(value, bool):
        return None
    try:
        result = float(value) if isinstance(value, (str, float, int)) else None
    except ValueError:
        return None
    return result if result is not None and math.isfinite(result) else None


def obj(value):
    return value if isinstance(value, dict) else {}


def text(value):
    return value.strip() if isinstance(value, str) else ""


def iso(value):
    try:
        if number(value) is not None:
            epoch = number(value)
            instant = datetime.fromtimestamp(epoch / 1000 if epoch > 100_000_000_000 else epoch, timezone.utc)
        elif isinstance(value, str):
            instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if instant.tzinfo is None:
                # Date-only billing resets are UTC; ambiguous local timestamps are omitted.
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                    instant = instant.replace(tzinfo=timezone.utc)
                else:
                    return None
        else:
            return None
        return instant.astimezone(timezone.utc).isoformat()
    except (ValueError, OSError, OverflowError):
        return None


def progress(id, label, used, limit=100, kind="percent", reset=None, minutes=None):
    used, limit = number(used), number(limit)
    if used is None or limit is None or limit <= 0 or used < 0:
        return None
    result = {"id": id, "type": "progress", "label": label, "used": used,
              "limit": limit, "format": {"kind": kind}}
    if iso(reset):
        result["resetsAt"] = iso(reset)
    if number(minutes) is not None and number(minutes) > 0:
        result["periodDurationMs"] = number(minutes) * 60000
    return result


def amount(id, label, value, kind="dollars"):
    value = number(value)
    if value is None or value < 0:
        return None
    return {"id": id, "type": "text", "label": label,
            "value": ("$" + f"{value:.2f}") if kind == "dollars" else f"{value:g}",
            "numericValue": value, "unit": kind}


def badge(id, label, value):
    return {"id": id, "type": "badge", "label": label, "text": value}


def rows(*items):
    return [item for item in items if item is not None]


def require_lines(lines):
    if not lines:
        raise ProviderError("no_usage_data")
    return lines


def jwt_payload(token):
    import base64
    try:
        encoded = token.split(".")[1]
        return obj(json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))))
    except (ValueError, IndexError, UnicodeError):
        return {}
