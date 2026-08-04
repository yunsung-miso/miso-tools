---
name: release-finish
description: (miso-native 전용) 출시 마무리 꼬리 전체를 한 번에 오케스트레이션 — ① 릴리즈 노트 최신화(release-to-main) → ② 🔒 릴리즈 정렬(release ← main 동기화) + release→main PR → ③ CI 폴링 후 머지 게이트 → ④ 티켓 일괄 Done(release-tickets-done) ∥ 다음 주차 브랜치 컷(release-branch-cut) → ⑤ #frontend-dev 공지(브랜치명 + Amplitude 버전 현황). "출시 마무리", "릴리즈 마무리 전체", "release-finish", "출시 끝까지 한번에", "릴리즈 꼬리 자동화" 같은 요청에 사용. 기존 스킬을 재구현하지 않고 구동만 한다.
---

# Release Finish Skill

출시(앱 심사 통과·배포) 직후의 마무리 작업을 한 번의 호출로 끝낸다. 기존 단계별 스킬을 구동하며, 사이의 기계적 작업을 자동화하고 제거 불가능한 사람 결정만 게이트로 모은다.

구동 대상 (재구현 금지, 각 스킬 문서에 함정 처리 위임):

- `release-to-main` — 노트 최신화 + PR 생성
- `release-tickets-done` — 티켓 일괄 Done
- `release-branch-cut` — 다음 주차 release/bundle 브랜치 생성

## 실행 구조 — 병렬/직렬 + 모델 배치 (속도 핵심)

이 스킬의 벽시계 시간은 거의 전부 **Gate A의 외부 CI 대기(5~10분, 못 줄임)**다. 핵심 전략은 그 대기를 **다른 모든 준비 작업으로 채우는 것**이다. 직렬로 미뤘다가 머지 후 몰아서 하면 20분, 겹치면 ~8분.

**모델 배치 (3-tier — 판단 강도로 가른다)**

- **opus (main 스레드, 이 세션)** — 판단·게이트만: 정렬 충돌 해소, 티켓 In Review/In Progress 분류 판단(skip/이동/보류), 승인 게이트, 머지 감지, 공지 문구 확정. 위임 결과를 받아 결정만 한다.
- **sonnet 서브에이전트** — 절차+함정 있는 기계작업: ① Phase 1 노트+PR 조립(changelog `## What's Changed` 보존 footgun + 검증), ② branch-cut(git+버전범프 — Husky 재시도·3파일 스테이지·main lint 부채 블로커 해소 판단이 끼어 haiku 불가). branch-cut을 opus/general-purpose로 띄우지 말 것 — 느리고 과함.
- **haiku 서브에이전트** — 판단 0인 순수 lookup/추출 (가장 큰 절감):
  - **티켓 40+개 `get_issue` → compact 표** `{id, status, statusType, team}`만 반환. 거대 description을 main에 안 들임. 분류는 opus가 표만 보고.
  - **CI 로그 빌드번호/Firebase raw 추출** — `gh api .../jobs/{id}/logs | grep -m{N} ...` 4건.
  - **승인된 티켓 `save_issue` 일괄 뮤테이션** (위임 시) — 표가 확정된 뒤 mechanical.

> 원칙: lookup·field 매핑·정해진 grep = haiku. 절차+footgun·조건분기·블로커 해소 = sonnet. 판단·게이트 = opus(main).

**병렬 구간 (동시 발사)**

- Phase 0 감지: 모든 gh/git read-only 체크 한 메시지에.
- Phase 1 fact-gather: prod-iOS · prod-Android · staging-iOS · staging-Android 로그 추출 + `generate-notes` + 🔒 정렬 체크 — 전부 독립 read라 동시. (sonnet 서브에이전트 1개가 노트+PR을 통째로 맡고, main은 정렬 체크를 동시에.)
- **Gate A 대기 윈도우 (가장 중요)**: CI 폴링(백그라운드) **∥** Linear 인증(사람) **∥** 티켓 추출+get_issue+분류+승인표 작성(haiku 서브에이전트). 머지 감지 순간 티켓 승인 게이트가 **즉시** 뜨도록 미리 다 만들어 둔다.
- Phase 2: 티켓 Done 뮤테이션(main, 게이트 직후 즉시) **∥** branch-cut(sonnet 백그라운드 에이전트).
- Phase 3: Amplitude 차트 2건 조회 **∥** 공지 초안 작성. branch-cut 결과가 나온 뒤에만 시작.

**직렬 장벽 (못 겹침)**

- 입력 수집 → 그 다음 전부. (단 Linear 인증·CI 폴링은 뒤 구간과 겹침)
- 🔒 정렬 확인 → 머지 진행 (정렬 안 됐으면 머지 금지).
- 사람 머지 → Phase 2 뮤테이션 (티켓 Done은 출시 후에만, branch-cut은 머지된 main 기준).
- 승인 게이트 → 뮤테이션 (티켓 Done, 충돌 해소).
- **branch-cut 완료 → Phase 3 공지** (공지에 실제 컷된 브랜치명·SHA를 쓰므로 추측 금지).

## 입력 (시작 시 한 번에 수집 — 중간 핑퐁 금지)

스킬 시작 시 아래를 **모두 먼저** 확보한다. 사람 입력은 한 번에 묶어 묻는다. **특히 Linear 인증은 여기서 미리** — 안 그러면 머지 후 흐름 중간에 인증 stall이 생긴다.

| 입력 | 확보 방법 |
|---|---|
| `version` (마무리 대상, 예 6.2607.2) | 현재 브랜치(`release/X`)/최신 `v*` 태그에서 추론 → 사용자 확인 |
| iOS TestFlight 링크 (prod + staging) | **사용자 입력 필수** (App Store Connect, CI 로그에 없음). 없으면 placeholder로 진행 가능 |
| 다음 릴리즈 버전 `next` | **사용자** (patch+1 기본 제시, 주차 롤오버는 판단) |
| Linear MCP 인증 | `get_issue`가 deferred 목록에 없으면 미인증 → **시작 시 즉시** `authenticate` 호출해 URL을 사용자에게 띄운다. 인증은 CI 대기와 겹쳐 진행됨. `mcp__linear-server__*`가 죽어 있어도 **`mcp__claude_ai_Linear__*`(claude.ai 커넥터)가 같은 회사 워크스페이스에 붙어 있으면 그걸 쓴다** — 인증 대기 없이 바로 진행 가능 |
| staging 빌드 run | `release/{version}`의 최신 "Build Host App" workflow_dispatch run 자동 탐색 → 확인 |
| `bundle` 버전 | = `version` (자동) |

> 빌드번호/Firebase/commit 등 나머지는 전부 자동 추출이므로 사람에게 묻지 않는다.

## Phase 0 — 상태 감지 (재개 가능, 전부 병렬)

이미 끝난 단계는 건너뛴다. 아래를 **한 메시지에 병렬로**:

```bash
gh release view "v{version}" --json body -q .body        # '## test app' 섹션 + placeholder 잔존 여부
gh pr list --base main --head "release/{version}" --state all --json number,state,mergedAt
git ls-remote --heads origin "release/{next}" "bundle/{version}"   # 있으면 브랜치컷 완료
```

진행 위치를 사용자에게 한 줄로 보고하고 남은 단계만 수행.

## Phase 1 — 노트 + 릴리즈 정렬 + PR (fact-gather 전부 병렬)

**sonnet 서브에이전트 1개**에 1-1·1-3을 위임(아래 절차 그대로)하고, main은 1-2 정렬 체크를 **동시에** 돈다. 4개 CI 로그 추출도 서브에이전트 안에서 한 메시지 병렬.

### 1-1. 노트 최신화 (`release-to-main` 구동)
`release-to-main` 절차대로 CI run 로그에서 빌드번호·Firebase 추출(`gh api .../jobs/{id}/logs | grep -m1 ...` — `gh run view --log`는 잘림, `| head`는 다단계 파이프라 금지 → `grep -m{N}`). prod는 release.yml run, staging은 "Build Host App" run에서 동일 추출 — **4건(prod·staging × iOS·Android) 병렬**. 노트 본문이 **비어 있으면** `gh api -X POST .../releases/generate-notes`로 changelog 생성 후 test app 섹션을 이어붙여 `gh release edit`. **changelog(`## What's Changed`) 보존 검증 필수.** 본문은 Write로 파일 만들어 `--notes-file`.

TestFlight 링크만 사용자에게서 늦게 오는 경우가 흔하다. 서브에이전트는 빌드번호만 채우고 `{{TESTFLIGHT_*}}`는 남겨 두게 하고, 링크가 도착하면 main이 그 파일을 Edit → `gh release edit`으로 한 번 더 반영한다.

### 1-2. 🔒 릴리즈 정렬 (필수 가드레일 — 절대 생략 금지, main 스레드가 1-1과 동시에)

> 사용자가 앱 심사 때 놓친 부분. **release ⊉ main 상태로는 머지 단계로 넘어가지 않는다.**

```bash
git fetch origin main "release/{version}" -q
git merge-base --is-ancestor origin/main "origin/release/{version}"   # exit 0 = 이미 정렬됨
```

`origin/main`이 `origin/release/{version}`의 조상이 아니면(= main에 release에 없는 커밋 존재) 정렬한다:

1. release 브랜치 체크아웃(또는 로컬 브랜치 최신화) 후 `git merge origin/main`.
2. **충돌 시**: 충돌 파일별로 merge-base 대비 양쪽 diff를 분석해 **구간별 권장 해소안 제시**. 내용 기준으로 남길 블록을 명확히 지정.
3. **사용자 승인 후** 해소 적용 → `git push`.
4. 충돌 마커 잔여물 0건 + `mergeable: MERGEABLE` 재확인.

로컬 `release/{version}` 이 원격보다 뒤처져 있으면 `git merge --ff-only origin/release/{version}` 으로 먼저 맞춘다(로컬 tracking이 `origin/main`을 향해 있어 "diverged"로 보이는 경우가 있다 — 원격 ref만 신뢰).

### 1-3. PR 생성/갱신 (서브에이전트, 빌드데이터 모이면 노트 edit과 무관하게 발사)
`release-to-main`의 PR 본문 템플릿(빌드정보 표 + commit + 릴리즈 노트 링크)으로 `Release/{version} to main` PR 생성. 이미 있으면 본문 갱신.

## Gate A — 머지 (CI 폴링하면서 그 시간에 Phase 2a 준비를 끝낸다)

PR이 서면 **CI 폴링을 백그라운드로 띄우고, 그 대기 시간에 다음을 병렬로 진행**한다 (이게 이 스킬 속도의 전부):

1. **CI 폴링 (백그라운드 스크립트)** — 비정적 루프는 PreToolUse 훅이 막으니 폴 루프를 `.sh` 파일로 Write 후 `bash <path>`를 `run_in_background`로. pending bucket 0 되면 exit → 자동 알림.
   ```bash
   gh pr checks {pr} --json name,state,bucket   # bucket: pending/pass/fail/skipping
   ```
2. **Linear 인증** — 시작 시 안 됐으면 여기서라도. (이상적으론 입력 단계에서 끝나 있음)
3. **티켓 Phase 2a 사전 준비 (haiku 서브에이전트)** — 머지 전에 다 만들어 둔다:
   - 티켓 추출 = `git log v{prev}..v{version}`의 `(PRD|MIS|IBP|MPP|AIP|RFQP)-[0-9]+` ∪ GitHub changelog PR 목록 (번들/cherry-pick 토폴로지로 갈리므로 **합집합** 후 unique).
   - `get_issue` 병렬 호출 후 **compact 표만 반환**: `{id, status, statusType, team}`. 거대 description을 main에 안 들인다. (필드 매핑뿐이라 haiku로 충분 — 분류 판단은 main.)
   - ⚠️ **서브에이전트가 낸 개수 요약은 신뢰하지 말고 표를 직접 세라.** 실측에서 haiku가 "Test Passed 22건"이라 보고했는데 표를 세면 27건이었다. 승인 게이트에 올리는 숫자는 main이 표에서 재계산한 값.
   - main이 그 표로 분류(아래 2a)해서 **승인 게이트를 머지 전에 미리 띄워도 됨** (상태는 5분 새 안 바뀜). 머지 감지 순간 뮤테이션만 발사.

CI green이면 사용자에게 **"머지하세요"** 알림 (자동 머지 `gh pr merge` 금지 — 브랜치 보호). 머지 감지(`gh pr view {pr} --json state` → MERGED)되면 Phase 2로 자동 진행.

## Phase 2 — 머지 후 (두 작업 병렬)

티켓(Linear MCP only)과 branch-cut(git)은 독립이라 **동시**. branch-cut은 **sonnet 백그라운드 서브에이전트**(메인 체크아웃 — node_modules 있어야 Husky pre-push 통과, **worktree 격리 금지**), 티켓 뮤테이션은 main 스레드.

### 2a. 티켓 일괄 Done (`release-tickets-done` 구동)
- 분류 (Gate A에서 받은 compact 표 기준):
  - `Done`(completed) → **skip**
  - `Duplicate`/`Canceled` → **skip**
  - `Test Passed`/`Ready to Deploy`(completed) → **이동**
  - `In Review`/`In Progress`(started) → **이동**, 단 "임시/진단 로그만 출시되고 본 수정은 진행 중"인 티켓(예: 계측 전용 티켓, 활성 작업 브랜치 티켓, 서버사이드 미해결 핫픽스)은 **보류** 후보로 분리 — main이 판단해 사용자에게 옵션으로 제시.
  - `Backlog`/`Todo` → 사용자 확인.
- 표로 정리해 **승인 게이트** → 승인 후 `save_issue({id, state: 'Done'})` 일괄(병렬).
- ⚠️ **save_issue 응답은 eventually-consistent** — 방금 쓴 status가 응답·즉시 재조회에 **이전 값으로 보일 수 있다**(updatedAt/stateHistory 미변). 한 건씩 즉시 재검증하지 말 것(detour 유발). 일괄 발사 후 필요하면 **한 박자 뒤 한 번만** 샘플 재조회. exit 성공이면 적용된 것으로 신뢰.
- `state: 'Done'`(이름)이 안 먹는 듯 보이면 팀별 Done state ID로(아래 캐시) — 단 위 stale 때문일 가능성이 더 큼.

### 2b. 다음 주차 브랜치 컷 (`release-branch-cut` 구동, sonnet 백그라운드)
- `bundle/{version}` = origin/main tip (커밋 없음) 생성·푸시.
- `release/{next}` 생성 → PM 자동감지 후 `pnpm set-versionName {next}` → **3개 파일만**(package.json / build.gradle / project.pbxproj) 스테이지 → `Set version to {next}` 커밋(+ Co-Authored-By) → 푸시.
- Husky pre-push 통과(우회 금지). 원브랜치 복귀. **Podfile.lock 머신 드리프트 폐기**(`git checkout -- packages/host/ios/Podfile.lock`).
- ⚠️ **방금 머지된 main에 lint 부채가 실려 있으면 버전범프 커밋의 Husky pre-commit(`lint:check`)이 막힌다.** CI Lint가 green이어도 로컬 full `lint:check`는 잡는다. 차단되면 우회 금지 — **그 수정을 release/{next}에 별도 커밋**(버전범프 커밋과 분리, `git add -A` 금지)으로 올리고 진행. main 직접 수정은 보호라 불가. 사전 회피: 컷 시작 전 `pnpm lint:check` 한 번 돌려 부채 유무 먼저 확인.
- ⚠️ 서브에이전트에게 **원브랜치명과 기존 untracked 파일 목록을 명시로 넘긴다.** 안 넘기면 "클린 복귀"를 자기 기준으로 판단해 사용자 작업 브랜치에 드리프트를 남긴다.
- 결과(브랜치 SHA·ls-remote 확인)를 구조화해 반환. **반드시 원브랜치 복귀 + 워킹트리 클린 확인.**
- main이 반환값을 **직접 재검증**한다: `git ls-remote --heads origin release/{next} bundle/{version}` + `git show --stat {버전범프 SHA}`(3파일인지) + `git status --short --branch`.

## Phase 3 — #frontend-dev 공지 (브랜치명 + Amplitude 버전 현황)

브랜치컷이 끝나면 팀에 알린다. **컷 결과가 확정된 뒤에만** 시작한다 — 공지에 브랜치명을 추측해 쓰면 안 된다.

### 3-1. 채널·대상 (하드코딩 — Slack 검색이 부실하다)

| 항목 | 값 |
|---|---|
| 채널 | `#frontend-dev` = `C0A5SC89V0F` |
| 멘션 그룹 | `<!subteam^S0ASK9X8F7S>` (기존 출시 공지 관행) |

⚠️ **Slack MCP의 `slack_search_channels`/`slack_search_users`는 퍼지 쿼리에 0건을 낸다.** `"frontend dev 프론트엔드 개발"`, `"fe"`, `"Yunju Lee 이윤주"` 모두 실패하고 `"frontend-dev"`, `"윤주"` 같은 **정확한 단일 토큰**에만 맞는다. 채널 ID를 잊었으면 `slack_search_public_and_private`로 과거 공지 메시지를 찾는 게 더 빠르다(`query: "브랜치 컷 release bundle from:<@{내 user_id}>"`). `slack_read_channel`은 정상 동작한다.

### 3-2. 구조 (부모 헤더 + 스레드 답글 — 기존 관행 준수)

과거 공지가 전부 이 형태다. 단일 메시지로 뭉치지 말 것.

**부모**
```
<!subteam^S0ASK9X8F7S> 앱 출시 및 새로운 버전 브랜치 생성
```

**답글 1 — 브랜치 안내 (컷 결과 그대로)**
```
{version} 릴리즈 마무리와 함께 다음 버전 브랜치를 만들어두었습니다.

• release/{next}
• bundle/{version}

기능 작업은 이제 bundle/{version} 브랜치를 사용해주세용.
백포트는 {직전 라이브 버전}까지 진행하면 됩니다.
```

- 브랜치명은 `ls-remote`로 확인한 실제 이름을 그대로 쓴다.
- **백포트 하한**은 아직 유저가 남아 있는 직전 라이브 버전(= 3-3의 최상위 점유 버전)이다. Amplitude 조회 결과로 정하고, 답글 2에서 근거를 보인다.

**답글 2 — 버전 현황 (Amplitude)**
```
최근 7일 기준 현재 우리 앱의 버전 현황입니다.

고객앱 (App Users)
• {v} — {n}명 ({p}%)
...
• 그 외 6.x 구버전 — 약 {p}%
• 5.x 레거시 — 약 {p}%

파트너앱 (레거시 4.x)
• {v} — {n}명 ({p}%)

{최상위 버전}이 {p}%라 백포트를 {최상위 버전}까지만 챙겨도 대부분 커버됩니다.

차트: <{url}|Customer App Version (Last 7d)> / <{url}|Partner App Version (Last 7d)>
```

**답글 3 — 개별 후속 요청 (있을 때만)**
```
<@{user_id}> 오늘 bundle/{직전} 에 올려주신 <{PR url}|#{n}> 작업은 {version}에도 반영 부탁드려요!
```

### 3-3. Amplitude 조회

저장된 차트를 그대로 쓴다(사용자가 과거에 스크린샷으로 올린 것과 동일 출처).

| 앱 | project | chart | 비고 |
|---|---|---|---|
| Miso Customer App | `364534` | `uhqtric` — Customer App Version (Last 7d) | 원앱 6.x 분포. 여기가 본체 |
| Miso Partner App | `393458` | `0enrg8su` — Partner App Version (Last 7d) | **레거시 파트너앱 4.x** — 원앱 아님 |

```
query_charts({ chartIds: ["uhqtric", "0enrg8su"], groupByLimit: 15, timeSeriesLimit: 0 })
```

- `composition` 차트 / `metric: MOST_RECENT` / user property `version` 기준이다. 응답은 CSV(`[버전, App Users, % of App Users]`).
- `timeSeriesLimit: 0` 필수 — 안 주면 인터벌 행이 쏟아진다.
- 상위 3개만 개별로 적고 나머지는 **"그 외 6.x 구버전 약 N%" / "5.x 레거시 약 N%"로 합산**한다. 15줄을 다 옮기면 아무도 안 읽는다.
- 파트너앱 프로젝트를 "원앱 파트너"로 오해하지 말 것. 원앱은 고객앱 프로젝트에 6.x로 잡힌다.

### 3-4. 가드레일

- **발송 전 초안 승인 필수.** 부모/답글 전문을 사용자에게 보이고 승인받은 뒤에만 `slack_send_message`. Slack 발송은 되돌리기 어렵다.
- 🔒 **"출시되었습니다" 문구는 Amplitude에 그 버전 유저가 실제로 잡힐 때만 쓴다.** 실측 사례: 6.2607.2 릴리즈 마무리를 다 했는데 Amplitude 유저는 0명이고 6.2607.1이 93.9%였다 — 스토어 배포 전이었다. 이때 "출시되었습니다"는 거짓이 된다. 유저가 0이면 "릴리즈 마무리와 함께" 같은 중립 표현으로 쓰고, 그 사실을 사용자에게도 보고한다.
- 스레드 답글은 `thread_ts`에 **부모 메시지의 ts**를 넣는다(부모 발송 응답의 `message_ts`).
- 사람 멘션은 `<@{user_id}>`, 그룹은 `<!subteam^{id}>`. 이름 문자열로 쓰면 멘션이 안 걸린다.
- 링크는 Slack 문법 `<url|label>`.
- 톤은 해요체 + 기존 공지 어미(`~해주세용`)를 따른다. 대외 문구를 임의로 격식화하지 말 것.

## 사람 터치포인트 (총 5, 대부분 CI 대기와 겹쳐 stall 최소화)

1. 시작 시 한 번에: iOS TestFlight 링크 prod/staging + 다음 버전 + (필요시) Linear 인증 URL
2. 충돌 해소 승인 (충돌이 있을 때만)
3. PR 머지 클릭
4. 티켓 Done 승인 (CI 대기 중 미리 표를 만들어 두면 머지 직후 즉답 가능)
5. 공지 초안 승인 (Phase 3)

## 가드레일

- **🔒 릴리즈 정렬 필수** — `git merge-base --is-ancestor origin/main origin/release/{version}` 실패 시 정렬 전엔 머지 금지.
- **Husky 우회 절대 금지** — `--no-verify`/`HUSKY=0`/`SKIP_HUSKY`/hook 수정 전부 금지. 실패 시 원인 수정 후 동일 명령 재시도.
- **Podfile.lock 머신 로컬 hermes/codegen 드리프트 커밋 금지** — 작업트리에 남으면 `git checkout --`로 폐기. `pnpm install`·`pnpm typecheck`의 postinstall이 `pod install`을 돌려 매번 다시 생긴다.
- **changelog 보존 검증** — 노트 편집 후 `## What's Changed` 생존 확인.
- **iOS TestFlight 링크 추측/생성 금지** — 사용자 입력 필수(없으면 placeholder 명시).
- **티켓 Done은 승인 후에만** (외부 시스템 일괄 변경). save_issue는 eventually-consistent.
- **버전 범프 커밋엔 3개 파일만** — `git add -A`/`commit -a` 금지.
- **branch-cut 후 원브랜치 복귀 + 클린 확인 필수** — 안 하면 사용자 브랜치 오염.
- **Slack 발송 전 초안 승인 필수**, 출시 표현은 Amplitude 실측과 일치할 때만.
- **Bash**: 단일 명령, `cd` 복합 금지, 명령치환·다단계 파이프 금지(`grep -m{N}`로 `head` 대체, `2>&1` 리다이렉트도 훅이 막음). 큰 출력은 run_in_background 파일을 Read.

## Linear 팀 Done state ID 캐시 (이름 안 먹을 때만)

- Product `77794628-6b82-4fc4-9a4e-56d0af24a97f`
- Miso-All `24a44b73-03cf-4623-97c3-0b0802370b58`
- MP Product `3487f25b-59da-462f-b82f-f9b923ce8ae7`
- AI Product `83af4438-dc42-4d5f-8142-d6bceab0a321`
- IB Product `b401b2d2-9c8a-45fa-975c-12176e0be35f`

## 범위 밖

- 자동 머지(`gh pr merge`) — 머지는 사람 클릭 유지.
- `release-create`(태그·릴리즈 생성) — 이 스킬 선행 단계.
- 번들 잔여 작업의 release 반영 — `bundle-to-release-merge` / `bundle-release-status` 소관.
- 공지 후 오픈 PR의 타겟 재조정 — 별도 요청으로 처리.
- GitHub Actions / 멀티 에이전트 Workflow 형태 — 인터랙티브 게이트·자격증명 제약으로 미채택.

## 관련

- 단계별 스킬: `release-to-main`, `release-tickets-done`, `release-branch-cut`, `release-create`
- 번들 계열: `bundle-release-status`, `bundle-to-release-merge`, `ota-release`
