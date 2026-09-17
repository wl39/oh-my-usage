# oh-my-usage · v0.6.1

**[English](../README.md) · [简体中文](README.zh-CN.md) · [한국어](README.ko.md)**

在 **iTerm2 状态栏**中查看 [OpenUsage](https://github.com/robinebers/openusage) 用量。也可开启终端内淡灰色提示：输入为空时显示，开始输入后隐藏。

**Mac + zsh + iTerm2 是兼容性最好的组合。** 需要 macOS 15+、Python 3.9+ 和原生 OpenUsage（已基于 0.7.6 验证）。Oh My Zsh 可选。其他终端和手机 SSH 客户端连接到同一 Mac 账户后，也能使用终端内显示。

## 安装 → 打开新标签页 → 启动

```zsh
git clone https://github.com/wl39/oh-my-usage.git
cd oh-my-usage
./install.sh
```

安装程序会复用已有的 OpenUsage；如果没有，则通过 Homebrew 安装。缺少 Python 时也会安装。如果需要 Homebrew 但尚未安装，请先前往 [brew.sh](https://brew.sh)。在 OpenUsage 的 **Customize** 中启用服务，并为要显示的指标加星标。

**安装完成后，打开一个新的 zsh 终端标签页。** 然后只需执行：

```zsh
oh-my-usage start
```

此命令会在不抢占焦点的情况下打开 OpenUsage，读取用量并更新显示。普通安装无需手动 `source`、配置 PATH 或编辑 `.zshrc`。以后新标签页会自动加载集成，需要重新打开应用或刷新时运行 `start` 即可。

> 安装程序是独立进程，不能直接向已经打开的 shell 添加命令，所以安装后需要打开一次新标签页。iTerm2 状态栏还需完成下方的一次性组件设置。终端内显示不需要状态栏设置。

安装说明和帮助在终端中使用柔和的颜色区分内容。重定向到文件或管道时输出纯文本。设置 `NO_COLOR=1` 可关闭颜色，`TERM=dumb` 环境也不会使用颜色。

## 常用命令

| 命令 | 效果 |
| --- | --- |
| `oh-my-usage` | 显示帮助，不读取用量 |
| `oh-my-usage help` / `oh-my-usage --help` | 显示相同的帮助 |
| `oh-my-usage start` | 打开 OpenUsage 并刷新显示 |
| `oh-my-usage inline on` | 开启终端内显示，**当前和以后的会话均生效** |
| `oh-my-usage inline off` | 关闭终端内显示，**当前和以后的会话均生效** |
| `oh-my-usage inline on --session` | 仅在当前 shell 中开启 |
| `oh-my-usage inline off --session` | 仅在当前 shell 中关闭 |
| `oh-my-usage inline status` | 查看实际生效的设置及其来源 |
| `oh-my-usage config` | 打开设置菜单 |
| `oh-my-usage doctor` | 检查应用、设置和 API 连接 |

只需运行所需的命令；`on` 和 `off` 是两种选择。运行 `oh-my-usage inline --help` 可查看该命令的帮助。

### 终端内显示：开启一次，以后自动保留

```zsh
oh-my-usage inline on
```

默认关闭。开启后，新标签页以及以后登录**同一账户的 SSH 会话**都会自动应用。已经打开的其他标签页会在下次显示提示符时读取新设置。`--session` 只影响当前 shell，不修改保存的值。不带该选项运行 `inline on/off` 会清除当前 shell 的临时覆盖，并保存新选择。

- 新标签页的第一个提示符会立即显示缓存；没有缓存时，读取完成后自动重绘当前行，无需按 Enter。
- 只有输入完全为空时才显示提示，默认淡灰色（颜色编号 `245`）。
- 输入文字、空格、粘贴内容、调出历史命令或多行续行时隐藏；清空输入后恢复。
- 宽度达到 80 列时显示在右侧提示符旁；更窄时显示在输入行上方。过长内容以 `…` 截断。
- 输入过程中，iTerm2 状态栏仍然显示。

设置保存在 `~/.config/oh-my-usage/inline` 这个小文件中，不会修改 `.zshrc`。优先级为：**`--session` → 已保存的选择 → `OH_MY_USAGE_INLINE` → 关闭**。保存的选择也会优先于 v0.4 中添加的 `export OH_MY_USAGE_INLINE=...`。

### 设置菜单：已用/剩余、顺序和颜色

```zsh
oh-my-usage config
```

输入编号并选择值即可立即保存。选择时按 Enter 取消，主菜单输入 `0` 退出。菜单包含终端内显示开关、**used（已用）/ left（剩余）**、**Claude → Codex / Codex → Claude**、自定义服务顺序，以及柔和的颜色预设和 256 色编号。

也可以直接运行：

```zsh
oh-my-usage config mode left
oh-my-usage config order claude,codex
oh-my-usage config color cyan
```

- `mode used` 显示已用量，`mode left` 显示剩余额度，`mode auto` 跟随 OpenUsage。
- `order claude,codex` 将 Claude 放在 Codex 前面，其余已启用的服务随后显示。不会启用服务或修改星标。`order auto` 恢复 OpenUsage 的顺序。
- `color` 支持 `gray`、`cyan`、`green`、`blue`、`purple`、`yellow`、`red`、`white` 或 `0`–`255`。保存值优先于 `OH_MY_USAGE_INLINE_COLOR`；`color auto` 恢复环境变量或默认颜色。
- **颜色仅应用于终端内显示。** iTerm2 状态栏颜色请在 Interpolated String 组件设置中修改。已用/剩余和顺序应用于两种显示。
- `config show` 查看设置；`config reset` 重置模式、顺序和颜色，保留终端内显示开关。

设置以小文件（`inline`、`mode`、`order`、`color`）保存在 `~/.config/oh-my-usage` 或自定义目录中。新标签页、SSH 会话和更新后仍然保留，不修改 OpenUsage 应用设置。其他已打开的标签页在下一个提示符生效。当前 shell 的 `inline --session` 覆盖仍然优先。缓存有效时，更改模式和顺序无需再次请求 API。

### iTerm2 状态栏：仅设置一次

1. 打开 **Settings → Profiles → 当前配置文件 → Session**，启用 **Status bar enabled**。
2. 在 **Configure Status Bar** 中添加 **Interpolated String**。
3. 在 **Configure Component → String Value** 中粘贴：

```text
\(user.oh_my_usage)
```

之后运行 `oh-my-usage start` 即可。现有配置和布局会保留。这里使用 iTerm2 自带组件，而非独立小组件。参考 [iTerm2 官方文档](https://iterm2.com/documentation-status-bar.html)。

### SSH / Termius / iPhone

通过 SSH 登录到运行 OpenUsage 的同一 Mac 账户，在 zsh 中执行一次 `oh-my-usage inline on`。以后的会话会记住设置。如果 OpenUsage 已关闭，运行 `oh-my-usage start` 会在 Mac 上打开它。

Mac 负责读取用量，客户端负责显示提示符。手机无需安装 iTerm2，也无需开放 API 端口、设置端口转发或伪造 `TERM_PROGRAM`。如果之前在 Termius 中强制设置了 `TERM_PROGRAM=iTerm.app`，请删除该赋值。连接其他主机时不会自动获得原 Mac 的用量。Windows、Linux 和手机可作为 SSH 客户端，但不支持作为数据读取主机。不支持 Bash、Fish、PowerShell 或旧版 Tauri OpenUsage。

## 更新到 v0.6.1

在克隆的仓库目录中运行：

```zsh
git pull --ff-only
./install.sh
```

打开新标签页，再运行 `oh-my-usage start`。如果首次安装使用了自定义 `--prefix` 或 `--no-shell`，请保留相同选项。

**v0.6.1 更新：** 修复新 shell 尚未加载行编辑器、以及 agnoster 等未预先定义右侧提示符的主题中首次显示失败的问题。快速提示符恢复终端输出后也会应用显示。无需按 Enter、增加启动等待或常驻进程。v0.6 的设置菜单保持可用。

## 常见问题

先运行 `oh-my-usage doctor`。

| 现象 | 处理方法 |
| --- | --- |
| `command not found` | 安装后打开新的 **zsh** 标签页；使用 `--no-shell` 时需自行加载插件 |
| 状态栏为空 | 检查配置文件及准确的 `\(user.oh_my_usage)` 值，然后运行 `start` |
| 没有终端内提示 | 查看 `inline status`，运行 `inline on` 并清空输入；过长的主题可能占满右侧空间 |
| `[offline]` | 在同一 Mac 账户中运行 `start`；当前显示的是上次成功读取的数据 |
| 服务名称后有 `~` | 数据超过 10 分钟未更新，或时间戳无效 |
| `no pinned data` | 在 OpenUsage 中启用服务，并为有数据的指标加星标 |
| `menuBarPins` / 设置错误 | 使用当前版本，在 Customize 中取消再添加星标，重启应用后运行 `refresh` |

缺少 `menuBarPins` 键时使用默认星标；已保存的空列表保持为空。`OH_MY_USAGE_DISPLAY=off` 会关闭两种显示；`start` 会在当前 shell 中重新启用集成。

## 高级选项

<details>
<summary>安装模式、环境变量、脚本和 Oh My Zsh</summary>

原有两种模式仍可使用：`./install-full.sh` 在缺少 OpenUsage 时安装；`./install-existing.sh` 仅使用已有应用。默认安装到 `~/.local/share/oh-my-usage`，备份 shell 配置，并在 `~/.zshrc` 或 `$ZDOTDIR/.zshrc` 中注册插件。请勿使用 `sudo`。使用 `--prefix /your/install/path` 可自定义目录，使用 `--no-shell` 可自行管理加载。

按需在加载插件之前设置环境变量：

| 变量 | 默认值 / 用途 |
| --- | --- |
| `OH_MY_USAGE_INLINE` | `off`；仅在没有保存值时作为默认设置 |
| `OH_MY_USAGE_INLINE_COLOR` | `245`；256 色编号，0–255；实际亮度取决于终端调色板 |
| `OH_MY_USAGE_INLINE_WIDTH` | 自动；提示最大宽度，受屏幕空间限制 |
| `OH_MY_USAGE_DISPLAY` | `status`；`off` 关闭两种显示 |
| `OH_MY_USAGE_INTERVAL` | `30`；缓存有效期，单位秒，最小 5 |
| `OH_MY_USAGE_CONFIG_DIR` | `$XDG_CONFIG_HOME/oh-my-usage`，或 `~/.config/oh-my-usage` |
| `OH_MY_USAGE_CACHE_DIR` | `~/Library/Caches/oh-my-usage` |
| `OH_MY_USAGE_PYTHON` | 自动检测；指定 Python 可执行文件 |
| `OH_MY_USAGE_PREFERENCES` | 可选的 OpenUsage plist 文件 |
| `OH_MY_USAGE_APP_DIR` | 包含 OpenUsage.app 的目录，供安装和 `start` 使用 |

路径请使用绝对路径或 `$HOME`。修改配置目录后，请打开新标签页。

`show` 使用缓存输出用量，`refresh` 强制刷新，`cached` 输出上次显示内容，`--version` 查看版本。`oh-my-usage-unload` 移除当前 shell 的 hook。脚本请使用 `~/.local/share/oh-my-usage/bin/oh-my-usage`；该可执行文件也支持通过 `inline on/off` 保存设置。`--session` 需要已加载的交互式 zsh 函数。

若要通过 Oh My Zsh 插件列表管理，而不是使用普通 source 配置块，请在首次安装时添加 `--no-shell`，然后运行：

```zsh
mkdir -p "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins"
ln -s "$HOME/.local/share/oh-my-usage" \
  "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/oh-my-usage"
```

在已有的 `plugins=(...)` 列表中添加 `oh-my-usage`。环境变量放在 Oh My Zsh 的 source 行之前。只选择一种加载方式；`--no-shell` 不会删除旧安装添加的 source 配置块。

</details>

<details>
<summary>从旧版 OUIterm 迁移与卸载</summary>

如果旧版 OUIterm 仍然存在，在新仓库中运行 `./install.sh uninstall --prefix "$HOME/.local/share/ouiterm"`；旧版使用自定义路径时请指定旧路径。删除手动添加的 `ouiterm` 插件项和符号链接，将 `OUITERM_*` 改为 `OH_MY_USAGE_*`，并将 `\(user.ouiterm)` 改为 `\(user.oh_my_usage)`。随后安装并打开新标签页。

卸载命令：

```zsh
~/.local/share/oh-my-usage/install.sh uninstall
```

卸载会移除安装文件、带标记的 shell 配置块和本工具的缓存。OpenUsage、Python、其他状态栏组件、备份及保存的设置会保留。关闭旧 shell 或运行 `oh-my-usage-unload`，并删除 Interpolated String 及手动添加的 Oh My Zsh 插件项/链接。自定义安装请使用对应目录中的 `install.sh uninstall`。

若要同时清除偏好设置，请删除配置目录中的 `inline`、`mode`、`order`、`color` 文件。之后会重新使用环境变量或默认值。

</details>

## 轻量设计与开发

仅使用 Python 标准库和 zsh，没有 pip 依赖、额外常驻进程或轮询定时器。标签页共享缓存和锁，在显示新提示符之前检查刷新，不会在空闲或运行命令时持续读取。按键处理使用 zsh 内置功能，保存的偏好设置在提示符阶段读取。读取结束后通过一次性管道通知 ZLE 重绘首个提示符，随后关闭管道。OpenUsage 应用本身需要单独运行。

读取程序只请求 `http://127.0.0.1:6736/v1/usage`，不读取凭据、钥匙串条目或对话日志。缓存和设置文件仅当前用户可访问。显示遵循星标和文字/条形模式；顺序和 Used/Left 在没有 `config` 覆盖时跟随 OpenUsage；每个服务最多两个指标，条形模式总计最多四个。菜单栏图标、颜色和屏幕共享检测不会复现。[legacy UI API](https://github.com/robinebers/openusage/blob/main/docs/local-http-api.md) 和上游设置格式可能变化。

运行 `./scripts/check.sh` 可检查语法并执行单元测试和真实 zsh 伪终端测试，包括跨会话设置保留。手机行为通过终端环境模拟验证，并非自动化 iPhone 界面测试。配置（`config.py`、`zsh/config.zsh`）、启动（`start.py`）、数据/显示设置/渲染/缓存、CLI、shell 传输和终端内显示分别由独立模块负责。个人笔记和预览不会进入 Git 或安装文件。

[MIT 许可证](../LICENSE)。本项目独立于 OpenUsage、iTerm2 和 Oh My Zsh。
