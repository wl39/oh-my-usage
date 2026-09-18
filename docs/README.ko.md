# oh-my-usage · v0.7.0

**[English](../README.md) · [简体中文](README.zh-CN.md) · [한국어](README.ko.md)**

**11개 AI 서비스의 사용량을 직접 조회**해 zsh 프롬프트와 **iTerm2 상태바**에 표시합니다. 설치·로그인된 클라이언트를 자동으로 찾고, 입력을 시작하면 프롬프트의 사용량 표시를 숨깁니다.

**macOS와 Linux를 지원합니다.** Python 3.9+가 필요하며, 프롬프트 연동에는 zsh를 사용합니다. OpenUsage와 Oh My Zsh는 선택 사항입니다. 설치 시 전용 Python 환경을 만들고 Ollama 서명용 `cryptography`를 설치합니다. CLI는 다른 셸에서도 실행할 수 있습니다.

## 데모

![입력하면 숨겨지고 지우면 다시 나타나는 사용량 표시와 남은 양·순서·색상 설정](assets/inline-demo.gif)

**예시 데이터로 실제 zsh 출력을 녹화해 만든 이미지**입니다. 첫 프롬프트 표시, 입력 중 숨김, 남은 양·순서·색상 저장을 보여줍니다. 데모는 선택 기능인 터미널 내부 표시이며, iTerm2 상태바 설정은 아래에서 안내합니다. [터미널 녹화 원본](assets/inline-demo.cast)은 asciinema가 설치되어 있으면 저장소에서 `asciinema play docs/assets/inline-demo.cast`로 재생할 수 있습니다.

<details>
<summary>설정 메뉴 보기 — oh-my-usage config</summary>

![내부 표시 켜짐, 남은 양, Claude 다음 Codex, 옅은 청록색으로 저장된 설정 메뉴](assets/settings.png)

번호를 선택해 설정을 바꿉니다. 변경 즉시 저장되며 이후 세션에도 적용됩니다.

</details>

## 명령 하나로 설치하고 바로 실행

```zsh
git clone https://github.com/wl39/oh-my-usage.git
cd oh-my-usage
./install.sh
```

`./install.sh` 자체는 **sudo 없이 본인 계정으로 실행**하세요. Linux에서 Python 3.9+·venv/pip·zsh 등 필요한 시스템 패키지가 없으면 설치기가 패키지 관리자로 준비하며, 그때만 sudo 비밀번호를 요청합니다. 전용 Python 환경 생성·복구, 의존성 설치, 명령 등록, 첫 서비스 감지와 사용량 조회까지 이어서 처리합니다. **Linux에서는 OpenUsage를 설치하거나 실행하지 않습니다.** `install-full.sh`·`install-existing.sh`도 Linux에서는 독립 조회로 설치합니다.

대화형 터미널에서는 설치 직후 준비된 zsh로 들어갑니다. 새 탭, `source`, PATH 설정 없이 곧바로 `oh-my-usage`를 실행하고 프롬프트 표시를 사용할 수 있습니다. `oh-my-usage providers`로 11개 서비스의 연결 상태를 확인하세요. 설치·로그인된 클라이언트는 자동 연동하며, API 키가 필요한 서비스는 해당 키를 등록해야 합니다. 기존 표시 설정은 보존합니다. `exit`하면 이전 셸로 돌아가며, 다음 터미널에서도 프롬프트 표시를 쓰려면 zsh를 사용하세요. 기본 로그인 셸은 변경하지 않습니다.

자동화 설치는 `./install.sh --no-start`로 첫 조회와 대화형 셸 진입을 생략할 수 있습니다. `--no-shell`은 프롬프트 연동 없이 CLI만 설치합니다. 어느 셸에서든 `~/.local/bin/oh-my-usage`로 실행할 수 있습니다. 비대화형 실행에서는 새 셸을 열지 않습니다. **`No module named pip`가 발생했던 경우에도 `./install.sh`를 다시 실행하면 복구**하며, 저장한 설정은 유지합니다.

macOS의 누락된 필수 도구는 기존 Homebrew로 설치합니다. OpenUsage는 macOS에서 선택 사항입니다. iTerm2 상태바에는 아래의 컴포넌트 추가가 최초 한 번 필요하며, 터미널 내부 표시는 별도 상태바 설정이 필요 없습니다.

설치 안내와 도움말은 터미널에서 색상으로 구분해 표시합니다. 파일 저장·파이프 출력은 일반 텍스트입니다. 색상을 끄려면 `NO_COLOR=1`을 설정하세요. `TERM=dumb` 환경에서도 색상을 사용하지 않습니다.

## 자주 쓰는 명령

| 명령 | 동작 |
| --- | --- |
| `oh-my-usage` | 도움말 표시. 사용량은 조회하지 않음 |
| `oh-my-usage help` / `oh-my-usage --help` | 같은 도움말 표시 |
| `oh-my-usage start` | 서비스 자동 감지 및 사용량 갱신 |
| `oh-my-usage providers --refresh` | 11개 서비스 연결 상태 확인 및 조회 |
| `oh-my-usage connect openrouter` | API 키를 숨김 입력으로 저장 |
| `oh-my-usage history --provider codex` | 저장된 사용량 이력 출력(JSON) |
| `oh-my-usage config source direct` | 독립 조회 모드 선택 |
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

새 독립 설치에서는 켜짐으로 저장합니다. 기존 저장값은 유지합니다. 한 번 켜면 새 탭과 이후 **같은 계정으로 접속하는 SSH 세션**에도 자동 적용됩니다. 이미 열린 다른 탭은 다음 프롬프트부터 변경값을 반영합니다. `--session`은 현재 셸만 바꾸고 저장값은 유지합니다. 플래그 없이 `inline on/off`를 실행하면 현재 셸의 임시 설정을 해제하고 새 값을 저장합니다.

- 새 탭의 첫 프롬프트에서 바로 표시합니다. 캐시가 없으면 최초 조회가 끝나는 즉시 같은 줄을 갱신하므로 Enter를 누를 필요가 없습니다.
- 입력이 완전히 비어 있을 때만 기본적으로 옅은 회색(`245`)으로 표시합니다.
- 문자·공백·붙여넣기·이전 명령·여러 줄 입력 중에는 숨깁니다. 전부 지우면 다시 표시합니다.
- 화면이 80칸 이상이면 기본적으로 오른쪽 프롬프트 옆에 표시합니다. `position left`로 기존 왼쪽 프롬프트 앞에 붙일 수 있습니다. 더 좁은 화면에서는 어느 모드든 입력줄 위에 표시합니다. 긴 내용은 `…`로 줄입니다.
- 입력 중에도 iTerm2 상태바는 계속 표시됩니다.

설정은 `.zshrc` 대신 `~/.config/oh-my-usage/inline` 파일 하나에 저장합니다. 우선순위는 **`--session` → 저장값 → `OH_MY_USAGE_INLINE` → 꺼짐**입니다. v0.4에서 넣었던 `export OH_MY_USAGE_INLINE=...`보다 새로 저장한 값이 우선합니다.

### 설정 메뉴: 위치, 아이콘, 사용량·남은 양, 순서, 색상

```zsh
oh-my-usage config
```

번호를 고르고 값을 선택하면 바로 저장됩니다. 선택 도중 Enter는 취소, 첫 메뉴에서 `0`은 종료입니다. 내부 표시 켜기/끄기, **used(사용량) / left(남은 양)**, **Claude → Codex / Codex → Claude**, 직접 지정하는 제공자 순서, 옅은 색상 프리셋과 256색 번호를 선택할 수 있습니다.

**`9`번을 선택하면 ‘왼쪽 + 아이콘 + 남은 %’를 한 번에 적용하고 내부 표시를 켭니다.** 제공자마다 지표 하나를 선택한 경우 다음처럼 보입니다.

```text
✳ 72% | ◇ 58% (left) ~/project >
```

설정 화면과 `config show`에서 위치·아이콘·비율·순서·색상의 미리보기를 볼 수 있습니다. 저장된 사용량을 사용하며, 데이터나 설정을 읽을 수 없으면 **sample data**로 표시한 예시를 사용합니다. 프리뷰의 프롬프트는 예시이며 실제 셸 테마는 유지됩니다. 미리보기를 위해 API를 호출하지 않습니다.

아이콘은 `✳`(Claude), `◇`(Codex) 같은 **유니코드 문자 기호**로 표시합니다. 이미지 전송이나 Nerd Font 전용 문자는 사용하지 않습니다. 터미널 폰트에서 기호가 깨지거나 간격이 어긋나면 `8`번에서 **ASCII (`CL`, `CX`)**로 바꾸세요. 등록되지 않은 제공자는 이름을 표시합니다. 지표가 둘이면 `◇ S:58%/W:90%`처럼 세션(`S`)·주간(`W`)을 구분합니다. 한도가 있는 지표는 비율로, 잔액·텍스트 지표는 원래 단위로 표시합니다.

같은 설정 화면에서 세부 항목도 바꿀 수 있습니다.

| 번호 | 설정 |
| --- | --- |
| `6` | 왼쪽 프롬프트 앞·뒤, 별도 윗줄, 오른쪽, 자동 배치 |
| `10` | 제공자별·지표별 켜기 / 끄기 / 소스 기본값 |
| `11` | 제공자별 아이콘·짧은 이름 직접 입력. `none`은 아이콘 숨김, `auto`는 기본값 복원 |
| `12` | 프롬프트 간격 0–8칸, 왼쪽·윗줄 들여쓰기 0–20칸, 최대 너비 1–240칸 또는 자동 |
| `13` | 지표 이름, `(used)`·`(left)` 표시, 제공자 구분자 선택 |

각 편집 화면에서 변경된 미리보기를 확인할 수 있습니다. 캐시에 있는 지표는 별표가 없어도 직접 켤 수 있으며, 제공자도 켜져 있어야 표시합니다. 직접 선택한 지표는 두 개를 넘어도 표시하고, 모두 끄면 내부 힌트를 숨깁니다. 없는 데이터는 0%로 만들지 않습니다. 세부 선택은 내부 표시에만 적용하며 OpenUsage 및 상태바 선택은 유지합니다. `9`번 프리셋은 세부 선택을 유지하고, `5`번 초기화는 세부 선택도 지웁니다.

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

사용자 지정 아이콘은 출력 가능한 문자 1–12자로, 아이콘 스타일에서 Unicode/ASCII보다 우선합니다. 메뉴의 아이콘 편집기는 아이콘 스타일도 켭니다. CLI에서는 `config style icons`를 사용하세요. `config icon codex auto`, `config provider claude auto`, `config metric codex.weekly auto`처럼 항목 하나만 복원할 수도 있습니다. 편집기 목록을 만들기 위해 API를 조회하지 않습니다. `config show`는 저장된 개별 설정도 나열합니다.

명령으로 바로 바꿔도 됩니다.

```zsh
oh-my-usage config mode left
oh-my-usage config order claude,codex
oh-my-usage config color cyan
oh-my-usage config position left
oh-my-usage config style icons
oh-my-usage config icons unicode
```

- `mode used`: 사용량, `mode left`: 남은 양. `mode auto`는 소스 기본값을 따릅니다(독립 모드: 사용량).
- `order claude,codex`: Claude 다음 Codex 순서. 나머지 활성 제공자는 뒤에 이어집니다. 제공자를 켜거나 별 선택을 바꾸지는 않습니다. `order auto`는 소스 기본 순서로 돌아갑니다.
- `color`: `gray`, `cyan`, `green`, `blue`, `purple`, `yellow`, `red`, `white` 또는 `0`~`255`. 저장 색상이 `OH_MY_USAGE_INLINE_COLOR`보다 우선하며, `color auto`로 환경 변수/기본 색상으로 돌아갑니다.
- `position left/after/above/right/auto`: 왼쪽 프롬프트 앞·뒤, 윗줄, 오른쪽, 자동 배치. `auto`는 기존 오른쪽 표시를 유지합니다. 80칸 미만에서는 모두 입력줄 위에 표시합니다. 저장된 `width`는 `OH_MY_USAGE_INLINE_WIDTH`보다 우선하며 화면 공간 이내로 제한합니다.
- `style text/icons`: 전체 이름·아이콘 표시 선택. `icons unicode/ascii`: 문자 기호·영문 약칭 선택. 기본값은 `text`, `unicode`입니다.
- **색상은 터미널 내부 표시에 적용됩니다.** iTerm2 상태바 색상은 Interpolated String 컴포넌트 설정에서 바꿉니다. used/left와 순서는 두 표시 모두에 적용됩니다.
- 위치·스타일·아이콘은 내부 표시에만 적용하며 iTerm2 상태바의 전체 텍스트 표시는 유지됩니다.
- `config show`: 저장값과 미리보기 확인. `config reset`: 표시 설정 전체 초기화. 내부 표시 켜기/끄기는 유지합니다.

`~/.config/oh-my-usage` 또는 지정한 설정 폴더에 작은 파일(`inline`, `mode`, `order`, `color`, `position`, `style`, `icons`, `gap`, `indent`, `width`, `metric-labels`, `mode-label`, `separator` 및 JSON 맵 `icon-map`, `providers`, `metrics`)로 저장합니다. 새 탭·SSH 세션·업데이트 후에도 유지되며 OpenUsage 앱 설정은 바꾸지 않습니다. 다른 열린 탭은 다음 프롬프트부터 반영합니다. `inline --session`으로 지정한 값은 해당 셸에서 계속 우선합니다. 유효한 캐시가 있으면 API 재조회 없이 모드와 순서를 바꿉니다.

### iTerm2 상태바: 최초 한 번 설정

1. **Settings → Profiles → 사용 중인 프로필 → Session**에서 **Status bar enabled**를 켭니다.
2. **Configure Status Bar**에서 **Interpolated String**을 추가합니다.
3. **Configure Component → String Value**에 아래 값을 붙여넣습니다.

```text
\(user.oh_my_usage)
```

이후 `oh-my-usage start`로 실행하면 됩니다. 기존 프로필과 배치는 유지합니다. 별도 위젯이 아닌 iTerm2 기본 컴포넌트를 사용합니다. [iTerm2 공식 안내](https://iterm2.com/documentation-status-bar.html).

### SSH / Termius / iPhone

클라이언트가 설치·로그인된 macOS 또는 Linux 계정으로 SSH 접속해 zsh를 사용하면 됩니다. 사용량은 해당 호스트에서 읽고 휴대폰에는 프롬프트만 표시합니다. API 포트 전달이나 휴대폰의 iTerm2는 필요하지 않습니다. 다른 서버로 로그인·사용량이 자동 복사되지는 않습니다.

## v0.7.0으로 업데이트

내려받은 저장소 폴더에서 실행합니다.

```zsh
git pull --ff-only
./install.sh
```

대화형 터미널에서는 설치기가 첫 조회 후 준비된 zsh로 진입합니다. 처음에 사용자 지정 `--prefix`나 `--no-shell`을 썼다면 같은 옵션을 붙이세요.

**v0.7.0 변경:** 전체 11개 서비스 독립 조회, 자동 감지·연결, Linux 설치, 서비스별 재시도 제어, 30일 사용량 이력을 추가했습니다. 기본 설치는 독립 모드를 선택합니다. 기존 OpenUsage 연동을 유지하려면 `./install-existing.sh`를 사용하세요.

## 자동 연결과 추적 범위

Antigravity, Claude, Codex, GitHub Copilot, Cursor, Devin, Grok, Ollama, OpenCode, OpenRouter, Z.ai를 지원합니다. 각 클라이언트의 로컬 로그인 정보를 사용하며, OpenRouter와 Z.ai 등은 API 키가 필요합니다. [서비스별 인증 경로·지표·제약](providers.md)을 확인하세요.

기본 30초 간격의 프롬프트 갱신에서 전체 서비스의 설치·로그인을 다시 감지합니다. 사용량 API는 서비스별 5분 간격으로 조회하며 새 인증정보는 즉시 반영합니다. `refresh`는 강제 조회하지만 서버가 지정한 호출 제한 대기 시간은 지킵니다. 셸이 대기 중이거나 명령을 실행하는 동안 상주 수집하지 않습니다. 무인 서버에서는 CLI를 원하는 주기로 실행하면 됩니다.

성공한 조회의 수치·단위·초기화 시각을 30일 동안 저장합니다. `history --provider codex --days 7`은 현재 인증정보에 해당하는 기록을 JSON으로 보여줍니다. 설치 이전의 토큰 비용을 복원하는 기능은 아니며 OpenUsage의 모든 비용 추정·UI 기능을 재현하지는 않습니다. 로그인 만료 시 각 클라이언트에서 갱신·재로그인합니다. 캐시에는 인증정보·계정 이름·대화 내용을 넣지 않습니다.

설정 메뉴 `14`에서 소스를, `15`에서 전체 서비스 연결 상태를 확인할 수 있습니다. 표시는 기본적으로 서비스당 두 지표이며 지표 설정에서 더 추가할 수 있습니다.

## 문제 해결

먼저 `oh-my-usage doctor`를 실행하세요.

| 증상 | 해결 방법 |
| --- | --- |
| `command not found` | `zsh` 실행 또는 `~/.local/bin/oh-my-usage` 사용. `--no-shell`은 프롬프트 표시용 플러그인을 따로 불러와야 함 |
| `No module named pip` 설치 오류 | 최신 코드를 받고 `./install.sh` 재실행. 전용 환경을 자동 복구함 |
| 상태바가 비어 있음 | 현재 프로필과 정확한 `\(user.oh_my_usage)` 값 확인 후 `start` |
| 내부 표시가 안 나옴 | `inline status` 확인 후 `inline on`, 입력 전부 지우기. 매우 긴 테마는 오른쪽 공간을 가릴 수 있음 |
| `[offline]` | 같은 Mac 계정에서 `start`. 마지막으로 받은 데이터를 표시 중 |
| 제공자 이름 뒤 `~` | 데이터가 10분 넘게 오래됐거나 시간 정보가 유효하지 않음 |
| `no connected services` | `providers`에서 상태를 보고 클라이언트 로그인 또는 API 키 설정 |
| `no pinned data` (OpenUsage 모드) | OpenUsage에서 제공자와 별을 선택 |
| `menuBarPins` / 설정 오류 | 현재 버전 사용, Customize에서 별을 껐다 켜기, 앱 재실행 후 `refresh` |

`menuBarPins` 키가 없으면 기본 별을 사용하고, 저장된 빈 목록은 그대로 유지합니다. `OH_MY_USAGE_DISPLAY=off`는 두 표시를 모두 끕니다. `start`는 현재 셸에서 연동을 다시 켭니다.

## 고급 설정

<details>
<summary>설치 모드·환경 변수·스크립트·Oh My Zsh</summary>

기본 `./install.sh`는 macOS/Linux 독립 설치입니다. 기존 macOS 전용 두 모드도 유지합니다. `./install-full.sh`는 OpenUsage가 없으면 설치하고, `./install-existing.sh`는 설치된 앱만 사용합니다. 설치 위치는 `~/.local/share/oh-my-usage`입니다. 셸 설정을 백업하고 `~/.zshrc` 또는 `$ZDOTDIR/.zshrc`에 플러그인을 등록합니다. 두 보조 설치 스크립트도 Linux에서는 독립 모드로 설치합니다. 설치 명령 앞에 `sudo`를 붙이지 마세요. 필요한 시스템 패키지 설치에만 설치기가 sudo를 요청합니다. `--prefix /원하는/경로`로 위치를 바꾸거나 `--no-shell`로 셸 로딩을 직접 관리할 수 있습니다.

필요한 환경 변수만 플러그인 로딩 전에 설정합니다.

| 변수 | 기본값 / 역할 |
| --- | --- |
| `OH_MY_USAGE_INLINE` | `off`. 저장값이 없을 때만 사용하는 기본 설정 |
| `OH_MY_USAGE_INLINE_COLOR` | `245`. 256색 번호 0~255. 실제 밝기는 터미널 팔레트에 따라 다름 |
| `OH_MY_USAGE_INLINE_WIDTH` | 자동. 표시 최대 폭, 화면 크기에 맞게 제한 |
| `OH_MY_USAGE_DISPLAY` | `status`. `off`는 두 표시 모두 끄기 |
| `OH_MY_USAGE_INTERVAL` | `30`. 캐시 유효 시간(초), 최소 5 |
| `OH_MY_USAGE_CONFIG_DIR` | `$XDG_CONFIG_HOME/oh-my-usage` 또는 `~/.config/oh-my-usage` |
| `OH_MY_USAGE_CACHE_DIR` | macOS: `~/Library/Caches/oh-my-usage`, Linux: `$XDG_CACHE_HOME/oh-my-usage` 또는 `~/.cache/oh-my-usage` |
| `OH_MY_USAGE_SOURCE` | `direct` / `openusage`. 저장한 소스보다 우선 |
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

설치 파일·표시된 셸 블록·표시 캐시를 제거합니다. 재설치를 위해 `direct` 사용량 이력과 저장한 API 키는 남겨두며, 삭제하려면 캐시의 `direct` 폴더와 설정의 `credentials.json`을 별도로 제거하세요. OpenUsage·Python·다른 상태바 컴포넌트·백업·저장된 설정은 유지합니다. 열린 셸을 닫거나 `oh-my-usage-unload`를 실행하고, Interpolated String 및 직접 추가한 Oh My Zsh 항목·링크를 제거하세요. 사용자 지정 설치는 해당 경로의 `install.sh uninstall`을 사용합니다.

저장값까지 초기화하려면 `oh-my-usage config reset`을 실행하고 설정 폴더의 `inline` 파일을 제거하세요. 이후 환경 변수 또는 기본값이 적용됩니다.

</details>

## 경량 구조와 개발

Python과 zsh를 사용하며 Ollama의 요청 서명에만 `cryptography`가 필요합니다. 탭끼리 캐시와 잠금을 공유하고 키 입력은 zsh 내장 기능으로 처리합니다. 수집은 일회성 프로세스이며 서비스별 오류를 분리합니다. 네이티브 인증 저장소는 읽기만 하고, macOS 키체인은 권한 창을 띄우지 않는 제한 시간 있는 별도 프로세스에서 읽습니다.

`direct` 모드는 OpenUsage의 API·설정·캐시를 사용하지 않습니다. 선택적인 `openusage` 모드는 기존 로컬 API와 표시 설정을 유지합니다. 서비스의 일부 API는 비공개 형식이므로 변경될 수 있습니다. 참조한 OpenUsage 형식 구현의 MIT 고지는 `oh_my_usage/providers/third_party`에 있으며 설치에도 포함됩니다.

개발 환경에 `requirements.txt`를 설치하고 `./scripts/check.sh`로 검증합니다. 11개 응답 형식, 로그인 감지, 서명, 실패·호출 제한, 이력, 실제 zsh 가상 터미널 테스트를 macOS/Linux CI에서 실행합니다. 또한 별도 기본 Ubuntu 22.04/24.04 컨테이너에서 필수 패키지 자동 설치·pip 복구·설치 직후 셸 실행도 검증합니다.

README 이미지는 macOS에서 `scripts/record_demo.py`로 다시 만들 수 있습니다. 필요한 개발용 패키지는 파일 상단에 안내되어 있으며, 예시 데이터를 넣은 독립 zsh 세션을 사용합니다. 이미지 생성 도구와 이미지 파일은 프로그램 설치에서 제외됩니다.

[MIT 라이선스](../LICENSE). OpenUsage·iTerm2·Oh My Zsh의 공식 제품이 아닌 독립 프로젝트입니다.
