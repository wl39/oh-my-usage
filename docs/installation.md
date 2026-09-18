# 설치 과정과 문제 진단 · v0.7.1

`./install.sh`는 Linux에서 OpenUsage를 설치하거나 실행하지 않습니다. 필수 도구 준비, 전용 Python 환경, 명령 등록, 첫 사용량 조회, 대화형 zsh 진입까지 처리합니다. 설치 성공과 각 서비스의 로그인·사용량 API 성공은 구분합니다.

## 앞서 발생한 오류의 원인

**`No module named pip`**: Python 실행 파일이 있다는 사실만으로 가상환경이 완성됐다고 판단한 것이 원인이었습니다. 가상환경 생성이 중단되거나 pip만 삭제되면 Python은 실행돼도 `python -m pip`는 실패합니다. 현재는 Python·pip를 별도로 확인하고, `ensurepip`로 복구합니다. 인터프리터 자체가 깨졌으면 전용 `.venv`를 다시 만듭니다.

**NodeSource의 `jammy Release` 404**: `apt-get update`는 oh-my-usage의 의존성 저장소만 조회하는 명령이 아닙니다. 시스템에 등록된 모든 저장소를 조회합니다. 관련 없는 NodeSource 저장소가 실패해 APT가 100을 반환하자 설치 스크립트도 종료됐습니다. NVIDIA·Docker의 `legacy trusted.gpg` 경고와는 별개였습니다. 현재는 APT의 일반 오류 100이면 사용 가능한 패키지 목록으로 필요한 도구 설치를 시도합니다. 저장소를 삭제하거나 서명 검사를 끄지 않으며, 실제 패키지 설치 실패는 그대로 실패 처리합니다.

## 단계별 처리

| 단계 | 확인·처리하는 내용 | 실패할 때의 동작 |
| --- | --- | --- |
| 시스템 Python | Python 3.9+, ssl, sqlite3, venv, ensurepip. PATH의 shim이 불완전하면 정상 시스템 Python을 먼저 탐색 | 명시한 `OH_MY_USAGE_PYTHON`이 잘못됐으면 패키지를 설치하기 전에 구체적으로 안내 |
| 시스템 패키지 | 필요한 도구만 설치. APT 설치 잠금은 최대 60초 대기 | sudo 거절·사용자 취소·필수 패키지 설치 실패는 중단. 잠금 파일 삭제나 프로세스 강제 종료는 하지 않음 |
| 경로·셸 확인 | 설치·설정·캐시·명령 경로의 파일 종류와 쓰기 권한. 설정·캐시의 상대 경로는 거부하며 `~/`는 실제 홈으로 해석. `.zshenv` 적용 후 실제 `.zshrc` 위치 | 잘못된 경로·읽기 전용 설정을 의존성 설치와 파일 복사 전에 보고. 다른 사용자 파일을 덮어쓰지 않음 |
| 전용 Python 환경 | pip 유무, 인터프리터 실행, Ollama용 Ed25519 서명·검증까지 실제 실행 | pip 복구, 손상된 서명 의존성 재설치. 가상환경 재생성 실패 시 이전 환경을 되돌림 |
| 명령·표시 등록 | 사용자 명령과 zsh 플러그인 등록. 기존 표시 설정 유지 | CLI만 필요하면 `--no-shell` 사용. 같은 계정의 동시 설치·제거는 잠금으로 차단 |
| 서비스 조회 | 설치·로그인된 클라이언트 발견 후 첫 사용량 조회 | 로그인 만료·API 오류는 서비스 상태로 표시. 설치 성공을 로그인 성공으로 간주하지 않음 |
| 즉시 사용 | 터미널에서 실행하면 준비된 zsh로 진입 | `--no-start`와 비대화형 실행은 새 셸을 열지 않음. 기본 로그인 셸은 바꾸지 않음 |

전용 환경에서는 외부 `PYTHONHOME`, `PYTHONUSERBASE`, `PIP_TARGET`, `PIP_PREFIX`, `PIP_USER`가 설치 위치를 바꾸지 않게 처리합니다. 설치된 명령은 기록된 전용 Python을 우선 사용합니다. `OH_MY_USAGE_PYTHON`은 설치 환경을 만드는 Python을 선택하며, 설치 후의 전용 환경을 건너뛰지는 않습니다. 사내망에서 필요한 인덱스·프록시·인증서 환경 설정은 유지합니다. pip의 전역 설정 파일에 별도 `target`이 강제돼 있으면 해당 설정은 사용자가 확인해야 합니다.

의존성 설치는 소켓 제한 시간 15초, 재시도 2회, 한 번의 설치 명령 제한 시간 180초로 실행합니다. 이 제한 때문에 매우 느린 네트워크나 오래 걸리는 소스 빌드는 실패할 수 있으며, 무한 대기 대신 실패 단계를 안내합니다.

## 오류별 다음 행동

| 메시지 또는 증상 | 의미와 다음 행동 |
| --- | --- |
| `APT could not refresh every repository` | 일부 저장소 갱신이 실패했지만 필요한 패키지 설치를 계속하는 중. 뒤의 설치 결과 확인 |
| `Required system packages could not be installed` | 정상 패키지 목록도 없거나 다운로드·의존성 해결에 실패. 바로 위 APT 오류의 저장소·네트워크·패키지 문제를 해결한 뒤 재실행 |
| `OH_MY_USAGE_PYTHON must name...` | 잘못된 실행 파일 또는 지원하지 않는 Python. 지정값을 고치거나 `unset OH_MY_USAGE_PYTHON` 후 재실행 |
| `Python dependency installation failed` / `timed out` | PyPI/사내 미러 접근, 프록시, 인증서, wheel 호환성, pip 설정을 확인. SSL 검증을 끄지 말고 올바른 네트워크 설정을 사용 |
| `is not writable by this user` | 이전 sudo 설치나 읽기 전용 파일의 소유권·권한 문제. 표시된 경로의 권한을 확인. 전체 설치기를 sudo로 실행하지 않음 |
| `Cannot register zsh integration` | `.zshenv` 실패, 상대 ZDOTDIR, RCS 비활성화 등으로 자동 로딩할 수 없음. 설정을 고치거나 `--no-shell`로 CLI 설치 |
| `Another oh-my-usage installation...` | 다른 설치·제거가 진행 중. 완료 후 재실행 |
| `no connected services` / 서비스 인증 오류 | 프로그램 설치와 별개로 해당 클라이언트에 로그인하거나 필요한 API 키를 등록. `oh-my-usage providers`로 서비스별 확인 |

저장소에서 업데이트·재설치:

```sh
git pull --ff-only
./install.sh
```

설치된 파일의 환경만 복구하려면 다음도 가능합니다. 이 명령은 새 코드를 내려받는 업데이트는 아닙니다.

```sh
~/.local/share/oh-my-usage/install.sh --no-start
```

망이 막혔거나, 관리자 권한이 없거나, 시스템 패키지 데이터베이스가 손상된 상황까지 설치기가 임의로 해결하지는 않습니다. 실패 단계와 대상 경로를 확인할 수 있게 안내하며, 사용자 저장소·인증서 검증·파일 소유권을 임의 변경하지 않습니다.

## 검증 범위

CI는 Ubuntu 22.04/24.04의 정상 저장소 및 HTTP 404 저장소를 검사합니다. 일반 사용자 계정에서 필수 도구가 없는 최초 설치, pip 누락 복구, 즉시 사용 가능한 셸, OpenUsage 미호출, 제거까지 실행합니다.

`tests/integration/install-recovery.py`는 별도로 Python/pip 환경 변수 충돌, 잘못된 Python, 공백 경로, `.zshenv`의 설정 위치 변경, 손상된 암호화 모듈, 삭제된 인터프리터, 재생성 실패·복원, 권한 부족, 패키지 인덱스 연결 거절, 재시도, 전용 Python 없는 제거, APT 잠금 대기를 검사합니다. macOS/Python 최소 버전 검증과 각 서비스 응답·셸 테스트도 유지합니다.

다른 Linux 배포판의 패키지 관리자 분기는 제공하지만, 위 Ubuntu 검증을 모든 배포판의 실제 검증으로 확대해서 말하지 않습니다. 회사별 프록시·인증서·보안 정책이나 개별 사용자의 모든 dotfile 조합도 동일하게 재현한 것은 아닙니다.

동작 원칙을 확인한 공식 문서: [Python ensurepip](https://docs.python.org/3/library/ensurepip.html), [zsh 시작 파일](https://zsh.sourceforge.io/Doc/Release/Files.html), [pip 설정 우선순위](https://pip.pypa.io/en/stable/topics/configuration/).
