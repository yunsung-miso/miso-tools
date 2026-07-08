# miso-tools 온보딩

미소 작업용 Claude Code 플러그인 마켓플레이스. 플러그인 6개. 터미널·데스크톱 앱·IDE 확장·claude.ai/code 웹 어디서 설치해도 계정을 따라온다.

**전제**: Claude Code 설치·로그인 완료. 터미널에서 `claude` 뜨면 준비 끝.

## 1. 마켓플레이스 등록 (한 번만)

```
/plugin marketplace add yunsung-miso/miso-tools
```

## 2. 플러그인 설치 (필요한 것만 골라서)

```
/plugin install loop-delegation@miso-tools
/plugin install guardrails@miso-tools
/plugin install personal-workflow@miso-tools
/plugin install humanize@miso-tools
/plugin install create-pr@miso-tools
/plugin install miso-native@miso-tools
```

## 플러그인별 요약

| 플러그인 | 뭐 하나 | 누구용 |
| --- | --- | --- |
| `loop-delegation` | 루프 원칙 기반 위임 산출물(사람 지시서 / 서브에이전트 프롬프트 / 예약·상시 실행 설정) 생성 | 공용 |
| `guardrails` | 범용 가드레일 훅 — 공식도구 강제·정적분석 불가 bash 차단·시크릿 노출 차단·LSP 우선. 의존물 없음 | 공용 |
| `personal-workflow` | 윤성 개인 환경 훅 — rtk 재작성·worktree settings/env 동기화. 의존물 없으면 no-op | 윤성 개인 |
| `humanize` | 한글 AI 티 제거 윤문 스킬 + PR/리뷰/이슈 제출 직전 자동 트리거 훅 | 공용 |
| `create-pr` | PR 생성 스킬 — 간결성 하네스·베이스 브랜치 자동 검출·구조 PR Mermaid 강제 | 미소 레포 작업자 |
| `miso-native` | miso-native 프로젝트 스킬(릴리즈·번들·OTA·센트리·시뮬레이터·e2e 등 14종) + e2e 가드 훅 | miso-native 작업자 |

## 설치 확인

플러그인·훅·스킬은 **세션 시작 때 로드**된다. 설치 후 새 세션 하나 켜서 확인:

- **스킬** — `/loop-delegation`, `/create-pr` 등이 자동완성/스킬 목록에 뜨면 성공.
- **훅** — Claude에게 "cat으로 이 파일 읽어줘" 시켜 보기. 프롬프트 없이 거부되며 *"파일 읽기는 Read 도구를 쓰세요"* 나오면 guardrails 훅 정상.

## settings.json 직접 (팀 공유·자동화용)

```jsonc
// ~/.claude/settings.json 또는 프로젝트 .claude/settings.json
{
  "extraKnownMarketplaces": {
    "miso-tools": {
      "source": { "source": "github", "repo": "yunsung-miso/miso-tools" },
      "autoUpdate": true
    }
  },
  "enabledPlugins": {
    "loop-delegation@miso-tools": true,
    "guardrails@miso-tools": true,
    "humanize@miso-tools": true,
    "create-pr@miso-tools": true,
    "miso-native@miso-tools": true
  }
}
```

`autoUpdate: true` 로 두면 세션 시작 때 자동 최신화. 특정 프로젝트에서만 끄려면 그 프로젝트 `.claude/settings.local.json` 에서 해당 플러그인을 `false`.
