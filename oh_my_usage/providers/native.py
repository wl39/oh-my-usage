"""Read the signed-in clients' native stores. Never change their credentials.

macOS lookups disable authentication UI, so background polling cannot prompt.
Protocol/format attribution: third_party/OpenUsage-LICENSE.txt.
"""

import base64
import ctypes
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import sqlite3
import subprocess
import sys
import time

from .common import Credential, Detection, ProviderError, number, obj, text


def run(command, timeout=4):
    try:
        result = subprocess.run(command, capture_output=True, timeout=timeout)
        return result.stdout if result.returncode == 0 else b""
    except (OSError, subprocess.SubprocessError):
        return b""


def keychain(service, account=None):
    if sys.platform != "darwin":
        return None
    try:
        result = subprocess.run([sys.executable, "-m", "oh_my_usage.providers.native", service, account or ""],
                                capture_output=True, timeout=5)
    except subprocess.TimeoutExpired:
        raise ProviderError("keychain_read_timeout") from None
    if result.returncode:
        raise ProviderError("keychain_access_required")
    return result.stdout or None


def _keychain_read(service, account=None):
    if sys.platform != "darwin":
        return None
    # Calling `security -w` from a prompt hook can open a modal access dialog.
    # Security.framework's explicit UI policy instead returns an error immediately.
    cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    sec = ctypes.CDLL("/System/Library/Frameworks/Security.framework/Security")
    pointer = ctypes.c_void_p
    cf.CFStringCreateWithCString.argtypes = [pointer, ctypes.c_char_p, ctypes.c_uint32]
    cf.CFStringCreateWithCString.restype = pointer
    cf.CFDictionaryCreate.argtypes = [pointer, pointer, pointer, ctypes.c_long, pointer, pointer]
    cf.CFDictionaryCreate.restype = pointer
    cf.CFDataGetLength.argtypes = [pointer]
    cf.CFDataGetLength.restype = ctypes.c_long
    cf.CFDataGetBytePtr.argtypes = [pointer]
    cf.CFDataGetBytePtr.restype = pointer
    cf.CFRelease.argtypes = [pointer]
    sec.SecItemCopyMatching.argtypes = [pointer, ctypes.POINTER(pointer)]
    sec.SecItemCopyMatching.restype = ctypes.c_int32

    def constant(name):
        return pointer.in_dll(sec, name).value

    owned = []

    def string(value):
        result = cf.CFStringCreateWithCString(None, value.encode(), 0x08000100)
        owned.append(result)
        return result

    pairs = [(constant("kSecClass"), constant("kSecClassGenericPassword")),
             (constant("kSecAttrService"), string(service)),
             (constant("kSecReturnData"), pointer.in_dll(cf, "kCFBooleanTrue").value),
             (constant("kSecUseAuthenticationUI"), constant("kSecUseAuthenticationUIFail"))]
    if account:
        pairs.append((constant("kSecAttrAccount"), string(account)))
    keys = (pointer * len(pairs))(*(x[0] for x in pairs))
    values = (pointer * len(pairs))(*(x[1] for x in pairs))
    query = cf.CFDictionaryCreate(None, keys, values, len(pairs),
                                 ctypes.addressof(ctypes.c_byte.in_dll(cf, "kCFTypeDictionaryKeyCallBacks")),
                                 ctypes.addressof(ctypes.c_byte.in_dll(cf, "kCFTypeDictionaryValueCallBacks")))
    result = pointer()
    try:
        status = sec.SecItemCopyMatching(query, ctypes.byref(result))
        if status == -25300:  # errSecItemNotFound
            return None
        if status:
            raise ProviderError("keychain_access_required")
        length = cf.CFDataGetLength(result)
        if not 0 <= length <= 4 * 1024 * 1024:
            raise ProviderError("invalid_credentials")
        return ctypes.string_at(cf.CFDataGetBytePtr(result), length)
    finally:
        if result.value:
            cf.CFRelease(result)
        cf.CFRelease(query)
        for value in owned:
            cf.CFRelease(value)


def decode_json(raw):
    try:
        return obj(json.loads(raw))
    except (ValueError, UnicodeError):
        return obj(json.loads(bytes.fromhex(raw.decode().strip())))


def read_json(path):
    try:
        if path.stat().st_size > 4 * 1024 * 1024:
            raise ProviderError("invalid_credentials")
        return obj(json.loads(path.read_text()))
    except FileNotFoundError:
        return {}


def sqlite_values(path, keys):
    if not path.exists():
        return {}
    connection = sqlite3.connect(path.absolute().as_uri() + "?mode=ro", uri=True, timeout=1)
    try:
        placeholders = ",".join("?" for _ in keys)
        return dict(connection.execute(f"SELECT key, value FROM ItemTable WHERE key IN ({placeholders})", keys))
    finally:
        connection.close()


def application_dir(name):
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support" / name
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / name


def app_installed(name, command):
    return bool(shutil.which(command) or application_dir(name).exists() or
                (sys.platform == "darwin" and (Path("/Applications") / (name + ".app")).exists()))


def antigravity_servers():
    found = []
    for line in run(["ps", "-axo", "pid=,args="]).decode(errors="replace").splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2 or not parts[0].isdigit():
            continue
        pid, command = parts
        try:
            argv = shlex.split(command)
        except ValueError:
            continue
        if not argv or "language_server" not in Path(argv[0]).name:
            continue
        if "antigravity" not in command.lower():
            continue
        match = re.search(r"--csrf_token(?:=|\s+)(\S+)", command)
        if not match:
            continue
        listeners = run(["lsof", "-nP", "-a", "-p", pid, "-iTCP", "-sTCP:LISTEN", "-Fn"])
        ports = {int(x.rsplit(":", 1)[1]) for x in listeners.decode().splitlines()
                 if re.fullmatch(r"n127\.0\.0\.1:\d+", x)}
        # Linux fallback without lsof: map this process's socket inodes to tcp listeners.
        if not ports and sys.platform.startswith("linux"):
            try:
                inodes = {os.readlink(p)[8:-1] for p in (Path("/proc") / pid / "fd").iterdir()
                          if os.readlink(p).startswith("socket:[")}
                for row in (Path("/proc") / pid / "net/tcp").read_text().splitlines()[1:]:
                    cells = row.split()
                    if cells[3] == "0A" and cells[9] in inodes and cells[1].startswith("0100007F:"):
                        ports.add(int(cells[1].split(":")[1], 16))
            except OSError:
                pass
        if ports:
            found.append({"ports": sorted(ports), "csrf": match.group(1), "pid": pid})
    return found


def opencode_root():
    return Path(os.environ.get("OPENCODE_DATA_DIR") or
                Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "opencode").expanduser()


def detect(provider):
    from .. import config
    # This tool's own optional credentials, never OpenUsage's private stores.
    own_error = False
    try:
        own = read_json(config.directory() / "credentials.json")
    except (OSError, ValueError, ProviderError):
        own, own_error = {}, True
    env_names = {"openrouter": ("OPENROUTER_API_KEY",), "zai": ("ZAI_API_KEY", "GLM_API_KEY"),
                 "copilot": ("GH_TOKEN", "GITHUB_TOKEN"), "claude": ("CLAUDE_CODE_OAUTH_TOKEN",),
                 "opencode": ("OPENCODE_GO_API_KEY",), "devin": ("DEVIN_API_KEY",),
                 "antigravity": ("ANTIGRAVITY_ACCESS_TOKEN",)}
    for name in env_names.get(provider, ()):
        token = text(os.environ.get(name))
        if token:
            return Detection(True, Credential("environment:" + name, token), "ready")
    if provider in env_names and text(own.get(provider)):
        return Detection(True, Credential("oh-my-usage credentials", own[provider]), "ready")
    installed, credential, status = False, None, "authentication_required"
    if provider == "codex":
        executable = shutil.which("codex")
        root = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()
        auth = read_json(root / "auth.json")
        installed = bool(executable or root.exists())
        if executable:
            # CLI also supports OS credential storage, so absence of auth.json is not logout.
            binding = json.dumps(auth, sort_keys=True) if auth else "native-cli"
            credential = Credential("codex app-server", data={"executable": executable}, binding=binding)
        else:
            status = "cli_required"
    elif provider == "antigravity":
        installed = app_installed("Antigravity", "antigravity")
        servers = antigravity_servers()
        if servers:
            credential = Credential("Antigravity local server", data={"servers": servers},
                                    binding=json.dumps(servers, sort_keys=True))
            installed = True
        elif sys.platform == "darwin" and installed:
            raw = keychain("gemini", "antigravity")
            if raw:
                if raw.startswith(b"go-keyring-base64:"):
                    raw = base64.b64decode(raw.split(b":", 1)[1])
                token = text(obj(decode_json(raw).get("token")).get("access_token"))
                if token:
                    credential = Credential("Antigravity keychain", token)
            status = "start_client_or_sign_in"
        else:
            status = "start_client_or_sign_in"
    elif provider == "claude":
        root = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude").expanduser()
        installed = bool(shutil.which("claude") or root.exists() or app_installed("Claude", "claude"))
        candidates = [("Claude Code file", read_json(root / ".credentials.json"))]
        keychain_error = None
        if sys.platform == "darwin" and installed:
            custom = os.environ.get("CLAUDE_CONFIG_DIR")
            service = "Claude Code-credentials" + ("-" + hashlib.sha256(custom.encode()).hexdigest()[:8] if custom else "")
            try:
                raw = keychain(service, getpass.getuser())
                if raw:
                    candidates.insert(0, ("Claude Code keychain", decode_json(raw)))
            except ProviderError as error:
                keychain_error = error
        for origin, data in candidates:
            auth = obj(data.get("claudeAiOauth"))
            expires = number(auth.get("expiresAt"))
            scopes = auth.get("scopes")
            if expires is not None and expires <= time.time() * 1000 + 60000:
                status = "login_expired"
                continue
            if isinstance(scopes, list) and scopes and "user:profile" not in scopes:
                status = "usage_scope_required"
                continue
            if text(auth.get("accessToken")):
                credential = Credential(origin, auth["accessToken"])
                break
        if not credential and sys.platform == "darwin" and (application_dir("Claude") / "config.json").exists():
            try:
                credential = Credential("Claude Desktop", desktop_token())
            except ProviderError as error:
                status = error.code
        elif not credential and keychain_error:
            status = keychain_error.code
    elif provider == "copilot":
        root = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
        installed = (root / "github-copilot").exists() or bool(shutil.which("gh") or shutil.which("copilot"))
        for name in ("apps.json", "hosts.json"):
            for host, entry in read_json(root / "github-copilot" / name).items():
                if (host == "github.com" or host.startswith("github.com:")) and text(obj(entry).get("oauth_token")):
                    credential = Credential("GitHub Copilot " + name, entry["oauth_token"])
                    break
            if credential:
                break
        if not credential and shutil.which("gh"):
            token = run(["gh", "auth", "token", "--hostname", "github.com"]).decode().strip()
            if token:
                credential = Credential("GitHub CLI", token)
        if not credential:
            hosts = root / "gh/hosts.yml"
            if hosts.exists():
                installed = True
                active = False
                for line in hosts.read_text().splitlines():
                    if line and not line[0].isspace() and not line.startswith("#"):
                        active = line.strip() == "github.com:"
                    match = re.fullmatch(r"\s{4}oauth_token:\s*([A-Za-z0-9_]+)\s*", line)
                    if active and match:
                        credential = Credential("GitHub CLI hosts", match.group(1))
                        break
    elif provider == "cursor":
        installed = app_installed("Cursor", "cursor")
        values = sqlite_values(application_dir("Cursor") / "User/globalStorage/state.vscdb", ["cursorAuth/accessToken"])
        token = text(values.get("cursorAuth/accessToken"))
        if not token and installed and sys.platform == "darwin":
            token = (keychain("cursor-access-token") or b"").decode().strip()
        if token:
            credential = Credential("Cursor native login", token)
    elif provider == "devin":
        root = Path.home() / ".local/share/devin"
        installed = root.exists() or app_installed("Devin", "devin")
        path = root / "credentials.toml"
        if path.exists():
            # Only two single-line scalar fields are needed; no optional TOML dependency.
            data = {}
            for key, value in re.findall(r'(?m)^\s*(windsurf_api_key|api_server_url)\s*=\s*(["\'][^\r\n]*?["\'])\s*(?:#.*)?$', path.read_text()):
                data[key] = json.loads(value) if value.startswith('"') else value[1:-1]
            if text(data.get("windsurf_api_key")):
                credential = Credential("Devin CLI", data["windsurf_api_key"], {"server": data.get("api_server_url")})
        if not credential:
            value = sqlite_values(application_dir("Devin") / "User/globalStorage/state.vscdb", ["windsurfAuthStatus"])
            auth = obj(json.loads(value.get("windsurfAuthStatus", "{}")))
            if text(auth.get("apiKey")):
                credential = Credential("Devin editor", auth["apiKey"])
    elif provider == "grok":
        root = Path(os.environ.get("GROK_HOME") or Path.home() / ".grok").expanduser()
        installed = root.exists() or bool(shutil.which("grok"))
        for entry in read_json(root / "auth.json").values():
            if text(obj(entry).get("key")):
                credential = Credential("Grok CLI", entry["key"])
                break
    elif provider == "ollama":
        path = Path.home() / ".ollama/id_ed25519"
        installed = path.exists() or bool(shutil.which("ollama"))
        if path.exists():
            credential = Credential("Ollama signing key", data={"path": str(path)},
                                    binding=hashlib.sha256(path.read_bytes()).hexdigest())
    elif provider == "opencode":
        root = opencode_root()
        installed = root.exists() or bool(shutil.which("opencode"))
        auth = read_json(root / "auth.json")
        token = text(obj(auth.get("opencode-go")).get("key"))
        if token:
            credential = Credential("OpenCode Go", token, {"root": str(root)})
        elif list(root.glob("opencode*.db")):
            # Zen exposes local spend, not a subscription quota endpoint.
            credential = Credential("OpenCode local usage", data={"root": str(root)}, binding=str(root))
    elif provider in ("openrouter", "zai"):
        status = "credentials_unreadable" if own_error else "api_key_required"
    return Detection(installed, credential, "ready" if credential else status if installed or provider in ("openrouter", "zai") else "not_installed")


def desktop_decrypt(encrypted, key):
    if not encrypted.startswith(b"v10"):
        raise ProviderError("desktop_encryption_format_unsupported")
    # Keep the key out of subprocess arguments. CommonCrypto is supplied by macOS.
    library = ctypes.CDLL("/usr/lib/system/libcommonCrypto.dylib")
    crypt = library.CCCrypt
    crypt.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p, ctypes.c_size_t,
                      ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p,
                      ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    crypt.restype = ctypes.c_int
    payload = encrypted[3:]
    output = ctypes.create_string_buffer(len(payload) + 16)
    length = ctypes.c_size_t()
    result = crypt(1, 0, 1, key, len(key), b" " * 16, payload, len(payload), output, len(output), ctypes.byref(length))
    if result:
        raise ProviderError("desktop_decryption_failed")
    return output.raw[:length.value]

def desktop_token():
    if sys.platform != "darwin":
        raise ProviderError("desktop_probe_macos_only")
    root = Path.home() / "Library/Application Support/Claude"
    config = json.loads((root / "config.json").read_text())
    if not any(isinstance(config.get(k), str) for k in ("oauth:tokenCache", "oauth:tokenCacheV2")):
        raise ProviderError("desktop_login_not_found")
    password = keychain("Claude Safe Storage", "Claude Key")
    if not password:
        raise ProviderError("desktop_keychain_unavailable")
    key = hashlib.pbkdf2_hmac("sha1", password, b"saltysalt", 1003, dklen=16)
    organization = None
    # Read only the active-organization marker, not session cookies or browsing data.
    for relative in ("Cookies", "Network/Cookies"):
        path = root / relative
        if not path.exists():
            continue
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        try:
            rows = connection.execute("SELECT host_key, value, encrypted_value FROM cookies "
                                      "WHERE name = 'lastActiveOrg' AND host_key IN ('.claude.ai', 'claude.ai') "
                                      "ORDER BY last_update_utc DESC").fetchall()
        finally:
            connection.close()
        for host, plain, encrypted in rows:
            if plain:
                organization = plain.lower()
            else:
                decoded = desktop_decrypt(encrypted, key)
                digest = hashlib.sha256(host.encode()).digest()
                if decoded.startswith(digest):
                    organization = decoded[len(digest):].decode().lower()
            if organization:
                break
        if organization:
            break
    if not organization:
        raise ProviderError("desktop_active_organization_missing")
    active_account = str(config.get("lastKnownAccountUuid", "")).lower()
    entries = {}
    for version in ("oauth:tokenCache", "oauth:tokenCacheV2"):
        if not isinstance(config.get(version), str):
            continue
        cache = json.loads(desktop_decrypt(base64.b64decode(config[version], validate=True), key))
        legacy, scoped = {}, {}
        for name, entry in cache.items():
            if name.startswith("acct:"):
                owner, separator, name = name[5:].partition("|")
                if separator and owner.lower() == active_account:
                    scoped[name] = entry
            else:
                legacy[name] = entry
        # Scoped entries and V2 deletion markers suppress obsolete fallback entries.
        legacy.update(scoped)
        entries.update(legacy)
    candidates = []
    for name, entry in entries.items():
        prefix, marker, scope_text = name.partition(":https://api.anthropic.com:")
        client, separator, org = prefix.partition(":")
        scopes = scope_text.split()
        if not marker or not separator or org.lower() != organization or "user:profile" not in scopes:
            continue
        if not isinstance(entry, dict) or not isinstance(entry.get("token"), str):
            continue
        expires = entry.get("expiresAt")
        if not (number(expires) is not None) or expires <= time.time() * 1000 + 120000:
            continue
        full = "user:inference" in scopes
        rank = (client == "9d1c250a-e61b-44d9-88ed-5944d1962f5e" and full, full, len(scopes), expires)
        candidates.append((rank, entry["token"]))
    if not candidates:
        raise ProviderError("desktop_login_expired_or_missing")
    return max(candidates, key=lambda item: item[0])[1]


if __name__ == '__main__':
    # Private helper: stdout is an anonymous pipe consumed only by keychain().
    # Keeping Security.framework in this bounded process prevents a hung keychain
    # service from blocking the collector's worker pool or cache lock indefinitely.
    try:
        if sys.stdout.isatty() or len(sys.argv) != 3:
            sys.exit(2)
        sys.stdout.buffer.write(_keychain_read(sys.argv[1], sys.argv[2] or None) or b'')
    except Exception:
        sys.exit(1)
