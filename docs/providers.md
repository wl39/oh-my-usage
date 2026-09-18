# 독립 수집: 서비스별 연결과 검증 범위

`./install.sh`의 기본값은 `direct`입니다. OpenUsage의 실행 파일, HTTP API, 설정, 캐시를 사용하지 않습니다. 모든 서비스는 같은 레지스트리에서 자동 감지하며, 설치되어 있어도 로그인이 없거나 구독 권한이 없으면 연결 상태로 구분합니다.

```sh
oh-my-usage providers            # 로컬 감지와 마지막 조회 상태; 원격 호출 없음
oh-my-usage providers --refresh  # 감지 및 실제 사용량 조회
oh-my-usage providers --json     # 인증정보를 제외한 상태 JSON
oh-my-usage history --provider codex --days 7
oh-my-usage config source direct
```

| 서비스 | 자동으로 읽는 인증 경로 | 수집 지표 | 추가 조건 |
| --- | --- | --- | --- |
| Antigravity | 실행 중인 language server의 루프백 포트·CSRF; macOS의 네이티브 `gemini` / `antigravity` 키체인 | Gemini·비 Gemini의 5시간/주간 사용률, 리셋 시각 | Linux에서는 클라이언트를 실행. 포트는 lsof 또는 `/proc`에서 감지. 선택적으로 `ANTIGRAVITY_ACCESS_TOKEN` |
| Claude | `CLAUDE_CONFIG_DIR` 또는 `~/.claude/.credentials.json`; macOS Claude Code 키체인과 Claude Desktop의 활성 계정·조직 캐시 | 세션·주간·응답에 있는 모델별 한도, 추가 사용액 | `user:profile` 범위 필요. 키체인이 접근을 거부하면 상태에 표시. `CLAUDE_CODE_OAUTH_TOKEN`도 지원하나 토큰 범위에 따라 조회 불가 |
| Codex | PATH의 `codex`, `CODEX_HOME` 및 CLI가 관리하는 인증 | `account/rateLimits/read`의 모든 한도 버킷과 리셋 시각 | Codex CLI 설치·구독 로그인 필요. primary/secondary 위치가 아니라 실제 기간으로 세션/주간을 구분 |
| GitHub Copilot | `$XDG_CONFIG_HOME/github-copilot/{apps,hosts}.json`, `gh auth token --hostname github.com`, gh `hosts.yml`; `GH_TOKEN` / `GITHUB_TOKEN` | 프리미엄 크레딧·채팅·완성 한도와 초과량 | 공개 GitHub 계정 대상. 조직 결제만 반환하는 경우 권한이 있는 첫 조직의 지표를 **Organization**으로 명시하며 개인 한도로 합산하지 않음 |
| Cursor | macOS `Library/Application Support/Cursor` 또는 Linux `$XDG_CONFIG_HOME/Cursor`의 `state.vscdb`; macOS 네이티브 키체인 | 총 사용량·Auto·API·추가 사용량·크레딧·Grok, 응답에 따라 요청 수/팀 사용액 | Connect API 우선, 대시보드 REST 대체 경로. 금액의 센트/달러를 변환하며 비율과 구분 |
| Devin | `~/.local/share/devin/credentials.toml`, Devin 편집기의 `state.vscdb`; `DEVIN_API_KEY` | 일간·주간 사용률, 추가 잔액 | 네이티브 설정의 HTTPS API 서버 사용 가능 |
| Grok | `GROK_HOME` 또는 `~/.grok/auth.json` | 현재 크레딧 주기의 사용률·리셋, 온디맨드 상한 | 네이티브 CLI가 로그인 갱신. 실제 주기가 주간일 때만 Weekly로 표시 |
| Ollama | `~/.ollama/id_ed25519` | 클라우드 세션·주간 사용률, 최근 4주 사용액 | Ollama 클라우드 로그인과 `cryptography` 필요. 개인키 대신 요청에 대한 Ed25519 서명과 공개키를 전송 |
| OpenCode | `OPENCODE_DATA_DIR` 또는 `$XDG_DATA_HOME/opencode/auth.json`의 `opencode-go`; 해당 디렉터리의 `opencode*.db` | Go 세션·주간·월간 한도, Go/Zen 로컬 오늘·어제·최근 30일 비용 | Go API 키가 없으면 로컬 hosted-provider 사용 기록을 조회. 다른 회사의 BYO 키 비용은 포함하지 않음 |
| OpenRouter | `OPENROUTER_API_KEY` 또는 `oh-my-usage connect openrouter` | 총 크레딧·잔액, 키 한도, 일·주·월 사용액 | CLI 설치 여부와 관계없이 키 필요. 두 엔드포인트 중 하나만 허용되어도 가능한 지표 표시 |
| Z.ai | `ZAI_API_KEY` / `GLM_API_KEY` 또는 `oh-my-usage connect zai` | GLM Coding Plan 세션·주간 등 응답의 기간별 한도, 검색 횟수 | 유효한 키와 Coding Plan 권한 필요 |

Linux 설정 디렉터리는 `$XDG_CONFIG_HOME` 또는 `~/.config`, 데이터 디렉터리는 `$XDG_DATA_HOME` 또는 `~/.local/share`입니다. API 키는 사용 중인 클라이언트나 환경에 이미 있으면 자동으로 읽습니다. 앱이 설치되었다는 이유만으로 새 계정을 만들거나 API 키를 발급하지는 않습니다. 별도의 `.env` 파일이나 다른 도구의 임의 설정 전체를 검색하지 않습니다.

키 전용 연결은 `connect openrouter`, `connect zai`, `connect opencode`, `connect devin`으로 설정할 수 있습니다. 키는 숨김 입력으로 받고 본 도구 설정 디렉터리의 `credentials.json`에 0600으로 저장합니다. 해당 환경변수가 있으면 저장값보다 우선합니다. 삭제는 해당 JSON 항목 또는 환경변수를 제거합니다. `ANTHROPIC_API_KEY`는 Claude 구독 로그인과 다르므로 구독 사용량 API에 보내지 않습니다.

## 감지, 갱신, 기록

새 프롬프트에서 기본 30초 간격으로 로컬 감지를 반복합니다. 이미 연결된 서비스의 원격 조회는 5분 간격이며, 새 인증정보가 발견되면 이전 대기 시간을 넘겨 조회합니다. 서비스별 실패를 분리하며, 429 응답의 `Retry-After`는 강제 갱신에도 적용합니다. 그 외 오류는 지수적으로 대기 시간을 늘립니다.

일시적인 통신 실패는 같은 인증정보의 마지막 정상 값을 `~`와 함께 유지합니다. 로그아웃·계정 변경 또는 명시적인 인증 거절 후에는 이전 값을 현재 값으로 표시하지 않습니다. 키체인을 읽지 못하는 경우에도 오래된 계정 값을 자동 연결된 것처럼 표시하지 않습니다.

현재 구현의 기록 단위는 **인증정보별 조회 스냅샷**입니다. 토큰 교체 시 이전 이력은 별도 묶음으로 남고 기본 `history`에는 새 인증정보의 기록만 나옵니다. 스냅샷은 최대 30일/100,000개이며, 정상 조회 시각·지표 ID·수치·단위·초기화 시각을 저장합니다. 토큰, 원문 API 응답, 계정 이름, 대화 내용은 기록하지 않습니다. OpenCode의 로컬 DB도 필요한 비용 필드만 선택해서 읽습니다.

상주 데몬이나 idle 타이머는 없습니다. 프롬프트를 사용하지 않는 서버에서는 원하는 스케줄러에서 `~/.local/share/oh-my-usage/bin/oh-my-usage show`를 실행할 수 있습니다. 표시를 숨기는 설정은 수집 제외 설정이 아닙니다. 전체 서비스 감지는 계속 수행합니다.

## 인증과 지원 범위

원래 클라이언트의 인증 파일·키체인을 수정하거나 자체적으로 refresh token을 교체하지 않습니다. Codex는 공식 CLI에 인증 관리를 맡기고, 다른 서비스는 클라이언트가 갱신한 자격정보를 다음 감지에서 읽습니다. 만료·권한 부족 상태는 `providers`에서 확인하고 원래 클라이언트에서 로그인합니다.

macOS 키체인 조회는 인증 UI를 금지하고 5초 제한을 둡니다. 자동 연동은 현재 프로세스가 읽을 수 있는 인증정보에 한합니다. 운영체제가 접근을 거부하면 사용자가 Keychain Access의 접근 권한 또는 클라이언트 로그인을 확인해야 합니다. Linux용 Claude Desktop 인증 복호화는 제공하지 않으며 Linux에서는 Claude Code 로그인을 사용합니다.

서비스 11종의 현재 사용량 조회를 구현했습니다. OpenUsage의 모든 화면, 다중 계정 전환 UI, 대화별 토큰 비용 추정, 과거 비용 복원까지 동일하게 구현한 것은 아닙니다. 제공자 응답에 없는 한도/리셋 시각은 만들어 넣지 않습니다. 비공개 API가 변경되거나 계정에 권한이 없으면 `no_usage_data`, `access_denied` 등으로 표시합니다.

## 검증과 출처

2026-09-18 이전 단계에서 실제 계정으로 Antigravity·Claude·Codex의 OpenUsage 없는 조회에 성공했습니다. [당시 검증 이력](standalone-feasibility.md)에 경로와 Claude 키체인 제약을 보존했습니다. 나머지 서비스는 실제 계정 테스트 대신 공개 구현의 요청·응답 계약을 바탕으로 합성 응답과 인증 파일, 서명 검증 테스트를 작성했습니다. 테스트는 네트워크와 실제 인증정보를 사용하지 않습니다.

통합 후 macOS와 Linux(Python 3.9, Docker)에서 각각 140개 테스트를 통과했고 Linux 기본 설치와 11개 서비스 검색도 확인했습니다. 새 수집기로 로컬 Antigravity·Codex 조회에 성공했습니다. Claude는 현재 이 기기에서 `keychain_read_timeout`으로 끝나며, 원인을 잠금이나 권한 문제 중 하나로 확정하지 않았습니다. 이전에 성공한 Claude API 조회와 현재 키체인 자동 접근의 제약을 구분해야 합니다.

주요 출처는 [OpenUsage 제공자 문서와 구현](https://github.com/robinebers/openusage/tree/519431b1345d9d6e2bffc7c12362eb4431a72e9b/docs/providers) (고정 커밋 `519431b1`, 2026-09-17) 및 [Codex App Server 공식 문서](https://learn.chatgpt.com/docs/app-server)입니다. 해당 구현을 참고한 네이티브 형식·프로토콜의 [MIT 고지](../oh_my_usage/providers/third_party/OpenUsage-LICENSE.txt)를 배포물에 포함합니다. 실행 시 OpenUsage 소스나 앱을 다운로드하거나 호출하지 않습니다.
