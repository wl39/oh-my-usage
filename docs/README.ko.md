# oh-my-usage · v0.6.1

**[English](../README.md) · [简体中文](README.zh-CN.md) · [한국어](README.ko.md)**

[OpenUsage](https://github.com/robinebers/openusage) 사용량을 **iTerm2 상태바**에 표시합니다. 옵션을 켜면 입력이 비어 있을 때 터미널 안에도 옅게 표시하고, 입력하면 숨깁니다.

**Mac + zsh + iTerm2 환경에서 가장 호환성이 좋습니다.** macOS 15+, Python 3.9+, 네이티브 OpenUsage가 필요합니다(0.7.6 기준 검증). Oh My Zsh는 선택 사항입니다. 다른 터미널과 휴대폰 SSH 앱에서도 같은 Mac 계정에 접속하면 내부 표시를 사용할 수 있습니다.

## 설치 → 새 탭 → 실행

```zsh
git clone https://github.com/wl39/oh-my-usage.git
cd oh-my-usage
./install.sh
```

OpenUsage가 있으면 그대로 사용하고, 없으면 Homebrew로 설치합니다. Python도 필요할 때 설치합니다. Homebrew가 필요한데 없다면 [brew.sh](https://brew.sh)에서 먼저 설치하세요. OpenUsage의 **Customize**에서 사용할 제공자를 켜고 원하는 지표에 별을 선택합니다.

**설치 후 새 zsh 터미널 탭을 한 번 여세요.** 이후에는 이 명령 하나로 실행합니다.

```zsh
oh-my-usage start
```

OpenUsage를 포커스 이동 없이 열고, 사용량을 조회해 표시를 갱신합니다. 일반 설치에서는 `source`, PATH 설정, `.zshrc` 수동 편집이 필요 없습니다. 이후 새 탭은 연동을 자동으로 불러오며, 앱을 다시 열거나 갱신할 때 `start`를 사용하면 됩니다.

> 설치 프로그램은 별도 프로세스라서 이미 열린 셸에는 명령을 직접 추가할 수 없습니다. 설치 직후 새 탭만 한 번 열어 주세요. iTerm2 상태바는 아래 컴포넌트 추가도 최초 한 번 필요합니다. 터미널 내부 표시에는 상태바 설정이 필요 없습니다.

설치 안내와 도움말은 터미널에서 색상으로 구분해 표시합니다. 파일 저장·파이프 출력은 일반 텍스트입니다. 색상을 끄려면 `NO_COLOR=1`을 설정하세요. `TERM=dumb` 환경에서도 색상을 사용하지 않습니다.

## 자주 쓰는 명령

| 명령 | 동작 |
| --- | --- |
| `oh-my-usage` | 도움말 표시. 사용량은 조회하지 않음 |
| `oh-my-usage help` / `oh-my-usage --help` | 같은 도움말 표시 |
| `oh-my-usage start` | OpenUsage 실행 및 표시 갱신 |
| `oh-my-usage inline on` | 내부 표시 켜기. **현재·다음 세션 모두 유지** |
| `oh-my-usage inline off` | 내부 표시 끄기. **현재·다음 세션 모두 유지** |
| `oh-my-usage inline on --session` | 현재 셸에서만 켜기 |
| `oh-my-usage inline off --session` | 현재 셸에서만 끄기 |
| `oh-my-usage inline status` | 실제 적용된 값과 설정 출처 확인 |
| `oh-my-usage config` | 설정 메뉴 열기 |
| `oh-my-usage doctor` | 앱·설정·API 연결 진단 |

필요한 명령 하나만 실행하세요. `on`과 `off`는 선택지입니다. 내부 표시 명령의 도움말은 `oh-my-usage inline --help`로 봅니다.

### 내부 표시: 한 번 켜면 다음에도 유지

```zsh
oh-my-usage inline on
```

기본값은 꺼짐입니다. 한 번 켜면 새 탭과 이후 **같은 계정으로 접속하는 SSH 세션**에도 자동 적용됩니다. 이미 열린 다른 탭은 다음 프롬프트부터 변경값을 반영합니다. `--session`은 현재 셸만 바꾸고 저장값은 유지합니다. 플래그 없이 `inline on/off`를 실행하면 현재 셸의 임시 설정을 해제하고 새 값을 저장합니다.

- 새 탭의 첫 프롬프트에서 바로 표시합니다. 캐시가 없으면 최초 조회가 끝나는 즉시 같은 줄을 갱신하므로 Enter를 누를 필요가 없습니다.
- 입력이 완전히 비어 있을 때만 기본적으로 옅은 회색(`245`)으로 표시합니다.
- 문자·공백·붙여넣기·이전 명령·여러 줄 입력 중에는 숨깁니다. 전부 지우면 다시 표시합니다.
- 화면이 80칸 이상이면 오른쪽 프롬프트 옆, 더 좁으면 입력줄 위에 표시합니다. 긴 내용은 `…`로 줄입니다.
- 입력 중에도 iTerm2 상태바는 계속 표시됩니다.

설정은 `.zshrc` 대신 `~/.config/oh-my-usage/inline` 파일 하나에 저장합니다. 우선순위는 **`--session` → 저장값 → `OH_MY_USAGE_INLINE` → 꺼짐**입니다. v0.4에서 넣었던 `export OH_MY_USAGE_INLINE=...`보다 새로 저장한 값이 우선합니다.

### 설정 메뉴: 사용량·남은 양, 순서, 색상

```zsh
oh-my-usage config
```

번호를 고르고 값을 선택하면 바로 저장됩니다. 선택 도중 Enter는 취소, 첫 메뉴에서 `0`은 종료입니다. 내부 표시 켜기/끄기, **used(사용량) / left(남은 양)**, **Claude → Codex / Codex → Claude**, 직접 지정하는 제공자 순서, 옅은 색상 프리셋과 256색 번호를 선택할 수 있습니다.

명령으로 바로 바꿔도 됩니다.

```zsh
oh-my-usage config mode left
oh-my-usage config order claude,codex
oh-my-usage config color cyan
```

- `mode used`: 사용량, `mode left`: 남은 양. `mode auto`는 OpenUsage 설정을 따릅니다.
- `order claude,codex`: Claude 다음 Codex 순서. 나머지 활성 제공자는 뒤에 이어집니다. 제공자를 켜거나 별 선택을 바꾸지는 않습니다. `order auto`는 OpenUsage 순서로 돌아갑니다.
- `color`: `gray`, `cyan`, `green`, `blue`, `purple`, `yellow`, `red`, `white` 또는 `0`~`255`. 저장 색상이 `OH_MY_USAGE_INLINE_COLOR`보다 우선하며, `color auto`로 환경 변수/기본 색상으로 돌아갑니다.
- **색상은 터미널 내부 표시에 적용됩니다.** iTerm2 상태바 색상은 Interpolated String 컴포넌트 설정에서 바꿉니다. used/left와 순서는 두 표시 모두에 적용됩니다.
- `config show`: 저장값 확인. `config reset`: 사용량 모드·순서·색상 초기화. 내부 표시 켜기/끄기는 유지합니다.

`~/.config/oh-my-usage` 또는 지정한 설정 폴더에 작은 파일(`inline`, `mode`, `order`, `color`)로 저장합니다. 새 탭·SSH 세션·업데이트 후에도 유지되며 OpenUsage 앱 설정은 바꾸지 않습니다. 다른 열린 탭은 다음 프롬프트부터 반영합니다. `inline --session`으로 지정한 값은 해당 셸에서 계속 우선합니다. 유효한 캐시가 있으면 API 재조회 없이 모드와 순서를 바꿉니다.

### iTerm2 상태바: 최초 한 번 설정

1. **Settings → Profiles → 사용 중인 프로필 → Session**에서 **Status bar enabled**를 켭니다.
2. **Configure Status Bar**에서 **Interpolated String**을 추가합니다.
3. **Configure Component → String Value**에 아래 값을 붙여넣습니다.

```text
\(user.oh_my_usage)
```

이후 `oh-my-usage start`로 실행하면 됩니다. 기존 프로필과 배치는 유지합니다. 별도 위젯이 아닌 iTerm2 기본 컴포넌트를 사용합니다. [iTerm2 공식 안내](https://iterm2.com/documentation-status-bar.html).

### SSH / Termius / 아이폰

OpenUsage가 실행 중인 같은 Mac 계정에 SSH로 접속한 뒤, zsh에서 `oh-my-usage inline on`을 한 번 실행합니다. 다음 접속부터 기억합니다. OpenUsage가 꺼져 있다면 `oh-my-usage start`로 Mac에서 엽니다.

데이터는 Mac이 읽고, 접속한 기기는 화면을 표시합니다. 아이폰에 iTerm2를 설치하거나 API 포트를 열거나 `TERM_PROGRAM`을 꾸밀 필요가 없습니다. 이전에 Termius에서 `TERM_PROGRAM=iTerm.app`을 강제로 설정했다면 해당 줄을 지우세요. 다른 서버에 원래 Mac의 사용량이 자동 전달되지는 않습니다. Windows·Linux·휴대폰은 SSH 클라이언트로 사용할 수 있지만 데이터 조회 호스트는 지원하지 않습니다. Bash·Fish·PowerShell 및 구 Tauri OpenUsage도 지원하지 않습니다.

## v0.6.1으로 업데이트

내려받은 저장소 폴더에서 실행합니다.

```zsh
git pull --ff-only
./install.sh
```

새 탭을 열고 `oh-my-usage start`를 실행합니다. 처음에 사용자 지정 `--prefix`나 `--no-shell`을 썼다면 같은 옵션을 붙이세요.

**v0.6.1 변경:** agnoster처럼 오른쪽 프롬프트를 미리 만들지 않는 테마와, 입력 편집기가 아직 불러와지지 않은 새 셸의 첫 표시 문제를 수정했습니다. 빠른 시작 테마가 터미널 출력을 복원한 뒤에도 표시를 적용합니다. Enter·시작 지연·상주 프로세스는 필요 없습니다. v0.6의 저장형 설정 메뉴는 그대로 사용할 수 있습니다.

## 문제 해결

먼저 `oh-my-usage doctor`를 실행하세요.

| 증상 | 해결 방법 |
| --- | --- |
| `command not found` | 설치 후 새 **zsh** 탭 열기. `--no-shell`로 직접 관리한다면 플러그인을 따로 불러와야 함 |
| 상태바가 비어 있음 | 현재 프로필과 정확한 `\(user.oh_my_usage)` 값 확인 후 `start` |
| 내부 표시가 안 나옴 | `inline status` 확인 후 `inline on`, 입력 전부 지우기. 매우 긴 테마는 오른쪽 공간을 가릴 수 있음 |
| `[offline]` | 같은 Mac 계정에서 `start`. 마지막으로 받은 데이터를 표시 중 |
| 제공자 이름 뒤 `~` | 데이터가 10분 넘게 오래됐거나 시간 정보가 유효하지 않음 |
| `no pinned data` | OpenUsage에서 제공자를 켜고 데이터가 있는 지표에 별 선택 |
| `menuBarPins` / 설정 오류 | 현재 버전 사용, Customize에서 별을 껐다 켜기, 앱 재실행 후 `refresh` |

`menuBarPins` 키가 없으면 기본 별을 사용하고, 저장된 빈 목록은 그대로 유지합니다. `OH_MY_USAGE_DISPLAY=off`는 두 표시를 모두 끕니다. `start`는 현재 셸에서 연동을 다시 켭니다.

## 고급 설정

<details>
<summary>설치 모드·환경 변수·스크립트·Oh My Zsh</summary>

기존 두 모드도 유지합니다. `./install-full.sh`는 OpenUsage가 없으면 설치하고, `./install-existing.sh`는 설치된 앱만 사용합니다. 설치 위치는 `~/.local/share/oh-my-usage`입니다. 셸 설정을 백업하고 `~/.zshrc` 또는 `$ZDOTDIR/.zshrc`에 플러그인을 등록합니다. `sudo`는 사용하지 마세요. `--prefix /원하는/경로`로 위치를 바꾸거나 `--no-shell`로 셸 로딩을 직접 관리할 수 있습니다.

필요한 환경 변수만 플러그인 로딩 전에 설정합니다.

| 변수 | 기본값 / 역할 |
| --- | --- |
| `OH_MY_USAGE_INLINE` | `off`. 저장값이 없을 때만 사용하는 기본 설정 |
| `OH_MY_USAGE_INLINE_COLOR` | `245`. 256색 번호 0~255. 실제 밝기는 터미널 팔레트에 따라 다름 |
| `OH_MY_USAGE_INLINE_WIDTH` | 자동. 표시 최대 폭, 화면 크기에 맞게 제한 |
| `OH_MY_USAGE_DISPLAY` | `status`. `off`는 두 표시 모두 끄기 |
| `OH_MY_USAGE_INTERVAL` | `30`. 캐시 유효 시간(초), 최소 5 |
| `OH_MY_USAGE_CONFIG_DIR` | `$XDG_CONFIG_HOME/oh-my-usage` 또는 `~/.config/oh-my-usage` |
| `OH_MY_USAGE_CACHE_DIR` | `~/Library/Caches/oh-my-usage` |
| `OH_MY_USAGE_PYTHON` | 자동 감지. Python 실행 파일 지정 |
| `OH_MY_USAGE_PREFERENCES` | OpenUsage plist 파일 직접 지정 |
| `OH_MY_USAGE_APP_DIR` | OpenUsage.app이 있는 폴더. 설치와 `start`에서 사용 |

경로는 절대 경로나 `$HOME`으로 지정하세요. 설정 폴더를 바꿨다면 새 탭을 엽니다.

`show`는 캐시를 활용한 사용량 출력, `refresh`는 강제 갱신, `cached`는 마지막 표시 출력, `--version`은 버전 확인입니다. `oh-my-usage-unload`는 현재 셸의 hook을 제거합니다. 스크립트에서는 `~/.local/share/oh-my-usage/bin/oh-my-usage`를 사용합니다. 이 실행 파일로도 `inline on/off`를 저장할 수 있지만, `--session`은 플러그인이 불러온 대화형 zsh 함수에서만 동작합니다.

일반 source 블록 대신 Oh My Zsh 목록으로 관리하려면 최초 설치에 `--no-shell`을 붙인 뒤 실행합니다.

```zsh
mkdir -p "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins"
ln -s "$HOME/.local/share/oh-my-usage" \
  "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/oh-my-usage"
```

기존 `plugins=(...)`에 `oh-my-usage`를 추가합니다. 환경 변수는 Oh My Zsh source 줄 앞에 둡니다. 로딩 방식은 하나만 사용하세요. `--no-shell`은 이전 설치의 source 블록을 제거하지 않습니다.

</details>

<details>
<summary>구 OUIterm 전환·제거</summary>

구 OUIterm이 남아 있다면 새 저장소에서 `./install.sh uninstall --prefix "$HOME/.local/share/ouiterm"`으로 제거합니다. 사용자 지정 경로였다면 옛 경로를 지정하세요. 직접 추가했던 `ouiterm` 플러그인 항목·심볼릭 링크를 제거하고, `OUITERM_*`를 `OH_MY_USAGE_*`로, `\(user.ouiterm)`을 `\(user.oh_my_usage)`로 바꿉니다. 이후 설치하고 새 탭을 엽니다.

제거 명령:

```zsh
~/.local/share/oh-my-usage/install.sh uninstall
```

설치 파일·표시된 셸 블록·관리 대상 캐시를 제거합니다. OpenUsage·Python·다른 상태바 컴포넌트·백업·저장된 설정은 유지합니다. 열린 셸을 닫거나 `oh-my-usage-unload`를 실행하고, Interpolated String 및 직접 추가한 Oh My Zsh 항목·링크를 제거하세요. 사용자 지정 설치는 해당 경로의 `install.sh uninstall`을 사용합니다.

저장값까지 초기화하려면 설정 폴더의 `inline`, `mode`, `order`, `color` 파일을 제거하세요. 이후 환경 변수 또는 기본값이 적용됩니다.

</details>

## 경량 구조와 개발

Python 표준 라이브러리와 zsh만 사용합니다. pip 의존성·추가 상주 프로세스·주기적인 타이머가 없습니다. 탭끼리 캐시와 잠금을 공유합니다. 갱신 여부는 새 프롬프트 직전에 확인하며, 대기 중이거나 명령이 실행 중일 때 계속 조회하지 않습니다. 키 입력 처리는 zsh 내장 기능으로 처리하고 저장 설정은 프롬프트 시점에 읽습니다. 조회가 끝나면 일회성 파이프로 ZLE에 알려 첫 입력 줄을 다시 그린 뒤 파이프를 닫습니다. OpenUsage 앱 자체는 별도로 실행되어야 합니다.

조회기는 `http://127.0.0.1:6736/v1/usage`에만 요청하며 인증 정보·키체인·대화 로그를 읽지 않습니다. 캐시·설정 파일은 사용자 전용 권한으로 저장합니다. 별 선택·텍스트/막대 모드를 반영하며, 순서·Used/Left는 `config`에 저장한 값이 없으면 OpenUsage를 따릅니다. 제공자당 최대 두 지표, 막대는 전체 최대 네 지표입니다. 메뉴바 아이콘·색상·화면 공유 감지는 재현하지 않습니다. [legacy UI API](https://github.com/robinebers/openusage/blob/main/docs/local-http-api.md)와 상위 설정 형식은 바뀔 수 있습니다.

`./scripts/check.sh`로 문법·단위 테스트와 실제 zsh 가상 터미널 테스트를 실행합니다. 세션 간 설정 유지도 검증합니다. 휴대폰 동작은 터미널 환경 재현이며 실제 아이폰 UI 자동 테스트는 아닙니다. 설정(`config.py`, `zsh/config.zsh`), 앱 시작(`start.py`), 데이터·표시 설정·렌더링·캐시, CLI, 셸 전송, 내부 표시를 모듈로 분리했습니다. 개인 노트·미리보기는 Git과 설치에서 제외합니다.

[MIT 라이선스](../LICENSE). OpenUsage·iTerm2·Oh My Zsh의 공식 제품이 아닌 독립 프로젝트입니다.
