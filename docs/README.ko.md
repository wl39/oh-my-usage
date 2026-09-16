# oh-my-usage

**[English](../README.md) · [简体中文](README.zh-CN.md) · [한국어](README.ko.md)**

[OpenUsage](https://github.com/robinebers/openusage) 메뉴바의 사용량을 **iTerm2 status bar**에 표시하는 가벼운 zsh 플러그인입니다. 옵션을 켜면 입력이 비어 있을 때 터미널 안에도 옅게 표시하고, 입력하는 즉시 숨깁니다.

**Mac + zsh + iTerm2 환경에서 가장 호환성이 좋습니다.** 현재 데이터 조회와 설치는 macOS를 대상으로 합니다. 다른 터미널이나 휴대폰 SSH 앱에서도 OpenUsage가 실행 중인 Mac의 같은 계정에 접속하면 터미널 내부 표시를 사용할 수 있습니다.

```text
상태바: [CPU] [Memory] [Codex Weekly 74%/Session 58% (left)]
```

숫자는 예시이며, 실제로는 본인의 OpenUsage 표시 설정과 사용량을 읽습니다.

## 가볍게 동작하는 방식

- Python 표준 라이브러리와 zsh만 사용합니다. pip 패키지나 별도 플러그인 프레임워크가 없습니다.
- 추가 상주 서비스나 주기적인 타이머가 없습니다. 갱신할 때만 Python이 잠깐 실행됩니다.
- 탭끼리 작은 캐시와 잠금을 공유해서 중복 조회를 줄입니다.
- 입력에 따른 숨김·표시는 zsh가 처리합니다. 키를 누를 때마다 프로세스를 실행하지 않습니다.
- OpenUsage 앱은 별도로 실행되어 있어야 합니다. 메모리 사용량이 0이라는 의미는 아닙니다.

## 요구 사항

| 항목 | 조건 |
| --- | --- |
| 실행하는 컴퓨터 | macOS 15 이상 |
| 셸 | 대화형 zsh. Oh My Zsh는 선택 사항 |
| 런타임 | Python 3.9 이상 |
| 데이터 | 네이티브 OpenUsage. 0.7.6 기준 검증 |
| 상태바 | iTerm2 |
| 터미널 내부 표시 | 로컬 zsh 또는 Mac으로 SSH 접속한 zsh |

Windows·Linux·휴대폰은 SSH 접속 기기로 사용할 수 있습니다. 이 기기들에서 직접 데이터 조회 프로그램을 실행하는 방식은 지원하지 않습니다. Bash·Fish·PowerShell 및 구 Tauri 버전 OpenUsage도 지원 대상이 아닙니다.

## 1. 설치

저장소를 내려받고 **두 모드 중 하나만** 선택합니다.

```zsh
git clone https://github.com/wl39/oh-my-usage.git
cd oh-my-usage
```

### A. OpenUsage가 없는 기기

```zsh
./install-full.sh
```

OpenUsage가 없으면 공식 Homebrew cask로 설치한 뒤 oh-my-usage를 설치합니다. Homebrew가 없다면 [brew.sh](https://brew.sh)에서 먼저 설치하세요. Homebrew 자체를 자동 설치하지는 않습니다.

### B. OpenUsage가 이미 있는 기기

```zsh
./install-existing.sh
```

현재 계정의 OpenUsage 앱과 메뉴바 표시 설정을 그대로 사용합니다. 두 모드 모두 적합한 Python이 없으면 Homebrew로 설치합니다. 서비스별 인증은 OpenUsage에서 처리합니다.

설치 위치는 `~/.local/share/oh-my-usage`입니다. `~/.zshrc` 또는 `$ZDOTDIR/.zshrc`를 백업한 뒤 표시된 source 블록 하나를 추가합니다. 설치가 끝나면 OpenUsage를 엽니다. 앱의 **Customize**에서 사용할 제공자를 켜고 원하는 지표에 별을 선택하세요.

새 탭을 열거나 현재 zsh 탭에서 실행합니다.

```zsh
source ~/.local/share/oh-my-usage/oh-my-usage.plugin.zsh
```

설치 위치를 바꾸려면 `--prefix /원하는/설치/경로`, 셸 로딩을 직접 관리하려면 `--no-shell`을 설치 명령 뒤에 붙입니다. `sudo`로 설치하지 마세요.

## 2. iTerm2 status bar에 추가

1. **iTerm2 → Settings → Profiles**에서 사용하는 기존 프로필을 선택합니다.
2. **Session → Status bar enabled**를 켜고 **Configure Status Bar**를 누릅니다.
3. **Interpolated String**을 기존 CPU·메모리 등의 항목 옆으로 끌어다 놓습니다.
4. **Configure Component → String Value**에 아래 값을 정확히 입력합니다.

```text
\(user.oh_my_usage)
```

같은 프로필의 새 탭을 열거나 위의 source 명령을 실행합니다. 첫 조회가 끝나면 상태바에 표시됩니다.

iTerm2 기본 컴포넌트를 사용하므로 별도의 “oh-my-usage” 위젯을 찾을 필요가 없습니다. 기존 프로필과 상태바 배치는 유지됩니다. [iTerm2 공식 설정 안내](https://iterm2.com/documentation-status-bar.html)도 참고하세요.

## 3. 선택 사항: 입력이 없을 때만 터미널 안에 표시

플러그인을 불러온 zsh에서 필요한 명령을 실행합니다.

```zsh
oh-my-usage inline on       # 현재 셸에서 켜기
oh-my-usage inline off      # 현재 셸에서 끄기
oh-my-usage inline status   # 현재 설정 확인
```

기본값은 **off**입니다. 켜면 다음처럼 동작합니다.

- 명령 입력이 완전히 비어 있을 때만 옅은 회색으로 표시합니다.
- 문자·공백·붙여넣기·이전 명령 불러오기 모두 표시를 숨깁니다. 입력을 전부 지우면 다시 나타납니다.
- 여러 줄 명령의 이어지는 줄에는 표시하지 않습니다.
- 화면이 80칸 이상이면 오른쪽 프롬프트 옆에, 더 좁으면 입력줄 위에 표시합니다. 긴 내용은 `…`로 줄입니다.
- 숨기거나 끄면 기존 테마가 복원됩니다. iTerm2 상태바 표시는 계속 유지됩니다.

새 셸에서도 켜려면 `.zshrc`의 **플러그인 source 블록 앞**에 추가합니다.

```zsh
export OH_MY_USAGE_INLINE=on
export OH_MY_USAGE_INLINE_COLOR=245  # 256색 번호, 0~255
# export OH_MY_USAGE_INLINE_WIDTH=30 # 선택 사항: 표시 최대 폭
```

실제 밝기는 터미널 팔레트에 따라 다릅니다. 새 셸에서 끄려면 `on`을 `off`로 바꾸세요. `inline on/off` 명령은 현재 셸만 바꾸며 `.zshrc`를 수정하지 않습니다.

## 4. SSH / Termius / 아이폰

OpenUsage가 실행 중인 **Mac의 같은 계정**에 SSH로 접속한 뒤 zsh에서 실행합니다.

```zsh
source ~/.local/share/oh-my-usage/oh-my-usage.plugin.zsh
oh-my-usage inline on
```

데이터 조회와 프롬프트 처리는 Mac에서 하고, SSH 앱은 결과를 화면에 표시합니다. 접속 기기에 iTerm2는 필요하지 않습니다. API 포트 개방·포워딩도 필요 없습니다. 다른 서버에 접속하면 원래 Mac의 사용량이 자동으로 따라오지는 않습니다.

SSH에서만 자동으로 켜려면 `.zshrc`의 source 블록 앞에 추가합니다.

```zsh
[[ -n ${SSH_CONNECTION:-} ]] && export OH_MY_USAGE_INLINE=on
```

Termius에서 `TERM_PROGRAM=iTerm.app`을 설정하지 마세요. 이전 안내에 따라 직접 넣었다면 해당 설정을 지우고, 그 Termius 세션에서 `unset TERM_PROGRAM`을 실행하세요. 내부 표시는 이 변수에 의존하지 않습니다. 다른 터미널 및 tmux/screen 안에서는 iTerm2 전용 상태바 코드를 보내지 않으며, 내부 표시 옵션은 사용할 수 있습니다.

## 명령과 설정

| 명령 | 기능 |
| --- | --- |
| `oh-my-usage show` | 유효한 캐시를 활용해서 사용량 조회 |
| `oh-my-usage refresh` | 즉시 다시 조회. 다음 프롬프트·hook에서 표시 반영 |
| `oh-my-usage cached` | 마지막 표시 문자열 출력 |
| `oh-my-usage doctor` | 앱·표시 설정·로컬 API 진단 |
| `oh-my-usage --version` | 버전 출력 |
| `oh-my-usage-unload` | 현재 셸의 hook 제거, 프롬프트·상태바 변수 복원 |

명령은 플러그인이 불러오는 셸 함수입니다. 스크립트에서는 `~/.local/share/oh-my-usage/bin/oh-my-usage`를 사용하세요. 내부 표시 제어와 unload는 대화형 셸 함수에서만 동작합니다.

아래 환경 변수는 플러그인을 불러오기 전에 설정합니다.

| 변수 | 기본값 | 의미 |
| --- | --- | --- |
| `OH_MY_USAGE_DISPLAY` | `status` | `status`는 연동 사용, `off`는 두 표시 모두 끄기 |
| `OH_MY_USAGE_INLINE` | `off` | `on`이면 빈 입력창 표시 |
| `OH_MY_USAGE_INLINE_COLOR` | `245` | 옅은 회색, 256색 번호 |
| `OH_MY_USAGE_INLINE_WIDTH` | 자동 | 최대 표시 폭. 화면에 맞게 제한 |
| `OH_MY_USAGE_INTERVAL` | `30` | 캐시 유효 시간(초), 최소 5 |
| `OH_MY_USAGE_CACHE_DIR` | `~/Library/Caches/oh-my-usage` | 공유 캐시 폴더 |
| `OH_MY_USAGE_PYTHON` | 자동 감지 | Python 실행 파일 지정 |
| `OH_MY_USAGE_PREFERENCES` | macOS 설정 | OpenUsage plist 파일 직접 지정 |
| `OH_MY_USAGE_APP_DIR` | `/Applications` 또는 `~/Applications` | 설치 시 OpenUsage.app이 있는 폴더 지정 |

갱신 여부는 **새 프롬프트가 나오기 직전**에 확인합니다. 30초는 타이머가 아니라 캐시 유효 시간입니다. 입력 대기 중이거나 명령이 실행 중일 때 주기적으로 조회하지 않습니다. 환경 변수로 내부 표시를 처음 켰다면 첫 조회 후 Enter를 누르거나 입력을 모두 지울 때 나타날 수 있습니다. `inline on`을 직접 실행하면 캐시가 없는 경우 첫 조회를 기다립니다.

OpenUsage의 별 선택, 제공자·지표 순서, Used/Left, 텍스트·막대 모드를 반영합니다. 제공자당 최대 두 지표, 막대 모드는 전체 최대 네 지표를 표시합니다. 데이터가 없는 지표는 생략합니다. 메뉴바 아이콘·색상·화면 공유 감지는 재현하지 않습니다.

## Oh My Zsh 플러그인 목록으로 관리하기

일반 설치만 해도 Oh My Zsh와 함께 사용할 수 있습니다. `plugins=(...)`로 관리하려면 처음 설치할 때 `--no-shell`을 사용합니다.

```zsh
./install-existing.sh --no-shell
mkdir -p "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins"
ln -s "$HOME/.local/share/oh-my-usage" \
  "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/oh-my-usage"
```

기존 목록에 이름을 추가합니다. 예: `plugins=(git oh-my-usage)`. 환경 변수는 Oh My Zsh source 줄 앞에 둡니다. 로딩 방식은 하나만 사용하세요. `--no-shell`은 이전 설치에서 추가된 source 블록을 제거하지 않습니다.

## 문제 해결

먼저 `oh-my-usage doctor`를 실행합니다.

| 증상 | 확인할 내용 |
| --- | --- |
| 상태바가 비어 있음 | 현재 프로필, 상태바 활성화, 정확한 `\(user.oh_my_usage)` 값, 플러그인 로딩 |
| 내부 표시가 안 나옴 | zsh에서 `inline on` 실행 후 입력 전부 지우기. 넓은 화면도 테마가 길면 오른쪽 공간이 부족할 수 있음 |
| `[offline]` | 같은 Mac 계정에서 OpenUsage 실행. 마지막으로 받은 데이터를 표시 중 |
| 제공자 이름 뒤 `~` | 데이터가 10분 넘게 오래됐거나 시간 정보가 유효하지 않음 |
| `no pinned data` | 제공자를 켜고 실제 데이터가 있는 지표에 별 선택 |
| `menu-bar settings not saved` / `menuBarPins` 오류 | 최신 코드 사용, Customize에서 별을 껐다 켜기, 앱 재실행 후 `refresh` |
| `command not found` | 플러그인을 source하거나 실행 파일의 전체 경로 사용 |

`menuBarPins` 키가 없으면 OpenUsage 기본 별을 사용합니다. 저장된 목록이 비어 있으면 빈 상태를 유지합니다. macOS 설정 서비스를 먼저 조회하고 파일 읽기를 대체 수단으로 사용합니다. Doctor는 인증 정보나 설정 값을 출력하지 않습니다.

## 업데이트·이름 전환·제거

### 업데이트

내려받은 저장소 폴더에서 실행합니다.

```zsh
git pull --ff-only
./install-existing.sh
```

새 셸을 여세요. 처음에 `--prefix`나 `--no-shell`을 사용했다면 같은 옵션을 붙입니다.

### OUIterm에서 전환

새 버전을 설치하기 전에, 새 저장소 폴더에서 기본 경로의 구버전을 제거합니다.

```zsh
./install.sh uninstall --prefix "$HOME/.local/share/ouiterm"
```

다른 경로였다면 구버전 경로를 지정하고, 이미 제거했다면 생략하세요. 직접 추가했던 `ouiterm` Oh My Zsh 항목·심볼릭 링크도 제거합니다. `OUITERM_*` 설정을 `OH_MY_USAGE_*`로 바꾸고 iTerm2의 `\(user.ouiterm)`을 `\(user.oh_my_usage)`로 바꿉니다. 이후 A/B 모드로 설치하고 새 셸을 여세요. 옛 변수명은 자동 호환되지 않습니다.

### 제거

```zsh
~/.local/share/oh-my-usage/install.sh uninstall
```

설치 파일·표시된 셸 블록·관리하는 캐시 파일을 제거합니다. OpenUsage·Python·다른 상태바 컴포넌트·셸 설정 백업은 유지합니다. 열린 셸을 닫거나 `oh-my-usage-unload`를 실행하고 Interpolated String 항목을 삭제하세요. Oh My Zsh 목록 방식이었다면 목록 항목과 직접 만든 심볼릭 링크도 제거합니다. 사용자 지정 경로에서는 그 경로의 `install.sh uninstall`을 실행합니다.

## 개발과 데이터 처리

```zsh
./scripts/check.sh
```

셸 문법, Python 단위 테스트, 실제 zsh 가상 터미널 테스트를 실행합니다. 렌더링·캐시·설치와 제거·상태바 전송·입력 숨김·화면 크기 변경·SSH 환경을 검증합니다. 휴대폰 동작은 터미널 환경을 재현해서 검사하며, 실제 아이폰 UI 자동 테스트는 아닙니다.

| 모듈 | 역할 |
| --- | --- |
| `oh_my_usage/settings.py` | OpenUsage 표시 설정 |
| `oh_my_usage/source.py` | 로컬 API 조회와 검증 |
| `oh_my_usage/metrics.py`, `render.py` | 지표 매핑과 문자열 렌더링 |
| `oh_my_usage/cache.py` | 공유 캐시·원자적 저장·잠금 |
| `oh_my_usage/diagnostics.py`, `__main__.py` | 진단과 CLI |
| `oh-my-usage.plugin.zsh` | 프롬프트 갱신과 iTerm2 전송 |
| `zsh/inline.zsh` | 입력 상태에 따른 선택적 표시 |
| `scripts/install.py` | 설치·셸 백업·제거 |

조회기는 `http://127.0.0.1:6736/v1/usage`에만 요청하며, 제공자 인증 정보·키체인·대화 로그를 읽지 않습니다. 캐시는 사용자 전용 권한으로 저장합니다. OpenUsage 자체의 인증과 네트워크 통신은 별개입니다. 메뉴바 지표를 위해 [legacy UI API](https://github.com/robinebers/openusage/blob/main/docs/local-http-api.md)를 사용하므로 상위 프로젝트의 API·설정 변경 시 대응이 필요할 수 있습니다.

개인 학습 노트·로컬 검증 기록·생성된 미리보기·로컬 설정은 Git에서 제외합니다. 설치 시에도 실행 파일과 공개 사용 안내만 복사합니다.

## 라이선스

[MIT](../LICENSE). OpenUsage·iTerm2·Oh My Zsh의 공식 제품이 아닌 독립적인 연동 프로젝트입니다. OpenUsage는 별도 프로젝트이며 자체 라이선스를 따릅니다.
