# oh-my-usage · v0.6.1

**[English](README.md) · [简体中文](docs/README.zh-CN.md) · [한국어](docs/README.ko.md)**

Your [OpenUsage](https://github.com/robinebers/openusage) metrics in the **iTerm2 status bar**, with an optional muted hint that disappears while you type.

**Best compatibility: Mac + zsh + iTerm2.** Requires macOS 15+, Python 3.9+, and native OpenUsage (verified against 0.7.6). Oh My Zsh is optional. Other terminal apps and phone SSH clients can display the inline hint when connected to the same Mac account.

## Install → open a new tab → start

```zsh
git clone https://github.com/wl39/oh-my-usage.git
cd oh-my-usage
./install.sh
```

The installer reuses OpenUsage if present, or installs it through Homebrew if missing. It also installs Python if needed. If Homebrew is required but missing, install it from [brew.sh](https://brew.sh) first. In OpenUsage, enable your providers and star the metrics you want in **Customize**.

**Open a new zsh terminal tab after installation.** Then run just:

```zsh
oh-my-usage start
```

This opens OpenUsage without stealing focus, refreshes usage, and updates your display. No manual `source`, PATH setup, or `.zshrc` editing is needed with the normal installer. Future tabs load the integration automatically; `start` can reopen OpenUsage and refresh whenever needed.

> The installer runs as a separate process, so an already-open shell needs a new tab to pick up the command. The iTerm2 status bar also needs the one-time component setup below. Inline display needs no status bar setup.

Help and installation instructions use subtle colors in a terminal. Redirected output stays plain text. Set `NO_COLOR=1` to disable color; `TERM=dumb` is also respected.

## The commands you need

| Command | Result |
| --- | --- |
| `oh-my-usage` | Show help; does not fetch usage |
| `oh-my-usage help` / `oh-my-usage --help` | Show the same help |
| `oh-my-usage start` | Open OpenUsage and refresh the display |
| `oh-my-usage inline on` | Enable inline display **now and in future sessions** |
| `oh-my-usage inline off` | Disable inline display **now and in future sessions** |
| `oh-my-usage inline on --session` | Enable only in this shell |
| `oh-my-usage inline off --session` | Disable only in this shell |
| `oh-my-usage inline status` | Show the effective setting and where it came from |
| `oh-my-usage config` | Open the settings menu |
| `oh-my-usage doctor` | Diagnose app, settings, and API access |

Run only the command you need; `on` and `off` are alternatives. `oh-my-usage inline --help` shows help for that command.

### Inline: saved once, used across sessions

```zsh
oh-my-usage inline on
```

The default is off. Once enabled, new tabs and later SSH sessions into the **same account** use it automatically. Already-open tabs pick up a changed setting at their next prompt. A `--session` override stays local to that shell and leaves the saved preference untouched. Running `inline on/off` without the flag clears the current shell's temporary override and saves the new choice.

- The first prompt displays cached data immediately; if no cache exists, it redraws as soon as the read finishes. No Enter is needed.
- Display appears only when input is completely empty, in muted gray (`245`) by default.
- Typing, spaces, paste, history recall, and multiline continuations hide it. Clearing input restores it.
- On screens at least 80 columns wide it appears beside the right prompt; narrower screens show it above the input line. Long text ends in `…`.
- The iTerm2 status bar remains visible while typing.

The setting is a tiny data file at `~/.config/oh-my-usage/inline`, not an edit to `.zshrc`. Priority: **`--session` → saved choice → `OH_MY_USAGE_INLINE` → off**. Saved choices also take precedence over old `export OH_MY_USAGE_INLINE=...` lines from v0.4.

### Settings menu: meter, order, and color

```zsh
oh-my-usage config
```

Choose a number, then a value. Each change saves immediately; Enter cancels a choice, and `0` exits. The menu includes inline on/off, **used / left**, **Claude → Codex / Codex → Claude**, custom provider order, and muted color presets or a 256-color index.

You can also set a single option directly:

```zsh
oh-my-usage config mode left
oh-my-usage config order claude,codex
oh-my-usage config color cyan
```

- `mode used` shows consumption; `mode left` shows remaining allowance. `mode auto` follows OpenUsage.
- `order claude,codex` puts Claude first and Codex second. Other enabled providers follow; this does not enable providers or change starred metrics. `order auto` follows OpenUsage.
- `color` accepts `gray`, `cyan`, `green`, `blue`, `purple`, `yellow`, `red`, `white`, or `0`–`255`. Saved colors override `OH_MY_USAGE_INLINE_COLOR`; `color auto` restores the environment/default color.
- **Color applies to inline text.** For the iTerm2 status bar, set the text color in the Interpolated String component's configuration. Meter and order apply to both displays.
- `config show` lists choices. `config reset` resets meter, order, and color; inline on/off stays unchanged.

Preferences are small files (`inline`, `mode`, `order`, `color`) in `~/.config/oh-my-usage` (or your configured directory). They persist across new tabs, SSH sessions, and updates without changing OpenUsage's own settings. Other open tabs adopt changes at their next prompt. An inline `--session` override still takes priority in its shell. A fresh cached snapshot can be reformatted without another API request.

### iTerm2 status bar: one-time setup

1. **Settings → Profiles → your profile → Session**: enable **Status bar enabled**.
2. **Configure Status Bar**: add **Interpolated String** beside your existing components.
3. **Configure Component → String Value**: paste:

```text
\(user.oh_my_usage)
```

Then use `oh-my-usage start`. Existing profiles/layouts are preserved. This is an iTerm2 built-in component, not a separate widget. [Official iTerm2 guide](https://iterm2.com/documentation-status-bar.html).

### SSH / Termius / iPhone

SSH into the same Mac account running OpenUsage, use zsh, and run `oh-my-usage inline on` once. Your next sessions remember it. If OpenUsage is closed, `oh-my-usage start` opens it on the Mac.

The Mac reads the usage; the client displays the prompt. No iTerm2 on the phone, API port forwarding, or `TERM_PROGRAM` spoofing is needed. If you previously forced `TERM_PROGRAM=iTerm.app` in Termius, remove that assignment. Other servers do not automatically receive this Mac's usage. Windows/Linux/phones are supported as SSH clients, not data-reader hosts. Bash/Fish/PowerShell and old Tauri OpenUsage are not supported.

## Update to v0.6.1

From your cloned repository:

```zsh
git pull --ff-only
./install.sh
```

Open a new tab, then use `oh-my-usage start`. Reuse any custom `--prefix` or `--no-shell` option from your original install.

**New in v0.6.1:** fixes the first prompt on fresh shells and themes with no existing right prompt, including agnoster. It also publishes after instant-prompt themes restore terminal output. No Enter, startup sleep, or resident process is required. The saved settings menu from v0.6 remains available.

## Troubleshooting

Start with `oh-my-usage doctor`.

| Symptom | Fix |
| --- | --- |
| `command not found` | Open a new **zsh** tab after installing; a custom `--no-shell` setup must load the plugin itself |
| Empty status bar | Check the profile and exact `\(user.oh_my_usage)` value, then run `start` |
| No inline hint | Run `inline status`, then `inline on`; clear input. A very long theme may leave no right-prompt space |
| `[offline]` | Run `start` in the same Mac account; the last successful data is being shown |
| Provider name ends in `~` | The snapshot is over 10 minutes old or has an invalid timestamp |
| `no pinned data` | Enable providers and star metrics with available data in OpenUsage |
| `menuBarPins` / settings error | Use this version; toggle a star in Customize, reopen OpenUsage, and run `refresh` |

A missing `menuBarPins` key uses OpenUsage's default stars; an explicitly empty list stays empty. `OH_MY_USAGE_DISPLAY=off` disables both displays; `start` re-enables integration in the current shell.

## Advanced options

<details>
<summary>Installation modes, configuration, scripts, and Oh My Zsh</summary>

The original two modes remain available: `./install-full.sh` installs OpenUsage if missing; `./install-existing.sh` requires an existing app. Both install to `~/.local/share/oh-my-usage`, back up shell configuration, and register the plugin in `~/.zshrc` or `$ZDOTDIR/.zshrc`. Do not use `sudo`. Use `--prefix /your/install/path` for a custom directory, or `--no-shell` for manual plugin management.

Optional environment variables, placed before the plugin loads:

| Variable | Default / purpose |
| --- | --- |
| `OH_MY_USAGE_INLINE` | `off`; fallback when no saved choice exists |
| `OH_MY_USAGE_INLINE_COLOR` | `245`; 256-color index, 0–255; brightness depends on your palette |
| `OH_MY_USAGE_INLINE_WIDTH` | Automatic; maximum hint width, capped to screen space |
| `OH_MY_USAGE_DISPLAY` | `status`; `off` disables both displays |
| `OH_MY_USAGE_INTERVAL` | `30`; cache lifetime in seconds, minimum 5 |
| `OH_MY_USAGE_CONFIG_DIR` | `$XDG_CONFIG_HOME/oh-my-usage`, or `~/.config/oh-my-usage` |
| `OH_MY_USAGE_CACHE_DIR` | `~/Library/Caches/oh-my-usage` |
| `OH_MY_USAGE_PYTHON` | Detected Python; override its executable path |
| `OH_MY_USAGE_PREFERENCES` | Optional OpenUsage plist file |
| `OH_MY_USAGE_APP_DIR` | Folder containing OpenUsage.app, for installation and `start` |

Use absolute paths or `$HOME` in path overrides. Open a new tab after changing the configuration directory.

`show` prints usage using the cache, `refresh` forces a new read, `cached` prints the last display, and `--version` prints the version. `oh-my-usage-unload` removes the current shell's hooks. For scripts, use `~/.local/share/oh-my-usage/bin/oh-my-usage`; `inline on/off` also saves settings through this executable. `--session` requires the loaded interactive zsh function.

To manage the plugin via Oh My Zsh instead of the normal source block, use `--no-shell` on the first install, then:

```zsh
mkdir -p "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins"
ln -s "$HOME/.local/share/oh-my-usage" \
  "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/oh-my-usage"
```

Add `oh-my-usage` to your existing `plugins=(...)` list. Put environment settings before the Oh My Zsh source line. Choose one loading method; `--no-shell` does not remove an earlier source block.

</details>

<details>
<summary>Migration from OUIterm and uninstall</summary>

If the old OUIterm installation still exists, remove it from the new clone with `./install.sh uninstall --prefix "$HOME/.local/share/ouiterm"` (use the old custom path if applicable). Remove manually added `ouiterm` plugin entries/symlinks, rename `OUITERM_*` variables to `OH_MY_USAGE_*`, and replace `\(user.ouiterm)` with `\(user.oh_my_usage)`. Then install and open a new tab.

To uninstall:

```zsh
~/.local/share/oh-my-usage/install.sh uninstall
```

Installed files, the marked shell block, and owned cache files are removed. OpenUsage, Python, other status bar components, backups, and saved preferences are kept. Close old shells or run `oh-my-usage-unload`; remove the Interpolated String and any manually added Oh My Zsh entry/symlink. For a custom install, use its `install.sh uninstall`.

To discard saved preferences too, remove the `inline`, `mode`, `order`, and `color` files from your configuration directory. The defaults then apply again.

</details>

## Lightweight design and development

Python standard library + zsh; no pip dependencies, extra daemon, or periodic timer. Tabs share a cache and lock. A refresh check runs before a new prompt, not continuously while idle or running a command. Keypress handling uses zsh builtins, and saved preferences are read at prompt boundaries. A one-shot pipe notifies ZLE when a read finishes so the first prompt redraws without keyboard input; the pipe closes immediately afterward. OpenUsage itself must run separately.

The reader requests only `http://127.0.0.1:6736/v1/usage`; it does not read credentials, keychain entries, or conversation logs. Cache/settings files are private to the user. Selected stars and text/bars modes are reflected; order and Used/Left follow OpenUsage unless overridden in `config`; up to two metrics per provider, or four total in bars mode. Menu-bar icons/colors/screen-sharing detection are not reproduced. The [legacy UI API](https://github.com/robinebers/openusage/blob/main/docs/local-http-api.md) and upstream settings can change.

Run `./scripts/check.sh` for syntax checks, unit tests, and real zsh pseudo-terminal tests, including persistence across sessions. Phone behavior uses simulated terminal environments, not automated iPhone UI tests. Modules separate config (`config.py`, `zsh/config.zsh`), startup (`start.py`), data/settings/rendering/cache, CLI, shell transport, and inline display. Personal notes and previews are excluded from Git and installation.

[MIT license](LICENSE). Independent of the OpenUsage, iTerm2, and Oh My Zsh projects.
