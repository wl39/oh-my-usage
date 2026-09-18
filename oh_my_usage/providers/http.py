"""Bounded requests with fixed destinations and redacted errors. No redirects."""

import email.utils
import http.client
import json
import ssl
import time
from urllib.parse import urlsplit

from .common import ProviderError

MAX_BYTES = 4 * 1024 * 1024


class Client:
    def __init__(self, timeout=8, budget=24):
        self.timeout = timeout
        self.deadline = time.monotonic() + budget

    def request(self, url, *, method="GET", headers=None, body=None, raw=False):
        target = urlsplit(url)
        if target.scheme not in ("https", "http") or not target.hostname or target.username or target.password:
            raise ProviderError("invalid_endpoint")
        local = target.hostname == "127.0.0.1"
        if target.scheme != "https" and not local:
            raise ProviderError("https_required")
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ProviderError("timeout")
        timeout = min(self.timeout, remaining)
        options = {"port": target.port, "timeout": timeout}
        if target.scheme == "https":
            options["context"] = ssl._create_unverified_context() if local else ssl.create_default_context()
            connection = http.client.HTTPSConnection(target.hostname, **options)
        else:
            connection = http.client.HTTPConnection(target.hostname, **options)
        outgoing = {"Accept": "application/json", "User-Agent": "oh-my-usage/0.7", **(headers or {})}
        if isinstance(body, (dict, list)):
            outgoing.setdefault("Content-Type", "application/json")
            body = json.dumps(body).encode()
        try:
            connection.request(method, target.path + ("?" + target.query if target.query else ""), body, outgoing)
            response = connection.getresponse()
            data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ProviderError("response_too_large")
            if not 200 <= response.status < 300:
                retry = response.getheader("Retry-After", "")
                try:
                    retry = float(retry)
                except ValueError:
                    try:
                        retry = email.utils.parsedate_to_datetime(retry).timestamp() - time.time()
                    except (ValueError, TypeError):
                        retry = 0
                code = {401: "authentication_required", 403: "access_denied", 429: "rate_limited"}.get(
                    response.status, "http_" + str(response.status))
                raise ProviderError(code, max(0, min(86400, retry)))
            if raw:
                return data
            try:
                return json.loads(data)
            except (ValueError, UnicodeError):
                raise ProviderError("invalid_response") from None
        except (TimeoutError, ConnectionError, OSError, http.client.HTTPException) as error:
            raise ProviderError("timeout" if isinstance(error, TimeoutError) else "connection_failed") from None
        finally:
            connection.close()

    def optional(self, url, **kwargs):
        try:
            return self.request(url, **kwargs)
        except ProviderError as error:
            if error.code == "rate_limited":
                raise
            return None
