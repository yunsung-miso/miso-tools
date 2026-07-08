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

## 설치 (신규 입사자용)

**전제**: Claude Code가 이미 설치·로그인돼 있어야 해요. 터미널에서 `claude` 명령이 뜨면 준비된 거예요.
(플러그인은 터미널·데스크톱 앱·IDE 확장·claude.ai/code 웹 어디서 설치해도 계정에 그대로 따라와요.)

### 방법 A — 슬래시 커맨드 (권장, 제일 쉬움)

Claude Code 세션 안에서 아래 두 줄만 입력하면 돼요:

```
/plugin marketplace add yunsung-miso/claude-loop-delegation
/plugin install loop-delegation@miso-tools
```

1번은 이 레포를 "마켓플레이스"로 등록하는 거예요(한 번만 하면 돼요). 2번은 그 마켓플레이스에서 플러그인을 설치하고요.
`/plugin` 만 쳐서 뜨는 메뉴에서 클릭으로 골라도 돼요.

### 방법 B — settings.json 직접 (팀 공유·자동화용)

여러 명에게 똑같이 깔거나 dotfiles로 관리할 땐 설정 파일에 직접 적어 두면 돼요:

```jsonc
// ~/.claude/settings.json (전 프로젝트 공통) 또는 프로젝트 .claude/settings.json
{
  "extraKnownMarketplaces": {
    "miso-tools": {
      "source": { "source": "github", "repo": "yunsung-miso/claude-loop-delegation" },
      "autoUpdate": true
    }
  },
  "enabledPlugins": { "loop-delegation@miso-tools": true }
}
```

`autoUpdate: true`로 두면 레포가 갱신될 때 세션 시작하면서 자동으로 최신 상태가 돼요.

### 설치 확인

플러그인·훅·스킬은 **세션 시작 때 로드**돼요. 설치했으면 새 세션을 하나 켜서 확인해 봐요:

- **스킬** — `/loop-delegation` 이 자동완성이나 스킬 목록에 뜨면 성공이에요.
- **훅** — Claude에게 "cat으로 이 파일 읽어줘"라고 한번 시켜 보세요. 프롬프트 없이 거부되면서
  *"파일 읽기는 Read 도구를 쓰세요 (cat 금지)"* 메시지가 나오면 훅이 잘 돌고 있는 거예요.

### 안 될 때

- `/plugin` 메뉴에서 `loop-delegation` 이 **enabled** 상태인지 확인해 보세요.
- 새 세션에서 다시 확인해 보세요 (기존 세션엔 반영이 안 돼요). `/plugin` 메뉴를 한 번 열면 config가 다시 로드돼요.
- 특정 프로젝트에서만 끄고 싶으면 그 프로젝트의 `.claude/settings.local.json`에서
  `"enabledPlugins": { "loop-delegation@miso-tools": false }` 로 지정하면 돼요.

## 튜닝

- 차단 명령 추가/제거 → `hooks/prefer-official-tools.py`의 `REDIRECT` 딕셔너리.
- 특정 프로젝트만 끄기 → 그 프로젝트 `.claude/settings.local.json`에서 `enabledPlugins`를 `false`.
