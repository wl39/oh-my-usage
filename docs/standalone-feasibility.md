# OpenUsage 독립 조회 검증

검증일: 2026-09-18. macOS의 실제 로그인으로 Antigravity, Claude, Codex의 사용량을 조회했다.
세 제공자 모두 OpenUsage의 HTTP API, CLI, 설정, 캐시를 사용하지 않고 조회에 성공했다.
이 문서는 제품 통합 이전의 개발용 검증 이력이다. 현재 제품에는 독립 수집과 Linux 설치를 통합했으며, [서비스별 연결 안내](providers.md)를 참고한다. 아래 스크립트는 당시 검증용 도구로 보존한다.

## 재실행

저장소 루트에서 Python 3.9 이상으로 실행한다.

```sh
python3 scripts/probe_direct_usage.py --claude-desktop

# 제공자 하나만 조회
python3 scripts/probe_direct_usage.py --provider codex
python3 scripts/probe_direct_usage.py --provider antigravity
python3 scripts/probe_direct_usage.py --provider claude --claude-desktop

# 실제 수치는 Git에서 제외된 개인 기록에 저장
python3 scripts/probe_direct_usage.py --claude-desktop \
  --output docs/private/direct-usage-latest.json

# 인증정보나 네트워크를 사용하지 않는 검증
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_direct_probe.py -v
```

모든 제공자에서 지표를 받으면 종료 코드 0, 인증/통신 실패나 지표 부재가 있으면 1이다.
실패한 제공자가 있어도 다른 제공자의 결과는 출력한다. 개별 결과의 `checked_at`을 확인한다.
출력 파일은 0600 권한으로 저장한다. 이번 실측 파일은 `docs/private/direct-usage-2026-09-18.json`이다.
실측 수치는 이후 사용에 따라 달라지므로 공개 문서에 고정하지 않는다.
이번 날짜별 기록은 성공 실행에서 관찰한 값과 후속 재조회 결과를 함께 보관한 검증 이력이다.

## 실제 검증한 경로

| 제공자 | 조회 방법 | 확인한 데이터 | 조건과 관찰 |
| --- | --- | --- | --- |
| Codex | `codex app-server`의 `account/rateLimits/read` | 주간 사용률, 다음 초기화 시각 | CLI 0.154.0. 응답의 primary가 7일 창이었다. 5시간 창은 반환되지 않아 만들지 않았다. |
| Claude | Anthropic `/api/oauth/usage` | 5시간·주간 사용률과 초기화 시각, 추가 지표 | CLI 2.1.185의 키체인 토큰은 만료되고 refresh token도 없어 직접 요청이 HTTP 401. Claude Desktop의 유효한 접근 토큰으로 HTTP 200을 받았다. |
| Antigravity | 앱 자체 language server의 `RetrieveUserQuotaSummary` | Gemini 및 비 Gemini 풀의 5시간·주간 지표 네 개 | 앱 2.12.2 실행 중. `--https_server_port=0`이므로 실제 리스닝 포트를 찾아야 했다. |

Codex는 공식 JSON-RPC 인터페이스를 사용한다. 핸드셰이크 이후 계정 한도만 읽으며,
작업 생성이나 모델 추론 요청은 하지 않는다. 인증 관리는 설치된 Codex CLI에 맡긴다.
다중 한도 버킷을 지원하고, 세션/주간 여부는 primary/secondary 위치 대신 기간으로 구분한다.

Claude는 기본 CLI 키체인 또는 `.credentials.json`을 먼저 확인한다. `--claude-desktop`을
명시하면 유효한 CLI 토큰이 없을 때 macOS Desktop의 암호화된 로그인 캐시를 읽는다.
현재 활성 계정·조직, 토큰 범위, 만료 시각을 확인하고 V2 삭제 표시도 존중한다.
Desktop의 refresh token은 사용하지 않고 로그인 파일이나 키체인도 수정하지 않는다.
키체인 접근이 허용되지 않았으면 macOS가 접근 확인을 표시할 수 있다.
CLI의 유효한 토큰이 서버에서 거절된 경우 Desktop 재시도까지는 구현하지 않은 검증 도구다.
Desktop 로그인으로 두 차례 조회에 성공한 뒤 후속 재조회에서는 키체인 읽기가 20초 후
타임아웃 됐다. 이 실패를 보존했고, 스크립트는 이제 `keychain_read_timeout`으로 구분한다.
조회 가능성은 확인했지만, 키체인 잠금/접근 UI 등 정확한 지연 원인은 확정하지 않았다.
주기적인 무인 갱신에는 사용자 상호작용 없는 키체인 접근과 명확한 재인증 상태 처리가 필요하다.

Antigravity는 실행 중인 프로세스에서 CSRF 값과 실제 포트를 알아낸 뒤 해당 프로세스의
루프백 서버만 조회한다. 자체 서명 인증서 허용은 `127.0.0.1`에만 적용한다.
외부 Anthropic 요청은 정상 TLS 검증을 수행하며 리디렉션은 따라가지 않는다.
앱 종료 상태의 Google OAuth 대체 경로는 이번에 구현하거나 검증하지 않았다.

인증값, 이메일, 계정/조직 ID, 응답 원문, 대화 내용은 결과에 포함하지 않는다.
스크립트 자체는 토큰을 갱신하거나 저장하지 않지만 Codex CLI는 자체 인증을 관리한다.
OpenUsage 앱을 종료하지는 않았다. 독립성은 스크립트의 호출 경로와 새로 받은 응답으로
확인했으며, OpenUsage 프로세스·API·파일은 호출하거나 읽지 않았다.

## 전체 제공자 지원 범위

확인한 OpenUsage의 현재 제공자는 총 11개다. 아래 나머지 8개는 상위 구현/문서를 조사한
상태이며 실계정으로 검증하지 않았다. 설치·구독·권한이 없는 제공자의 값은 자동으로 얻을 수 없다.
표의 Linux 열은 필요한 구현 경로이며, Linux 실기 검증을 마쳤다는 뜻이 아니다.

| 제공자 | 독립 수집에 필요한 인증·데이터 소스 | Linux에서 필요한 작업 | 검증 상태 |
| --- | --- | --- | --- |
| Antigravity | 자체 language server RPC. 앱 종료 시 Google OAuth 및 Cloud Code API | Linux 프로세스·포트 탐색, 앱/agy 로그인 저장소 및 headless 경로 확인 | macOS 실행 중 실측 성공 |
| Claude | CLI OAuth 로그인 및 usage API. macOS에서는 Desktop 토큰도 대체 가능 | 유효한 Claude Code 로그인 사용, 만료 처리. 이번 Desktop 대체 경로는 macOS 전용 | macOS Desktop 로그인으로 실측 성공 |
| Codex | 공식 CLI app-server의 계정 한도 조회 | Linux Codex CLI로 같은 JSON-RPC 호출 검증 | macOS 실측 성공 |
| Copilot | 편집기 로그인 파일 또는 GitHub CLI 인증, Copilot usage API | `gh`/파일 인증 어댑터. 조직별 권한 차이와 미제공 개인 지표 처리 | 구현 경로 조사 |
| Cursor | 앱의 SQLite 상태·인증, dashboard RPC 및 REST, 사용 내역 export | Linux 앱 데이터 경로·키링·토큰 갱신 처리 | 구현 경로 조사 |
| Devin | CLI `credentials.toml` 또는 앱 인증, `GetUserStatus` RPC | CLI 로그인 파일 경로 및 요청 서버 검증 | 구현 경로 조사 |
| Grok | CLI `auth.json`, billing API, 로컬 세션 내역 | OAuth 갱신·동시 쓰기 처리 및 세션 파서 | 구현 경로 조사 |
| Ollama Cloud | 로컬 Ed25519 서명 키, 클라우드 usage API | 서명 구현과 계정 연결 확인. 로컬 모델 사용량과 구분 | 구현 경로 조사 |
| OpenCode | Go API 키 및 usage API, Go/Zen 로컬 SQLite 내역 | XDG 데이터 경로와 여러 DB 처리 | 구현 경로 조사 |
| OpenRouter | 사용자 API 키, credits/key API | 환경 변수 또는 oh-my-usage 자체 키 저장소 | 구현 경로 조사 |
| Z.ai | 사용자 API 키, subscription/quota API | 환경 변수 또는 oh-my-usage 자체 키 저장소 | 구현 경로 조사 |

OpenRouter·Z.ai 키는 독립 모드에서 OpenUsage 설정을 읽는 방식으로 구현하면 안 된다.
사용자가 직접 지정한 환경 변수나 oh-my-usage가 관리하는 저장소를 사용한다.
Copilot 조직 지표처럼 원본 API가 제공하지 않는 개인 한도는 조회 도구만 바꿔도 얻어지지 않는다.

모든 제공자를 지원하는 것과 모든 지표를 동일하게 제공하는 것은 각각 검증해야 한다.
현재 스크립트는 세 제공자의 **실시간 한도**를 증명했다. 전체 지표 동등성을 위해서는
비용·잔액·모델별 한도·로컬 사용 내역·다중 계정도 제공자별로 구현해야 한다.
특히 로컬 로그의 토큰/추정 비용은 구독의 계정 전체 한도를 대체하지 않는다.

## 제품으로 옮길 구조

1. 제공자별 수집 모듈과 OS별 인증 접근 모듈을 분리한다. OpenUsage도 선택 가능한 수집 모듈로 유지한다.
2. 공통 데이터에 제공자·계정 식별자, 고정 metric ID, 단위, 값/한도, 기간, 초기화 시각,
   조회 시각, 데이터 출처와 오류 상태를 둔다. 계정 식별자는 캐시 분리에 쓰고 로그에 노출하지 않는다.
3. 실시간 한도/잔액과 로컬 비용 내역을 별도 수집한다. 권한 부족·미제공·조회 실패를 0으로 바꾸지 않는다.
4. 표시 설정의 기준을 oh-my-usage 자체 설정으로 옮긴다. OpenUsage plist 읽기는 연동 모드에만 남긴다.
5. 제공자·계정별 캐시와 재시도 대기 시간을 둔다. 현재 로컬 API용 30초 주기를 외부 API에 그대로
   적용하지 않는다. 로그인 변경 시 이전 계정 캐시를 재사용하지 않는다.
6. Linux용 설치·XDG 경로·zsh 표시를 검증한다. macOS 전용 키체인 코드는 공통 수집 코드와 분리한다.
7. 전체 11개 제공자에 같은 계약 테스트를 적용하고, 실제 로그인 가능한 환경에서 순서대로 검증한다.

현재 Python 기반 구조로 시작할 수 있다. 다만 Ed25519 서명, OS 키링, 복잡한 protobuf 처리까지
포함하면 선택적 라이브러리나 설치된 공식 CLI 사용이 필요할 수 있다. 기존의 '표준 라이브러리만'
방침을 모든 제공자의 독립 수집에 강제로 적용하지 않는 편이 현실적이다.

## 근거

- [Codex 공식 app-server 문서](https://developers.openai.com/codex/app-server#auth-endpoints)
- [OpenUsage 제공자 문서 목록](https://github.com/robinebers/openusage/tree/519431b1345d9d6e2bffc7c12362eb4431a72e9b/docs/providers)
- [Antigravity 프로토콜과 제약](https://github.com/robinebers/openusage/blob/519431b1345d9d6e2bffc7c12362eb4431a72e9b/docs/providers/antigravity.md)
- [Claude 인증·조회 방식](https://github.com/robinebers/openusage/blob/519431b1345d9d6e2bffc7c12362eb4431a72e9b/docs/providers/claude.md)
- [Claude Desktop 인증 형식 구현](https://github.com/robinebers/openusage/blob/519431b1345d9d6e2bffc7c12362eb4431a72e9b/Sources/OpenUsage/Providers/Claude/ClaudeDesktopAuthStore.swift)

상위 구현을 프로토콜 참고 자료로 사용했지만 실행 시 OpenUsage 코드를 불러오지 않는다.
Desktop 로그인 디코딩/선택을 참고·변환한 부분의 MIT 고지는
`scripts/third_party/OpenUsage-LICENSE.txt`에 보존했다.
일부 서비스의 내부 API/저장 형식은 변경될 수 있으므로 공식 인터페이스가 있으면 우선 사용한다.
