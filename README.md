# miso-tools

미소 작업용 Claude Code 플러그인 마켓플레이스. 스킬·훅을 플러그인 6개로 묶어 한 레포에서 배포한다.
터미널·데스크톱 앱·IDE 확장·claude.ai/code 웹 어디서 설치해도 계정을 따라온다.

## 담긴 플러그인

| 플러그인 | 뭐 하나 | 누구용 |
| --- | --- | --- |
| `loop-delegation` | 루프 원칙 기반 위임 산출물(사람 지시서 / 서브에이전트 프롬프트 / 예약·상시 실행 설정) 생성 | 공용 |
| `guardrails` | 범용 가드레일 훅 — 파괴 명령 차단(force push→보호브랜치·원격삭제·rm -rf /·DROP·terraform destroy 등)·공식도구 강제·정적분석 불가 bash 차단·시크릿 노출 차단·LSP 우선·완료 시 감사/요약 HTML 보고서. 풀 권한 운영용, 의존물 없음 | 공용 |
| `personal-workflow` | 윤성 개인 환경 훅 — rtk 재작성·worktree settings/env 동기화. 의존물 없으면 no-op | 윤성 개인 |
| `humanize` | 한글 AI 티 제거 윤문 스킬 + PR/리뷰/이슈 제출 직전 자동 트리거 훅 | 공용 |
| `create-pr` | PR 생성 스킬 — 간결성 하네스·베이스 브랜치 자동 검출·구조 PR Mermaid 강제 | 미소 레포 작업자 |
| `miso-native` | miso-native 프로젝트 스킬(릴리즈·번들·OTA·센트리·시뮬레이터·e2e 등 14종) + e2e 가드 훅 | miso-native 작업자 |

## 설치

Claude Code 세션에서:

```
/plugin marketplace add yunsung-miso/miso-tools
/plugin install loop-delegation@miso-tools
```

1번은 이 레포를 마켓플레이스로 등록(한 번만). 2번은 원하는 플러그인 설치 — 이름만 바꿔 반복.
6개 전체 install 명령·settings.json 방식·설치 확인법은 [`ONBOARDING.md`](./ONBOARDING.md) 참고.

## 레포 구조

```
.claude-plugin/marketplace.json   # 플러그인 6개 등록 (source + semver version)
plugins/<name>/
  .claude-plugin/plugin.json       # 플러그인 매니페스트
  skills/<skill>/SKILL.md          # 스킬 (있으면)
  hooks/                           # 훅 (있으면)
```

플러그인 추가/버전 범프는 각 `plugin.json` 과 `marketplace.json` 두 곳을 함께 갱신한다.
