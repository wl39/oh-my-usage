"""Independent, read-only usage transports for every supported provider."""

import base64
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import re
import selectors
import sqlite3
import subprocess
import tempfile
import time
from urllib.parse import quote, urlsplit

from . import mappers, native
from .common import ProviderError, amount, jwt_payload, number, obj, require_lines, text
from .http import Client

PROVIDERS = {"antigravity": "Antigravity", "claude": "Claude", "codex": "Codex", "copilot": "GitHub Copilot",
             "cursor": "Cursor", "devin": "Devin", "grok": "Grok", "ollama": "Ollama",
             "opencode": "OpenCode", "openrouter": "OpenRouter", "zai": "Z.ai"}


def codex_rpc(executable):
    process = subprocess.Popen([executable, "app-server", "--listen", "stdio://"], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, cwd=tempfile.gettempdir())
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    pending = bytearray()
    deadline = time.monotonic() + 25

    def send(message):
        process.stdin.write(json.dumps(message).encode() + b"\n")
        process.stdin.flush()

    def receive(id):
        while time.monotonic() < deadline:
            while b"\n" in pending:
                line, _, rest = pending.partition(b"\n")
                pending[:] = rest
                if not line:
                    continue
                message = obj(json.loads(line))
                if message.get("id") == id:
                    if "error" in message:
                        raise ProviderError("app_server_rpc_error")
                    return obj(message.get("result"))
            if not selector.select(max(0, deadline - time.monotonic())):
                break
            chunk = os.read(process.stdout.fileno(), 65536)
            if not chunk:
                raise ProviderError("app_server_closed")
            pending.extend(chunk)
            if len(pending) > 4 * 1024 * 1024:
                raise ProviderError("response_too_large")
        raise ProviderError("timeout")

    try:
        send({"id": 1, "method": "initialize", "params": {"clientInfo": {
            "name": "oh_my_usage", "title": "Oh My Usage", "version": "0.7.0"}}})
        receive(1)
        send({"method": "initialized", "params": {}})
        send({"id": 2, "method": "account/read", "params": {"refreshToken": False}})
        account = receive(2).get("account")
        if not isinstance(account, dict):
            raise ProviderError("authentication_required")
        if account.get("type") == "apiKey":
            raise ProviderError("subscription_required")
        send({"id": 3, "method": "account/rateLimits/read"})
        return receive(3)
    finally:
        selector.close()
        process.stdin.close()
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        process.stdout.close()


def local_opencode(root):
    """Local hosted-model spend only; never read messages from other providers."""
    now = datetime.now().astimezone()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    cutoffs = [today.timestamp() * 1000, (today - timedelta(days=1)).timestamp() * 1000,
               (now - timedelta(days=30)).timestamp() * 1000]
    totals = [0.0, 0.0, 0.0]
    matched = False
    seen = set()
    for path in sorted(Path(root).glob("opencode*.db")):
        connection = sqlite3.connect(path.absolute().as_uri() + "?mode=ro", uri=True, timeout=1)
        deadline = time.monotonic() + 3
        connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        try:
            # Selecting the few needed JSON fields keeps prompt text out of this process.
            cursor = connection.execute("""SELECT id, time_created, json_extract(data, '$.cost')
                FROM message WHERE time_created >= ? AND json_valid(data)
                AND json_extract(data, '$.role') = 'assistant'
                AND json_extract(data, '$.providerID') IN ('opencode', 'opencode-go')""", (cutoffs[2],))
            for id, stamp, cost in cursor:
                cost, stamp = number(cost), number(stamp)
                if id in seen or cost is None or cost < 0 or stamp is None:
                    continue
                seen.add(id)
                matched = True
                totals[2] += cost
                if stamp >= cutoffs[0]:
                    totals[0] += cost
                elif stamp >= cutoffs[1]:
                    totals[1] += cost
        finally:
            connection.close()
    if not matched:
        return []
    return [amount(id, label, value) for id, label, value in
            zip(("today", "yesterday", "last30"), ("Local today", "Local yesterday", "Local last 30 days"), totals)]


def fetch(provider, credential, client=None):
    client = client or Client()
    headers = {"Authorization": "Bearer " + credential.token}
    if provider == "codex":
        result = mappers.codex(codex_rpc(credential.data["executable"]))
    elif provider == "claude":
        result = mappers.claude(client.request("https://api.anthropic.com/api/oauth/usage", headers={
            **headers, "anthropic-beta": "oauth-2025-04-20"}))
    elif provider == "antigravity":
        result, failure = [], None
        for server in credential.data.get("servers", []):
            for port in server["ports"]:
                try:
                    body = client.request(f"https://127.0.0.1:{port}/exa.language_server_pb.LanguageServerService/RetrieveUserQuotaSummary",
                                          method="POST", body={"metadata": {"ideName": "antigravity", "extensionName": "antigravity",
                                                                            "ideVersion": "unknown", "locale": "en"}},
                                          headers={"Connect-Protocol-Version": "1", "x-codeium-csrf-token": server["csrf"]})
                    result = mappers.antigravity(obj(body))
                    if result:
                        break
                except ProviderError as error:
                    failure = error
            if result:
                break
        if credential.token:
            for host in ("daily-cloudcode-pa.googleapis.com", "cloudcode-pa.googleapis.com"):
                try:
                    result = mappers.antigravity(client.request("https://" + host + "/v1internal:retrieveUserQuotaSummary",
                                                               method="POST", body={}, headers=headers))
                    if result:
                        break
                except ProviderError as error:
                    failure = error
                    if error.code == "rate_limited":
                        raise
        if not result and failure:
            raise failure
    elif provider == "copilot":
        headers = {"Authorization": "token " + credential.token, "Editor-Version": "vscode/1.96.2",
                   "Editor-Plugin-Version": "copilot-chat/0.26.7", "User-Agent": "GitHubCopilotChat/0.26.7",
                   "X-Github-Api-Version": "2025-04-01"}
        data = client.request("https://api.github.com/copilot_internal/user", headers=headers)
        result = mappers.copilot(data)
        if not result and data.get("token_based_billing") is True:
            orgs = client.optional("https://api.github.com/user/orgs?per_page=100", headers=headers)
            for org in orgs[:10] if isinstance(orgs, list) else []:
                slug = text(obj(org).get("login"))
                if not re.fullmatch(r"[A-Za-z0-9-]{1,100}", slug):
                    continue
                data = client.optional("https://api.github.com/orgs/" + slug + "/settings/billing/usage/summary",
                                       headers={**headers, "X-Github-Api-Version": "2022-11-28"})
                result = mappers.copilot_org(obj(data))
                if result:
                    break  # Never sum overlapping organizations into a personal meter.
    elif provider == "cursor":
        base = "https://api2.cursor.sh/aiserver.v1.DashboardService/"
        connect = {**headers, "Connect-Protocol-Version": "1"}
        failure = None
        try:
            result = mappers.cursor(client.request(base + "GetCurrentPeriodUsage", method="POST", body={}, headers=connect))
        except ProviderError as error:
            if error.code == "rate_limited":
                raise
            failure, result = error, []
        if result:
            result += mappers.cursor_credits(obj(client.optional(base + "GetCreditGrantsBalance", method="POST", body={}, headers=connect)))
            result += mappers.cursor_grok(obj(client.optional(base + "GetSandUsageStatus", method="POST", body={}, headers=connect)))
        else:
            subject = text(jwt_payload(credential.token).get("sub"))
            if subject:
                user_id = subject.split("|", 1)[-1]
                cookie = {"Cookie": "WorkosCursorSessionToken=" + quote(user_id + "::" + credential.token, safe="")}
                summary = client.request("https://cursor.com/api/usage-summary", headers=cookie)
                result = mappers.cursor(summary, rest=True)
                data = client.optional("https://cursor.com/api/usage?user=" + quote(user_id, safe=""), headers=cookie)
                result += mappers.cursor_requests(obj(data))
            elif failure:
                raise failure
    elif provider == "devin":
        server = credential.data.get("server") or "https://server.codeium.com"
        # An explicit native API server is supported; never downgrade credential transport.
        if urlsplit(server).scheme != "https":
            raise ProviderError("https_required")
        result = mappers.devin(client.request(server.rstrip("/") + "/exa.seat_management_pb.SeatManagementService/GetUserStatus",
                                              method="POST", headers={"Connect-Protocol-Version": "1"}, body={"metadata": {
                                                  "apiKey": credential.token, "ideName": "devin", "ideVersion": "1.108.2",
                                                  "extensionName": "devin", "extensionVersion": "1.108.2", "locale": "en"}}))
    elif provider == "grok":
        result = mappers.grok(client.request("https://cli-chat-proxy.grok.com/v1/billing?format=credits",
                                            headers={**headers, "X-XAI-Token-Auth": "xai-grok-cli"}))
    elif provider == "ollama":
        try:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        except ImportError:
            raise ProviderError("cryptography_required") from None
        key = serialization.load_ssh_private_key(Path(credential.data["path"]).read_bytes(), password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise ProviderError("invalid_signing_key")
        public = key.public_key().public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH).split()[1]
        path = "/api/usage?ts=" + str(int(time.time()))
        signature = base64.b64encode(key.sign(("GET," + path).encode()))
        result = mappers.ollama(client.request("https://ollama.com" + path, headers={"Authorization": (public + b":" + signature).decode()}))
    elif provider == "opencode":
        result, failure = [], None
        if credential.token:
            try:
                result = mappers.opencode(client.request("https://opencode.ai/zen/go/v1/usage", headers=headers))
            except ProviderError as error:
                failure = error
        try:
            result += local_opencode(credential.data.get("root") or native.opencode_root())
        except (OSError, sqlite3.Error):
            if not result:
                raise ProviderError("local_usage_unavailable") from None
        if not result and failure:
            raise failure
    elif provider == "openrouter":
        payloads, failure = [], None
        for path in ("credits", "key"):
            try:
                payloads.append(client.request("https://openrouter.ai/api/v1/" + path, headers=headers))
            except ProviderError as error:
                payloads.append({})
                failure = error
                if error.code == "rate_limited":
                    raise
        result = mappers.openrouter(*payloads)
        if not result and failure:
            raise failure
    elif provider == "zai":
        result = mappers.zai(client.request("https://api.z.ai/api/monitor/usage/quota/limit", headers=headers))
    else:
        raise ProviderError("unknown_provider")
    return require_lines(result)
