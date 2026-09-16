# oh-my-usage

**[English](README.md) · [简体中文](docs/README.zh-CN.md) · [한국어](docs/README.ko.md)**

A lightweight zsh integration that brings your [OpenUsage](https://github.com/robinebers/openusage) menu-bar metrics into the **iTerm2 status bar**, with an optional muted display that disappears as soon as you type.

**Best compatibility: Mac + zsh + iTerm2.** The current data reader and installer require macOS. Other terminal apps, including phone SSH clients, can use the optional inline display when connected to the same Mac account running OpenUsage.

```text
Status bar: [CPU] [Memory] [Codex Weekly 74%/Session 58% (left)]
```

Example values only. This project reads your own OpenUsage selections and usage.

## Why it stays small

- Python standard library and zsh only; no pip packages or plugin framework.
- No additional resident service or polling timer. Python runs briefly when a refresh is needed.
- Tabs share a small cache and a nonblocking lock to avoid duplicate requests.
- Typing visibility is handled by zsh itself, without launching a process for each keystroke.
- OpenUsage remains a separate app and must be running. The integration is lightweight, not zero-memory.

## Requirements

| Component | Requirement |
| --- | --- |
| Host | macOS 15 or later |
| Shell | Interactive zsh; Oh My Zsh is optional |
| Runtime | Python 3.9+ |
| Data source | Native OpenUsage; verified against version 0.7.6 |
| Status bar | iTerm2 |
| Inline display | A zsh terminal, locally or over SSH to the Mac |

Windows/Linux/phone devices can be SSH clients; they are not supported data-reader hosts. Bash, Fish, and PowerShell are not supported shells. The older Tauri edition of OpenUsage is not supported.

## 1. Install

Clone the repository, then choose **one** installation mode:

```zsh
git clone https://github.com/wl39/oh-my-usage.git
cd oh-my-usage
```

### A. OpenUsage is not installed

```zsh
./install-full.sh
```

Installs OpenUsage through its official Homebrew cask if missing, then installs oh-my-usage. If Homebrew is missing, install it from [brew.sh](https://brew.sh) first. Homebrew is not installed automatically.

### B. OpenUsage is already installed

```zsh
./install-existing.sh
```

Reuses the app and the current macOS account's menu-bar settings. Both modes install Python through Homebrew if a suitable Python is missing. Provider authentication is handled in OpenUsage.

Both modes install to `~/.local/share/oh-my-usage`, back up your shell configuration, and add a marked source block to `~/.zshrc` (or `$ZDOTDIR/.zshrc`). OpenUsage is opened after installation. Enable your providers and star the metrics you want in its **Customize** screen.

Activate the plugin in the current zsh tab, or open a new tab:

```zsh
source ~/.local/share/oh-my-usage/oh-my-usage.plugin.zsh
```

Use `--prefix /your/install/path` for a custom installation directory, or `--no-shell` to manage shell loading yourself. Do not install with `sudo`.

## 2. Add the iTerm2 status bar component

1. Open **iTerm2 → Settings → Profiles** and select your existing profile.
2. Under **Session**, enable **Status bar enabled**, then click **Configure Status Bar**.
3. Drag **Interpolated String** beside your existing components.
4. Open **Configure Component** and enter this exact **String Value**:

```text
\(user.oh_my_usage)
```

Open a new tab using that profile, or source the plugin as shown above. The component receives the value after the first read finishes.

This uses iTerm2's built-in component; there is no separate “oh-my-usage” widget to find. Your existing profiles and status bar layout are preserved. See the [iTerm2 status bar documentation](https://iterm2.com/documentation-status-bar.html).

## 3. Optional: show usage only while input is empty

Run the command you need in a zsh tab with the plugin loaded:

```zsh
oh-my-usage inline on       # Enable for this shell
oh-my-usage inline off      # Disable for this shell
oh-my-usage inline status   # Show the current setting
```

The default is **off**. When enabled:

- Usage appears in muted gray only while the entire command input is empty.
- Any text, whitespace, pasted content, or recalled command hides it. Clearing all input brings it back.
- It stays hidden on continuation lines of a multiline command.
- At 80 columns or wider, it appears beside the right prompt; on narrower screens, above the input line. Long text is truncated with `…`.
- The existing theme is restored when the hint is hidden or disabled. The iTerm2 status bar remains visible.

For persistent settings, put these lines **before the plugin's source block** in `.zshrc`:

```zsh
export OH_MY_USAGE_INLINE=on
export OH_MY_USAGE_INLINE_COLOR=245  # 256-color index, 0–255
# export OH_MY_USAGE_INLINE_WIDTH=30 # Optional maximum display width
```

The apparent brightness depends on your terminal palette. Change `on` to `off` to disable inline display in future shells. The `inline on/off` commands only change the current shell; they do not edit `.zshrc`.

## 4. SSH / Termius / iPhone

SSH into the **same Mac account** that runs OpenUsage, start zsh, and run:

```zsh
source ~/.local/share/oh-my-usage/oh-my-usage.plugin.zsh
oh-my-usage inline on
```

The Mac reads the data and renders the prompt; your SSH client displays it. No iTerm2 installation is required on the client. No API port forwarding or network exposure is needed. Connecting to another host does not carry the original Mac's usage with you.

To enable inline display only over SSH, put this before the source block in `.zshrc`:

```zsh
[[ -n ${SSH_CONNECTION:-} ]] && export OH_MY_USAGE_INLINE=on
```

Do not set `TERM_PROGRAM=iTerm.app` in Termius. If you manually added that value from an older guide, remove that assignment and use `unset TERM_PROGRAM` in that Termius session. Inline display does not depend on that variable. iTerm2 status codes are not sent in other terminals or inside tmux/screen; inline display can still be used there.

## Commands and configuration

| Command | Purpose |
| --- | --- |
| `oh-my-usage show` | Read usage, respecting the cache |
| `oh-my-usage refresh` | Force a fresh read; the next prompt/hook displays it |
| `oh-my-usage cached` | Print the last cached display |
| `oh-my-usage doctor` | Diagnose app, display settings, and local API access |
| `oh-my-usage --version` | Print the version |
| `oh-my-usage-unload` | Remove this shell's hooks and restore the prompt/status variable |

The command is a function loaded by the plugin. In scripts, use `~/.local/share/oh-my-usage/bin/oh-my-usage`. Inline commands and unloading require the interactive shell function.

Set environment options before loading the plugin:

| Variable | Default | Meaning |
| --- | --- | --- |
| `OH_MY_USAGE_DISPLAY` | `status` | `status` enables integration; `off` disables both displays |
| `OH_MY_USAGE_INLINE` | `off` | `on` enables empty-input display |
| `OH_MY_USAGE_INLINE_COLOR` | `245` | Muted gray, 256-color index |
| `OH_MY_USAGE_INLINE_WIDTH` | Automatic | Maximum width, capped to available screen space |
| `OH_MY_USAGE_INTERVAL` | `30` | Cache lifetime in seconds, minimum 5 |
| `OH_MY_USAGE_CACHE_DIR` | `~/Library/Caches/oh-my-usage` | Shared cache directory |
| `OH_MY_USAGE_PYTHON` | Detected Python | Python executable override |
| `OH_MY_USAGE_PREFERENCES` | macOS preferences | Optional OpenUsage plist file override |
| `OH_MY_USAGE_APP_DIR` | `/Applications` or `~/Applications` | Installer override: directory containing OpenUsage.app |

A refresh check runs **before a new prompt**. The interval is a cache lifetime, not a timer: an idle prompt or running command does not trigger periodic reads. When inline display is enabled via the environment, its first data may appear after Enter or after clearing input. Explicit `inline on` waits for the first read if the cache is missing.

OpenUsage's selected stars, provider/metric order, Used/Left mode, and text/bars mode are reflected. At most two metrics per provider are shown; bars mode is capped at four metrics overall. Missing metrics are omitted. Icons, colors, and screen-sharing detection from the menu bar are not reproduced.

## Oh My Zsh plugin list (optional)

The normal installation already works with Oh My Zsh. To manage it through `plugins=(...)` instead, use `--no-shell` on the first install:

```zsh
./install-existing.sh --no-shell
mkdir -p "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins"
ln -s "$HOME/.local/share/oh-my-usage" \
  "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/oh-my-usage"
```

Add `oh-my-usage` to your existing `plugins` list, for example `plugins=(git oh-my-usage)`. Place environment options before the Oh My Zsh source line. Use one loading method; `--no-shell` does not remove a source block from an earlier installation.

## Troubleshooting

Start with `oh-my-usage doctor`.

| Symptom | What to check |
| --- | --- |
| Empty status bar | Correct profile, enabled status bar, exact `\(user.oh_my_usage)` string, plugin sourced |
| No inline display | Run `inline on` in zsh; clear all input; a long theme may leave no right-prompt space on a wide screen |
| `[offline]` | Open OpenUsage in the same Mac account; the last good data is being shown |
| Provider name ends in `~` | Its snapshot is older than 10 minutes, or its timestamp is invalid |
| `no pinned data` | Enable providers and star metrics that currently have data |
| `menu-bar settings not saved` / `menuBarPins` error | Use the current version; toggle a metric star in Customize, reopen OpenUsage, then run `refresh` |
| `command not found` | Source the plugin or use the full executable path |

An absent `menuBarPins` key uses OpenUsage's default stars. An explicitly empty list stays empty. Settings are read through the macOS preferences service first, with a file fallback. Doctor does not print credentials or preference values.

## Update, migration, and removal

### Update

From your cloned repository:

```zsh
git pull --ff-only
./install-existing.sh
```

Open a new shell. Reuse `--prefix` and `--no-shell` if you originally used them.

### Migrate from OUIterm

Before installing the renamed version, run this from the new clone to remove a default legacy installation:

```zsh
./install.sh uninstall --prefix "$HOME/.local/share/ouiterm"
```

Use the old custom prefix if applicable. Skip this step if the old installation was already removed. Remove any manually added `ouiterm` Oh My Zsh entry/symlink, replace `OUITERM_*` options with `OH_MY_USAGE_*`, and replace `\(user.ouiterm)` with `\(user.oh_my_usage)` in iTerm2. Then install using mode A or B and open a new shell. Old option names are not aliases.

### Uninstall

```zsh
~/.local/share/oh-my-usage/install.sh uninstall
```

Installed files, the marked shell block, and owned cache files are removed. OpenUsage, Python, other iTerm2 components, and shell configuration backups are kept. Close old shells or run `oh-my-usage-unload`, and remove the Interpolated String component. If you used the Oh My Zsh plugin list, remove its entry and the symlink you added. For a custom prefix, run that installation's `install.sh uninstall`.

## Development and data handling

```zsh
./scripts/check.sh
```

Checks shell syntax and runs Python unit tests plus real zsh pseudo-terminal tests. Tests cover rendering, cache behavior, installation/removal, status transport, input hiding, resizing, and simulated SSH environments. Phone-client behavior is tested through those terminal simulations, not automated iPhone UI tests.

| Module | Responsibility |
| --- | --- |
| `oh_my_usage/settings.py` | OpenUsage display preferences |
| `oh_my_usage/source.py` | Local API access and validation |
| `oh_my_usage/metrics.py`, `render.py` | Metric mapping and pure text rendering |
| `oh_my_usage/cache.py` | Shared cache, atomic writes, locking |
| `oh_my_usage/diagnostics.py`, `__main__.py` | Diagnostics and CLI |
| `oh-my-usage.plugin.zsh` | Prompt refresh and iTerm2 transport |
| `zsh/inline.zsh` | Optional input-aware prompt display |
| `scripts/install.py` | Installation, shell backup, removal |

The reader only requests `http://127.0.0.1:6736/v1/usage`; it does not read provider credentials, keychain entries, or conversation logs. Cache files use user-only permissions. OpenUsage handles its own authentication and network activity separately. The integration uses the [legacy UI API](https://github.com/robinebers/openusage/blob/main/docs/local-http-api.md) for menu-bar metrics; future upstream API/settings changes may require updates.

Personal notes, local validation records, generated previews, and local configuration are excluded from Git. The installer copies only runtime files and public usage guides.

## License

[MIT](LICENSE). This is an independent integration, not an official OpenUsage, iTerm2, or Oh My Zsh project. OpenUsage is a separate project with its own license.
