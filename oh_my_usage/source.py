"""The UI API is needed here: the limits API omits menu-bar spend metrics."""

import http.client
import json

MAX_BYTES = 2 * 1024 * 1024


def validate(payload):
    if not isinstance(payload, list):
        raise ValueError("Unsupported OpenUsage response")
    result = []
    for provider in payload:
        if not isinstance(provider, dict):
            raise ValueError("Invalid provider")
        if not all(isinstance(provider.get(k), str)
                   for k in ("providerId", "displayName", "fetchedAt")):
            raise ValueError("Invalid provider metadata")
        lines = provider.get("lines")
        if not isinstance(lines, list) or not all(isinstance(v, dict) for v in lines):
            raise ValueError("Invalid metrics")
        # Keep only fields needed for rendering. Never store plans, accounts, or charts.
        fields = ("type", "label", "used", "limit", "format", "value", "text", "id", "resetsAt",
                  "periodDurationMs", "numericValue", "unit")
        result.append({
            "providerId": provider["providerId"],
            "displayName": provider["displayName"],
            "fetchedAt": provider["fetchedAt"],
            "lines": [{k: line[k] for k in fields if k in line} for line in lines
                      if line.get("type") in ("progress", "text", "badge")],
            **({"status": provider["status"]} if isinstance(provider.get("status"), str) else {}),
        })
    return result


def fetch():
    # A fixed loopback endpoint: no proxy inheritance, redirects, or remote requests.
    connection = http.client.HTTPConnection("127.0.0.1", 6736, timeout=1.5)
    try:
        connection.request("GET", "/v1/usage")
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError("OpenUsage API unavailable")
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError("OpenUsage response too large")
        return validate(json.loads(body))
    finally:
        connection.close()
