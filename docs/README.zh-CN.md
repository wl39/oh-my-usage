# oh-my-usage · v0.7.0

**[English](../README.md) · [简体中文](README.zh-CN.md) · [한국어](README.ko.md)**

直接读取 **11 个 AI 服务**的用量，并在 zsh 提示符和 **iTerm2 状态栏**中显示。自动发现已安装、已登录的客户端；开始输入后隐藏提示。

**支持 macOS 和 Linux。** 需要 Python 3.9+；提示符集成使用 zsh。OpenUsage 和 Oh My Zsh 均为可选。安装程序创建独立 Python 环境，并安装 Ollama 签名所需的 `cryptography`。

## 演示

![输入时隐藏、清空后恢复的用量提示，以及剩余额度、服务顺序和颜色设置](assets/inline-demo.gif)

使用**示例数据录制并渲染的真实 zsh 输出**，展示首个提示符显示、输入时隐藏，以及保存剩余额度、顺序和颜色设置。演示的是可选的终端内显示，iTerm2 状态栏需按下方说明单独配置。[终端录制文件](assets/inline-demo.cast)：如已安装 asciinema，可在仓库中运行 `asciinema play docs/assets/inline-demo.cast` 回放。

<details>
<summary>查看设置菜单 — oh-my-usage config</summary>

![设置菜单：开启终端内显示、显示剩余额度、Claude 排在 Codex 前、使用柔和的青色](assets/settings.png)

输入编号修改设置。更改立即保存，并在以后的会话中生效。

</details>

## 安装 → 打开新标签页 → 启动

```zsh
git clone https://github.com/wl39/oh-my-usage.git
cd oh-my-usage
./install.sh
```

先安装 Python 和 zsh。Debian/Ubuntu：`sudo apt-get install python3 python3-venv zsh`。macOS 可按需使用 `brew install python zsh`。不使用 sudo 运行本安装程序。默认 `direct` 模式无需 OpenUsage，新安装会启用行内显示；已有显示偏好保持不变。

**安装完成后，打开一个新的 zsh 终端标签页。** 然后只需执行：

```zsh
oh-my-usage start
```

此命令发现已登录的服务、读取用量并更新显示。新标签页的第一个提示符也会自动启动发现；之后新安装或登录的服务在后续刷新时连接。普通安装无需手动配置 PATH、source 或编辑 `.zshrc`。

> 安装程序是独立进程，不能直接向已经打开的 shell 添加命令，所以安装后需要打开一次新标签页。iTerm2 状态栏还需完成下方的一次性组件设置。终端内显示不需要状态栏设置。

安装说明和帮助在终端中使用柔和的颜色区分内容。重定向到文件或管道时输出纯文本。设置 `NO_COLOR=1` 可关闭颜色，`TERM=dumb` 环境也不会使用颜色。

## 常用命令

| 命令 | 效果 |
| --- | --- |
| `oh-my-usage` | 显示帮助，不读取用量 |
| `oh-my-usage help` / `oh-my-usage --help` | 显示相同的帮助 |
| `oh-my-usage start` | 发现服务并刷新用量 |
| `oh-my-usage providers --refresh` | 11 个服务的连接状态与用量 |
| `oh-my-usage history --provider codex` | 用量快照历史（JSON） |
| `oh-my-usage connect openrouter` | 隐藏输入并保存 API 密钥 |
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

新独立安装会启用显示；已有保存的开关保持不变。设置会应用于后续标签页和同账户 SSH 会话；`--session` 只影响当前 shell。

- 新标签页的第一个提示符会立即显示缓存；没有缓存时，读取完成后自动重绘当前行，无需按 Enter。
- 只有输入完全为空时才显示提示，默认淡灰色（颜色编号 `245`）。
- 输入文字、空格、粘贴内容、调出历史命令或多行续行时隐藏；清空输入后恢复。
- 宽度达到 80 列时默认显示在右侧提示符旁；`position left` 可改为左侧提示符之前。更窄时两种位置都显示在输入行上方。过长内容以 `…` 截断。
- 输入过程中，iTerm2 状态栏仍然显示。

设置保存在 `~/.config/oh-my-usage/inline` 这个小文件中，不会修改 `.zshrc`。优先级为：**`--session` → 已保存的选择 → `OH_MY_USAGE_INLINE` → 关闭**。保存的选择也会优先于 v0.4 中添加的 `export OH_MY_USAGE_INLINE=...`。

### 设置菜单：位置、图标、已用/剩余、顺序和颜色

```zsh
oh-my-usage config
```

输入编号并选择值即可立即保存。选择时按 Enter 取消，主菜单输入 `0` 退出。菜单包含终端内显示开关、**used（已用）/ left（剩余）**、**Claude → Codex / Codex → Claude**、自定义服务顺序，以及柔和的颜色预设和 256 色编号。

**选择 `9` 可一次启用“左侧 + 图标 + 剩余百分比”。** 例如每个服务选择一个星标指标时：

```text
✳ 72% | ◇ 58% (left) ~/project >
```

设置菜单和 `config show` 都显示位置、图标、比例、顺序及颜色的预览。预览使用缓存；数据或设置不可用时明确标为 **sample data**。示例提示符不会替换实际 shell 主题，预览也不会请求 API。

图标是 Unicode 字符（`✳` Claude、`◇` Codex），无需图片协议或 Nerd Font 专用字符。如果字体显示异常，可在选项 `8` 改用 ASCII（`CL`、`CX`）。未知服务保留名称；多个指标使用 `S`（Session）和 `W`（Weekly），例如 `◇ S:58%/W:90%`。有额度上限的指标显示百分比，余额和文本保留原单位。

详细设置也在同一菜单中：

| 选项 | 设置 |
| --- | --- |
| `6` | 左侧提示符之前、之后、上方独立一行、右侧或自动 |
| `10` | 服务和单个指标的开启 / 关闭 / 使用来源默认值 |
| `11` | 每个服务的自定义符号或短标签；`none` 隐藏，`auto` 恢复默认 |
| `12` | 提示符间隔 0–8 格、左侧/上方缩进 0–20 格、最大宽度 1–240 格或自动 |
| `13` | 指标标签、used/left 标签及服务之间的分隔符 |

每个编辑器都有预览。可以开启缓存中未加星标的指标，服务也必须开启；显式选择可超过两个指标。全部关闭时隐藏提示，不会把缺失数据显示成 0%。这些选择只影响终端内显示，保留 OpenUsage 和状态栏设置。预设 `9` 保留细项，重置 `5` 清除细项。

```zsh
oh-my-usage config icon claude '✦'
oh-my-usage config icon codex 'C>'
oh-my-usage config provider claude off
oh-my-usage config metric codex.session on
oh-my-usage config metric codex.weekly off
oh-my-usage config position above
oh-my-usage config indent 2
oh-my-usage config gap 2
oh-my-usage config width 48
oh-my-usage config metric-labels off
oh-my-usage config mode-label off
oh-my-usage config separator space
```

自定义图标支持 1–12 个可打印字符，在图标样式下优先于 Unicode/ASCII。图标编辑器会启用图标样式；CLI 可用 `config style icons`。对单个图标、服务或指标设置 `auto` 可恢复默认。编辑器列表不请求 API，`config show` 也会列出已保存的逐项设置。

也可以直接运行：

```zsh
oh-my-usage config mode left
oh-my-usage config order claude,codex
oh-my-usage config color cyan
oh-my-usage config position left
oh-my-usage config style icons
oh-my-usage config icons unicode
```

- `mode used` 显示已用量，`mode left` 显示剩余额度，`mode auto` 使用来源默认值。
- `order claude,codex` 将 Claude 放在 Codex 前面，其余已启用的服务随后显示。不会启用服务或修改星标。`order auto` 恢复来源默认顺序。
- `color` 支持 `gray`、`cyan`、`green`、`blue`、`purple`、`yellow`、`red`、`white` 或 `0`–`255`。保存值优先于 `OH_MY_USAGE_INLINE_COLOR`；`color auto` 恢复环境变量或默认颜色。
- **颜色仅应用于终端内显示。** iTerm2 状态栏颜色请在 Interpolated String 组件设置中修改。已用/剩余和顺序应用于两种显示。
- `position left/after/above/right/auto` 选择位置；`auto` 保留原右侧布局，少于 80 列时均移至输入行上方。保存的 `width` 优先于 `OH_MY_USAGE_INLINE_WIDTH`，并受可用空间限制。
- `style text/icons` 选择完整名称或图标；`icons unicode/ascii` 选择符号或字母缩写。默认值为 `text` 和 `unicode`。这三个选项仅影响终端内显示。
- `config show` 查看设置和预览；`config reset` 重置全部显示设置，保留终端内显示开关。

设置以小文件（`inline`、`mode`、`order`、`color`、`position`、`style`、`icons`、`gap`、`indent`、`width`、`metric-labels`、`mode-label`、`separator` 及 JSON 映射 `icon-map`、`providers`、`metrics`）保存在 `~/.config/oh-my-usage` 或自定义目录中。新标签页、SSH 会话和更新后仍然保留，不修改 OpenUsage 应用设置。其他已打开的标签页在下一个提示符生效。当前 shell 的 `inline --session` 覆盖仍然优先。缓存有效时，更改模式和顺序无需再次请求 API。

### iTerm2 状态栏：仅设置一次

1. 打开 **Settings → Profiles → 当前配置文件 → Session**，启用 **Status bar enabled**。
2. 在 **Configure Status Bar** 中添加 **Interpolated String**。
3. 在 **Configure Component → String Value** 中粘贴：

```text
\(user.oh_my_usage)
```

之后运行 `oh-my-usage start` 即可。现有配置和布局会保留。这里使用 iTerm2 自带组件，而非独立小组件。参考 [iTerm2 官方文档](https://iterm2.com/documentation-status-bar.html)。

### SSH / Termius / iPhone

通过 SSH 连接到已安装并登录客户端的 macOS 或 Linux 账户，使用 zsh 即可。用量在该主机读取；无需 API 端口转发或在手机安装 iTerm2。登录和用量不会自动在主机间复制。

## 更新到 v0.7.0

在克隆的仓库目录中运行：

```zsh
git pull --ff-only
./install.sh
```

打开新标签页，再运行 `oh-my-usage start`。如果首次安装使用了自定义 `--prefix` 或 `--no-shell`，请保留相同选项。

**v0.7.0 更新：** 11 个服务的独立适配器、自动发现连接、Linux 安装、服务级重试和 30 天用量快照。`./install.sh` 选择独立模式；`./install-existing.sh` 保留可选的 OpenUsage 集成。

## 常见问题

先运行 `oh-my-usage doctor`。

| 现象 | 处理方法 |
| --- | --- |
| `command not found` | 安装后打开新的 **zsh** 标签页；使用 `--no-shell` 时需自行加载插件 |
| 状态栏为空 | 检查配置文件及准确的 `\(user.oh_my_usage)` 值，然后运行 `start` |
| 没有终端内提示 | 查看 `inline status`，运行 `inline on` 并清空输入；过长的主题可能占满右侧空间 |
| `[offline]` | 在同一 Mac 账户中运行 `start`；当前显示的是上次成功读取的数据 |
| 服务名称后有 `~` | 数据超过 10 分钟未更新，或时间戳无效 |
| `no connected services` | 用 `providers` 检查状态，然后登录客户端或配置 API 密钥 |
| `no pinned data`（OpenUsage 模式） | 在 OpenUsage 中启用服务并选择指标 |
| `menuBarPins` / 设置错误 | 使用当前版本，在 Customize 中取消再添加星标，重启应用后运行 `refresh` |

缺少 `menuBarPins` 键时使用默认星标；已保存的空列表保持为空。`OH_MY_USAGE_DISPLAY=off` 会关闭两种显示；`start` 会在当前 shell 中重新启用集成。

## 高级选项

<details>
<summary>安装模式、环境变量、脚本和 Oh My Zsh</summary>

默认 `./install.sh` 是 macOS/Linux 独立安装。macOS 上仍可使用 `./install-full.sh`（安装 OpenUsage）或 `./install-existing.sh`（使用已有 OpenUsage）。支持 `--prefix` 和 `--no-shell`；不要使用 sudo 运行安装程序。

按需在加载插件之前设置环境变量：

| 变量 | 默认值 / 用途 |
| --- | --- |
| `OH_MY_USAGE_INLINE` | `off`；仅在没有保存值时作为默认设置 |
| `OH_MY_USAGE_INLINE_COLOR` | `245`；256 色编号，0–255；实际亮度取决于终端调色板 |
| `OH_MY_USAGE_INLINE_WIDTH` | 自动；提示最大宽度，受屏幕空间限制 |
| `OH_MY_USAGE_DISPLAY` | `status`；`off` 关闭两种显示 |
| `OH_MY_USAGE_INTERVAL` | `30`；缓存有效期，单位秒，最小 5 |
| `OH_MY_USAGE_CONFIG_DIR` | `$XDG_CONFIG_HOME/oh-my-usage`，或 `~/.config/oh-my-usage` |
| `OH_MY_USAGE_CACHE_DIR` | macOS: `~/Library/Caches/oh-my-usage`；Linux: `$XDG_CACHE_HOME/oh-my-usage` 或 `~/.cache/oh-my-usage` |
| `OH_MY_USAGE_SOURCE` | `direct` / `openusage`，覆盖保存的来源 |
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

卸载会移除安装文件、带标记的 shell 配置块和显示缓存。用量历史、API 密钥及保存的偏好保留供重新安装；要擦除它们，请删除缓存目录中的 `direct` 和配置目录中的 `credentials.json`。

若要同时清除偏好设置，请删除配置目录中的 `inline`、`mode`、`order`、`color`、`position`、`style`、`icons` 文件。之后会重新使用环境变量或默认值。

</details>

## 轻量设计与开发

收集器使用 Python 和 zsh，Ollama 签名需要 `cryptography`。不启动常驻服务；在提示符边界发现服务，默认每 5 分钟读取一次每个服务的用量。服务失败相互隔离，服务器的限流等待时间会被遵守。原生凭据只读，macOS 钥匙串不会在后台弹出授权窗口。

独立模式完全不使用 OpenUsage 的 API、设置或缓存。成功快照保留 30 天，`history --provider ID --days 7` 输出当前凭据的记录；不是安装之前的费用重建。密钥、账户名称和对话内容不会写入用量缓存。过期登录由原生客户端续期。设置菜单 `14` 选择来源，`15` 查看连接状态。

支持 Antigravity、Claude、Codex、GitHub Copilot、Cursor、Devin、Grok、Ollama、OpenCode、OpenRouter 和 Z.ai。[服务设置、指标和限制](providers.md)列出了详细信息。OpenRouter/Z.ai 需要 API 密钥。部分 API 为非公开接口，可能变化；不复现 OpenUsage 的全部费用估算与 UI。

开发环境安装 `requirements.txt` 后运行 `./scripts/check.sh`；CI 在 macOS/Linux 上验证 11 个服务的响应、自动发现、缓存、重试、历史和真实 zsh 伪终端行为。参照 OpenUsage 格式实现的 MIT 声明随安装提供。

可在 macOS 上使用 `scripts/record_demo.py` 重新生成 README 图片；文件开头列出了可选的开发依赖。录制使用带有示例数据的独立 zsh 会话。图片生成工具和图片文件均不会随程序安装。

[MIT 许可证](../LICENSE)。本项目独立于 OpenUsage、iTerm2 和 Oh My Zsh。
