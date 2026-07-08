# loop-delegation (Claude Code plugin)

Claude Code 플러그인. 두 가지를 한 서피스(터미널·데스크톱 앱·IDE·claude.ai/code 웹)에 걸쳐 제공한다.

## 담긴 것

### 1. `loop-delegation` 스킬 (`skills/loop-delegation/`)

루프 엔지니어링 원칙(검증 가능한 정지 조건, maker/checker 분리, 가드레일, 실행 기록)에 따라
위임 산출물을 만든다. 수신자에 따라 형태가 갈린다:

| 수신자 | 산출물 | Claude Code 실행 수단 |
| --- | --- | --- |
| 사람 팀원 | 한국어 마크다운 지시서 | — |
| 인세션 서브에이전트 | `Agent` 프롬프트 + `subagent_type` | 단일/병렬 디스패치 |
| 독립·예약 에이전트 | 실행 설정 + 프롬프트 | `/schedule` cron, `/loop`, `Workflow` |

트리거: "지시서 만들어줘", "OO한테 맡기려고", "서브에이전트로 병렬로", "매시간 cron" 등.

### 2. `prefer-official-tools` 훅 (`hooks/`)

`PreToolUse(Bash)` 훅. 공식 도구로 대체 가능한 셸/경로 접근을 **조용히 auto-deny**(프롬프트 없이
거부)하고 리다이렉트 메시지를 준다. `&&`·`;`·`||`·`(`로 나뉜 **모든 구문의 머리**를 판정한다.

- **차단**: 절대경로/`node_modules/.bin/` 바이너리 직접 실행(`rg` 예외), 그리고 구문 머리의
  `cat`·`head`·`tail`·`sed`·`awk`·`grep`·`ls` → Read/Edit/rg로 유도.
- **허용**: `find`, `rg`(`/opt/homebrew/bin/rg` 포함), 파이프 뒤 필터(`git log | grep x`),
  모든 dev 도구(git/gh/pnpm/node/...).

`python3`로 실행하므로 exec 비트에 의존하지 않는다.

## 설치

```jsonc
// ~/.claude/settings.json (또는 프로젝트 .claude/settings.json)
{
  "extraKnownMarketplaces": {
    "miso-tools": { "source": { "source": "github", "repo": "<owner>/claude-loop-delegation" } }
  },
  "enabledPlugins": { "loop-delegation@miso-tools": true }
}
```

새 세션에서 로드된다. 스킬은 `/loop-delegation`으로도 호출 가능.

## 튜닝

- 차단 명령 추가/제거 → `hooks/prefer-official-tools.py`의 `REDIRECT` 딕셔너리.
- 특정 프로젝트만 끄기 → 그 프로젝트 `.claude/settings.local.json`에서 `enabledPlugins`를 `false`.
