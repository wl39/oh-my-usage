# oh-my-usage

**[English](../README.md) · [简体中文](README.zh-CN.md) · [한국어](README.ko.md)**

一个轻量级 zsh 集成工具，将 [OpenUsage](https://github.com/robinebers/openusage) 菜单栏中的用量显示到 **iTerm2 状态栏**。也可以开启终端内显示：输入为空时以淡灰色显示，开始输入后立即隐藏。

**Mac + zsh + iTerm2 是兼容性最好的组合。** 当前的数据读取程序和安装程序面向 macOS。其他终端以及手机 SSH 客户端，只要连接到运行 OpenUsage 的同一 Mac 账户，也能使用终端内显示。

```text
状态栏：[CPU] [Memory] [Codex Weekly 74%/Session 58% (left)]
```

以上数字仅为示例，实际内容来自你的 OpenUsage 显示设置和用量数据。

## 为什么轻量

- 仅使用 Python 标准库和 zsh，无需 pip 包或额外插件框架。
- 没有额外的常驻服务或轮询定时器，只在需要刷新时短暂运行 Python。
- 多个标签页共享小型缓存和非阻塞锁，避免重复请求。
- 输入时的显示与隐藏由 zsh 处理，不会每次按键都启动进程。
- OpenUsage 是独立应用，需要保持运行。轻量不代表完全不占内存。

## 环境要求

| 项目 | 要求 |
| --- | --- |
| 运行主机 | macOS 15 或更高版本 |
| Shell | 交互式 zsh；Oh My Zsh 可选 |
| 运行时 | Python 3.9+ |
| 数据来源 | 原生 OpenUsage，已基于 0.7.6 验证 |
| 状态栏 | iTerm2 |
| 终端内显示 | Mac 本地 zsh，或通过 SSH 连接到 Mac 的 zsh |

Windows、Linux 和手机可以作为 SSH 客户端，但不支持在这些设备上直接运行数据读取程序。不支持 Bash、Fish、PowerShell 或旧版 Tauri OpenUsage。

## 1. 安装

克隆仓库，然后选择**一种**安装模式：

```zsh
git clone https://github.com/wl39/oh-my-usage.git
cd oh-my-usage
```

### A. 尚未安装 OpenUsage

```zsh
./install-full.sh
```

如果缺少 OpenUsage，会先通过官方 Homebrew cask 安装，再安装 oh-my-usage。若尚未安装 Homebrew，请先前往 [brew.sh](https://brew.sh) 安装；本脚本不会自动安装 Homebrew。

### B. 已安装 OpenUsage

```zsh
./install-existing.sh
```

直接使用当前 macOS 账户的 OpenUsage 应用和菜单栏设置。两种模式都会在缺少合适的 Python 时通过 Homebrew 安装 Python。各服务的身份验证由 OpenUsage 处理。

默认安装到 `~/.local/share/oh-my-usage`。安装程序会备份 `~/.zshrc`（或 `$ZDOTDIR/.zshrc`），再添加一个带标记的 source 配置块。安装后会打开 OpenUsage。请在应用的 **Customize** 中启用服务，并为需要显示的指标加星标。

打开新标签页，或在当前 zsh 标签页中执行：

```zsh
source ~/.local/share/oh-my-usage/oh-my-usage.plugin.zsh
```

可添加 `--prefix /your/install/path` 自定义安装目录，或添加 `--no-shell` 自行管理插件加载。请勿使用 `sudo` 安装。

## 2. 添加 iTerm2 状态栏组件

1. 打开 **iTerm2 → Settings → Profiles**，选择当前使用的配置文件。
2. 在 **Session** 中启用 **Status bar enabled**，点击 **Configure Status Bar**。
3. 将 **Interpolated String** 拖到已有组件旁边。
4. 打开 **Configure Component**，将 **String Value** 设置为：

```text
\(user.oh_my_usage)
```

使用该配置文件打开新标签页，或执行上面的 source 命令。首次读取完成后，状态栏就会显示数据。

这里使用 iTerm2 自带的组件，无需寻找名为“oh-my-usage”的独立组件。现有配置文件和状态栏布局会保留。可参考 [iTerm2 状态栏文档](https://iterm2.com/documentation-status-bar.html)。

## 3. 可选：仅在输入为空时显示

在已加载插件的 zsh 中，根据需要执行：

```zsh
oh-my-usage inline on       # 在当前 shell 中开启
oh-my-usage inline off      # 在当前 shell 中关闭
oh-my-usage inline status   # 查看当前设置
```

默认**关闭**。开启后：

- 只有整条命令输入完全为空时，才以淡灰色显示用量。
- 输入文字、空格、粘贴内容或调出历史命令都会隐藏显示。清空输入后重新出现。
- 多行命令的续行不显示提示。
- 终端宽度达到 80 列时显示在右侧提示符旁；不足 80 列时显示在输入行上方。过长内容用 `…` 截断。
- 隐藏或关闭后恢复原有主题。iTerm2 状态栏仍然显示。

若希望在新 shell 中自动开启，请在 `.zshrc` 的**插件 source 配置块之前**添加：

```zsh
export OH_MY_USAGE_INLINE=on
export OH_MY_USAGE_INLINE_COLOR=245  # 256 色编号，0–255
# export OH_MY_USAGE_INLINE_WIDTH=30 # 可选：最大显示宽度
```

实际亮度取决于终端调色板。将 `on` 改为 `off` 可在后续 shell 中关闭。`inline on/off` 只修改当前 shell，不会自动编辑 `.zshrc`。

## 4. SSH / Termius / iPhone

通过 SSH 登录到**运行 OpenUsage 的同一 Mac 账户**，启动 zsh 后执行：

```zsh
source ~/.local/share/oh-my-usage/oh-my-usage.plugin.zsh
oh-my-usage inline on
```

数据读取和提示符处理在 Mac 上完成，SSH 客户端负责显示结果。客户端无需安装 iTerm2，也无需开放 API 端口或设置端口转发。连接到其他主机时，原 Mac 的用量不会自动跟随。

若只希望在 SSH 会话中自动开启，请在 `.zshrc` 的 source 配置块之前添加：

```zsh
[[ -n ${SSH_CONNECTION:-} ]] && export OH_MY_USAGE_INLINE=on
```

不要在 Termius 中设置 `TERM_PROGRAM=iTerm.app`。如果曾根据旧说明手动设置，请删除那条赋值，并在该 Termius 会话中运行 `unset TERM_PROGRAM`。终端内显示不依赖此变量。在其他终端或 tmux/screen 内不会发送 iTerm2 专用状态栏控制码，但仍可使用终端内显示。

## 命令与配置

| 命令 | 用途 |
| --- | --- |
| `oh-my-usage show` | 读取用量，优先使用有效缓存 |
| `oh-my-usage refresh` | 强制重新读取，在下一次提示符或 hook 执行时显示 |
| `oh-my-usage cached` | 输出上次缓存的显示内容 |
| `oh-my-usage doctor` | 检查应用、显示设置及本地 API |
| `oh-my-usage --version` | 输出版本 |
| `oh-my-usage-unload` | 移除当前 shell 的 hook，恢复提示符和状态栏变量 |

这些命令通过插件加载的 shell 函数提供。脚本中请使用 `~/.local/share/oh-my-usage/bin/oh-my-usage`。终端内显示控制和卸载 hook 需要使用交互式 shell 函数。

请在加载插件之前设置环境变量：

| 变量 | 默认值 | 含义 |
| --- | --- | --- |
| `OH_MY_USAGE_DISPLAY` | `status` | `status` 启用集成；`off` 关闭两种显示 |
| `OH_MY_USAGE_INLINE` | `off` | `on` 启用空输入时的显示 |
| `OH_MY_USAGE_INLINE_COLOR` | `245` | 淡灰色，256 色编号 |
| `OH_MY_USAGE_INLINE_WIDTH` | 自动 | 最大显示宽度，受屏幕空间限制 |
| `OH_MY_USAGE_INTERVAL` | `30` | 缓存有效期，单位秒，最小 5 |
| `OH_MY_USAGE_CACHE_DIR` | `~/Library/Caches/oh-my-usage` | 共享缓存目录 |
| `OH_MY_USAGE_PYTHON` | 自动检测 | 指定 Python 可执行文件 |
| `OH_MY_USAGE_PREFERENCES` | macOS 偏好设置 | 可选：指定 OpenUsage plist 文件 |
| `OH_MY_USAGE_APP_DIR` | `/Applications` 或 `~/Applications` | 安装时指定包含 OpenUsage.app 的目录 |

程序在**显示新提示符之前**检查是否需要刷新。30 秒是缓存有效期，不是定时器；停留在空闲提示符或运行命令时不会定期读取。通过环境变量首次开启终端内显示时，可能需要在首次读取后按 Enter 或清空输入才会出现。显式运行 `inline on` 时，如果缓存不存在，会等待首次读取完成。

显示会遵循 OpenUsage 的星标、服务和指标顺序、Used/Left 模式以及文字/条形模式。每个服务最多显示两个指标，条形模式总计最多四个指标。没有数据的指标会省略。菜单栏图标、颜色和屏幕共享检测不会复现。

## 使用 Oh My Zsh 插件列表（可选）

普通安装方式已经可以配合 Oh My Zsh 使用。如果希望通过 `plugins=(...)` 管理，请在首次安装时使用 `--no-shell`：

```zsh
./install-existing.sh --no-shell
mkdir -p "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins"
ln -s "$HOME/.local/share/oh-my-usage" \
  "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/oh-my-usage"
```

将 `oh-my-usage` 加入原有插件列表，例如 `plugins=(git oh-my-usage)`。环境变量应放在 Oh My Zsh 的 source 行之前。请选择一种加载方式；`--no-shell` 不会删除先前安装添加的 source 配置块。

## 常见问题

首先运行 `oh-my-usage doctor`。

| 现象 | 检查方法 |
| --- | --- |
| 状态栏为空 | 确认配置文件、状态栏开关、准确的 `\(user.oh_my_usage)` 值及插件加载状态 |
| 终端内不显示 | 在 zsh 中运行 `inline on` 并清空输入；宽屏下过长的主题也可能挤占右侧空间 |
| `[offline]` | 在同一 Mac 账户中打开 OpenUsage；当前显示的是上次成功获取的数据 |
| 服务名称后有 `~` | 数据超过 10 分钟未更新，或时间戳无效 |
| `no pinned data` | 启用服务，并为当前有数据的指标加星标 |
| `menu-bar settings not saved` / `menuBarPins` 错误 | 使用最新版本，在 Customize 中取消并重新添加星标，重启应用后运行 `refresh` |
| `command not found` | source 插件，或使用可执行文件的完整路径 |

若不存在 `menuBarPins` 键，会使用 OpenUsage 的默认星标；若保存的是空列表，则保持为空。程序优先读取 macOS 偏好设置服务，失败时再读取文件。Doctor 不输出凭据或偏好设置的具体值。

## 更新、迁移与卸载

### 更新

在克隆的仓库目录中执行：

```zsh
git pull --ff-only
./install-existing.sh
```

随后打开新 shell。如果首次安装使用了 `--prefix` 或 `--no-shell`，更新时也应使用相同选项。

### 从 OUIterm 迁移

安装更名后的版本之前，在新仓库目录中运行以下命令，移除默认路径下的旧安装：

```zsh
./install.sh uninstall --prefix "$HOME/.local/share/ouiterm"
```

如果旧版使用自定义路径，请指定旧路径；若已卸载则跳过。删除手动添加的 `ouiterm` Oh My Zsh 插件项和符号链接，将 `OUITERM_*` 改为 `OH_MY_USAGE_*`，并将 iTerm2 中的 `\(user.ouiterm)` 改为 `\(user.oh_my_usage)`。随后使用 A/B 模式安装并打开新 shell。旧变量名不会作为别名保留。

### 卸载

```zsh
~/.local/share/oh-my-usage/install.sh uninstall
```

卸载会移除安装文件、带标记的 shell 配置块和本工具的缓存文件。OpenUsage、Python、其他 iTerm2 组件以及 shell 配置备份会保留。关闭旧 shell 或运行 `oh-my-usage-unload`，并删除对应的 Interpolated String 组件。如果使用 Oh My Zsh 插件列表，还需删除插件项及手动创建的符号链接。自定义安装目录请运行该目录中的 `install.sh uninstall`。

## 开发与数据处理

```zsh
./scripts/check.sh
```

检查 shell 语法，并运行 Python 单元测试和真实 zsh 伪终端测试。覆盖渲染、缓存、安装与卸载、状态栏传输、输入隐藏、窗口缩放和模拟 SSH 环境。手机端行为通过终端环境模拟验证，不是自动化 iPhone 界面测试。

| 模块 | 职责 |
| --- | --- |
| `oh_my_usage/settings.py` | OpenUsage 显示偏好设置 |
| `oh_my_usage/source.py` | 本地 API 读取及验证 |
| `oh_my_usage/metrics.py`、`render.py` | 指标映射和纯文本渲染 |
| `oh_my_usage/cache.py` | 共享缓存、原子写入和锁 |
| `oh_my_usage/diagnostics.py`、`__main__.py` | 诊断与 CLI |
| `oh-my-usage.plugin.zsh` | 提示符刷新和 iTerm2 传输 |
| `zsh/inline.zsh` | 根据输入状态控制可选显示 |
| `scripts/install.py` | 安装、shell 备份和卸载 |

读取程序仅请求 `http://127.0.0.1:6736/v1/usage`，不读取服务凭据、钥匙串条目或对话日志。缓存文件仅当前用户可访问。OpenUsage 自身的身份验证和网络活动独立处理。本项目为获取菜单栏指标使用 [legacy UI API](https://github.com/robinebers/openusage/blob/main/docs/local-http-api.md)；上游 API 或设置格式改变时可能需要更新。

个人学习笔记、本地验证记录、生成的预览和本地配置不会提交到 Git。安装程序也只复制运行文件和公开使用说明。

## 许可证

[MIT](../LICENSE)。本项目是独立集成工具，并非 OpenUsage、iTerm2 或 Oh My Zsh 的官方项目。OpenUsage 是独立项目，遵循其自身许可证。
