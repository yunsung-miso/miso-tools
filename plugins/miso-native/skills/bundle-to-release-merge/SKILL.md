---
name: bundle-to-release-merge
description: 직전 출시 번들 브랜치(bundle/{이전버전})에 OTA 로 들어간 핫픽스를, 다음 출시(앱 심사 대상) release/{현재버전} 브랜치 위로 rebase 해서 네이티브 빌드에 baking 하는 작업. 번들 원본은 보존하려고 복사 브랜치(bundle-merge/{이전버전})에서 작업하고, 그 복사본을 release 로 향하는 PR 로 올린다. "번들 릴리즈에 리베이스 머지", "bundle/X.X.X 를 release/Y.Y.Y 에 병합", "심사 전에 번들 핫픽스 릴리즈에 반영", "번들 복사해서 리베이스 머지 커밋 만들어줘" 같은 요청에 사용.
---

# Bundle → Release Rebase-Merge Skill

앱 심사를 시작할 때, **직전 출시본의 OTA 번들 브랜치**(`bundle/{이전버전}`)에 쌓인 핫픽스를 **이번 심사 대상 릴리즈 브랜치**(`release/{현재버전}`) 위로 rebase 해서, 심사로 나갈 네이티브 빌드에 그 변경들을 같이 싣는다.

OTA 로만 나갔던 픽스(번들 브랜치에만 있는 커밋)는 네이티브 빌드에는 빠져 있으므로, 다음 네이티브 출시 때 반드시 release 브랜치로 끌어와야 한다. 이 스킬이 그 끌어오기를 안전하게(번들 원본 보존 + 충돌 진단 + 검증) 자동화한다.

> **이건 기계적 rebase 가 아니다.** release 브랜치는 한 주 사이 대규모 리팩토링(쿼리 레이어 전환, 패키지 매니저 이행, 라이브러리 제거 등)이 들어가 있을 수 있고, 그러면 번들 커밋이 **텍스트 충돌 없이도 깨진다**(아래 "시맨틱 충돌" 참조). rebase 가 깨끗하게 끝나는 건 시작일 뿐 — **typecheck + 전 패키지 test 가 진짜 게이트**다.

## 왜 "복사"인가 (핵심 동기)

`bundle/{이전버전}` 은 **그 버전에 잔류한 유저용 OTA 수정 PR 의 살아있는 타깃**이다. 계속 거기로 핫픽스 PR 이 들어온다.

이 레포는 **PR 머지 시 head 브랜치를 자동 삭제**한다. 따라서 `bundle/{이전버전}` 을 직접 release 로 머지하면 원본 번들 브랜치가 사라져 OTA 수정 경로가 끊긴다.

→ 그래서 `bundle/{이전버전}` 을 **복사**한 `bundle-merge/{이전버전}` 에서 rebase 하고, 그 복사본을 PR 로 올린다. PR 이 머지되며 삭제되는 건 복사본이고, 번들 원본은 그대로 남는다.

## 입력

- `bundleVersion` — OTA 핫픽스가 쌓인 직전 출시 번들 (예: `6.2606.1`). 소스 = `origin/bundle/{bundleVersion}`.
- `releaseVersion` — 이번 심사 대상 릴리즈 (예: `6.2606.2`). 타깃(rebase base + PR base) = `origin/release/{releaseVersion}`.

버전 스킴은 `6.{YYWW}.{N}`. **둘 중 하나라도 모호하면 사용자에게 물어본다.** 특히 타깃은 "지금 활성 릴리즈"이므로, `git ls-remote --heads origin "release/*"` 로 현재 살아있는 release 브랜치를 확인해 사용자와 맞춘다.

## 핵심 사실 (검증됨 — 함정 포함)

- **항상 fresh fetch 후 origin ref 만 신뢰**. 로컬 추적 ref(`origin/...`)도 stale 할 수 있다. 범위·개수·충돌 판단 전에 반드시 `git fetch origin {release} {bundle}` 하고, **stale 한 origin/bundle 로 센 커밋 수는 거짓**이다 (실측: stale ref 로 "5개"라 판단했다가 fresh fetch 후 실제 22개였던 사례).
- **타깃 base 는 반드시 `origin/release/{releaseVersion}`**. 로컬 `release/*` 브랜치를 base 로 쓰지 말 것. 이미 출시되어 `main` 에 머지·삭제된 릴리즈(예: `release/6.2606.1`)는 **로컬에만 stale 하게 남아** 엉뚱한 tip(누군가 origin/main 을 머지)을 가리킬 수 있고, 이걸 base 로 rebase 하면 무관한 커밋이 섞이고 PR 도 깨진다(`Base ref must be a branch`). 원격 실재를 `ls-remote` 로 확인하고 `origin/` 접두 ref 만 쓴다.
- **release 는 움직이는 타깃이다.** 작업 중에도 release/{현재버전} 에 새 커밋이 push 될 수 있다(실측: 작업 중 폴더블 7커밋이 추가됨). push 직전 다시 `git fetch` 해서 **최신 tip 으로 re-rebase** 하고, push 후 **PR mergeable 을 확인**한다. CONFLICTING 이면 또 re-rebase.
- **rebase 가 깨끗 ≠ 코드가 맞음 (시맨틱 충돌).** release 의 리팩토링이 번들 커밋의 전제를 깨면 **텍스트 충돌 없이도** 컴파일/런타임이 깨진다. 실측 사례:
  - `@lukemorales/query-key-factory` 제거 → 번들이 추가한 `*/queryKeys.ts`(createQueryKeys)·`*Keys._def` 사용처가 전부 깨짐 → release 의 `queries.ts`(queryOptions) 패턴으로 재구현.
  - `moment` 등 라이브러리 제거 → 번들의 `moment/moment` import 깨짐 → release 대체 유틸(`@miso/shared` formatDate 등)로 전환.
  - yarn → pnpm strict 이행 → 번들이 미선언 패키지를 직접 import(raw `axios` 등) 하던 게 깨짐 → shared 클라이언트/인터셉터 경유로 전환(불필요한 의존성 추가 금지).
  - **그래서 rebase 후 반드시 `typecheck` + 전 패키지 `test` 를 돌린다.** 이게 진짜 검증이고, pre-push·CI 도 동일하게 돈다.
- **복사 브랜치명 = `bundle-merge/{bundleVersion}`** (소스 번들 버전 기준).
- rebase 는 이미 release 에 들어간 커밋(patch-id 동등)을 **자동 skip**하고, 중복 `Set version` 커밋도 collapse 한다.
- 충돌 해소는 추측·자동 전략 금지, 진단 후 **합집합이 기본**.
- Husky pre-commit/pre-push 우회 절대 금지(`--no-verify`/`HUSKY=0`/`SKIP_HUSKY=1` 금지).
- **worktree 격리**에서 작업한다. 단, worktree 에서 `pnpm typecheck`/`test` 는 verify-deps 가 install→postinstall(pod install)을 트리거할 수 있으니 **`npm_config_verify_deps_before_run=false`** env 를 붙인다.

## Pre-flight Checks

```bash
git fetch origin "release/{releaseVersion}" "bundle/{bundleVersion}"   # 항상 fresh
git ls-remote --heads origin "release/{releaseVersion}"   # 비어있으면 STOP (버전 오인/미cut)
git ls-remote --heads origin "bundle/{bundleVersion}"     # 비어있으면 STOP
```

로컬에 동명의 `release/{releaseVersion}` 이 있어도 신뢰하지 말고 `origin/...` 만 쓴다.

## 병합 범위 산정 (실행 전 반드시 사용자에게 보여줄 것)

```bash
git merge-base origin/release/{releaseVersion} origin/bundle/{bundleVersion}
# patch-id 까지 감안한 "release 에 없는 번들 작업"의 진짜 목록:
git log --oneline --cherry-pick --right-only origin/release/{releaseVersion}...origin/bundle/{bundleVersion}
```

- `--cherry-pick --right-only` 결과가 **release 에 없는(=가져올) 커밋**이다. 단순 `A..B` 보다 정확(이미 다른 SHA 로 들어간 것 제외).
- **0건이면 STOP**: 번들이 이미 release 에 다 들어있음.
- 개수·목록을 사용자에게 보여주고, fresh fetch 직후 값인지 재확인한다.

## Step-by-Step Flow

### 1. worktree 생성 + rerere

```bash
git worktree add -b tmp/bundle-merge-{bundleVersion} <scratch>/wt-bundle-merge origin/bundle/{bundleVersion}
git -C <scratch>/wt-bundle-merge config rerere.enabled true   # 재-rebase 시 동일 충돌 자동 재현
```

### 2. release 위로 rebase → 충돌 해소

```bash
git -C <wt> rebase origin/release/{releaseVersion}
```

충돌 파일마다: `git -C <wt> diff <file>` 로 양쪽(HEAD=release / incoming=번들 커밋) 의도 파악 → **합집합 기본**(한쪽이 대체면 근거 남기고 택일) → `rg -n "<<<<<<<|>>>>>>>" <file>`(잔존 0) → `git -C <wt> add <file>` → `git -C <wt> -c core.editor=true rebase --continue`. `-X theirs/ours`·맹목적 `--skip` 금지.

리팩토링이 삭제한 파일을 번들이 수정한 경우(modify/delete)는 release 방향(삭제)을 따르고, 번들의 의도는 release 의 새 구조 위에 재구현한다.

### 3. 검증 (이 스킬의 핵심 — 생략 금지)

```bash
# 얹힌 커밋이 "가져올 것"과 일치하는지
git -C <wt> log --oneline origin/release/{releaseVersion}..tmp/bundle-merge-{bundleVersion}

# 시맨틱 충돌 잡기 — verify-deps 끄고 (postinstall pod 우회)
npm_config_verify_deps_before_run=false pnpm -C <wt> typecheck
npm_config_verify_deps_before_run=false pnpm -C <wt> test
```

- typecheck/test 가 깨면 → 시맨틱 충돌이다. release 의 새 구조에 맞춰 고친다(위 "시맨틱 충돌" 사례 참조).
- 이 **post-rebase 정합 수정은 rebase 한 여러 커밋에 걸치므로**, 맨 위에 `[Chore] release/{releaseVersion} 리팩토링 정합 — bundle 통합 후속 수정` 한 커밋으로 모은다(또는 관련 커밋에 fixup). 최종 트리만 맞으면 CI 는 통과.
- typecheck/test 는 **전 패키지** 로 돌린다. 타깃만 돌리면 다른 패키지의 기존 테스트(예: 옛 구현을 검증하던 테스트)가 깨진 걸 놓친다.

### 4. push (재-rebase 안전장치 포함)

```bash
git fetch origin release/{releaseVersion}            # push 직전 release 이동 확인
git log --oneline {직전 base}..origin/release/{releaseVersion}   # 새 커밋 있으면
git -C <wt> rebase origin/release/{releaseVersion}   # → re-rebase + 3번 재검증
git -C <wt> push origin tmp/bundle-merge-{bundleVersion}:bundle-merge/{bundleVersion}
```

- pre-push 가 **전 패키지 test 까지** 돈다(수 분). 3번에서 미리 통과시켜 두면 사이클 낭비를 막는다.
- **force-push 판단**: PR head 를 처음 만들 때·잘못 만든 PR 을 통째로 교정할 때·release 이동으로 re-rebase 할 때는 `-f` 가 정상(리뷰 스레드가 없으면 안전). 리뷰 코멘트가 달린 뒤 임의 force-push 는 스레드를 꼬이게 하니 피한다.
- push 후 `git ls-remote origin refs/heads/bundle-merge/{bundleVersion}` 로 tip 대조(rtk 가 push 출력을 요약해 가릴 수 있음).

### 5. PR 생성 (전용 최소 형식)

이미 리뷰·머지된 작업의 재배치라 일반 템플릿(테스트/배포 영향/UI·UX/리뷰 포인트)을 **쓰지 않는다**. `create-pr` 안 거치고 `gh pr create --body-file` 로 직접(템플릿 주입 무시).

**타이틀**: `[{bundleVersion}] merge to {releaseVersion}` (예: `[6.2606.1] merge to 6.2606.2`)

**본문**: 릴리즈 노트 스타일(`.github/release.yml` 카테고리). `## 작업 내용`(한두 줄 요약 + 정합·검증 언급) + `## 병합된 PR`(카테고리별 **`- #N` 만**) + 필요 시 `## 통합 후속 커밋`.

- **PR 은 `- #N` 만 적는다 — 제목을 같이 쓰지 말 것.** GitHub 가 `#N` 으로 PR 제목을 자동 렌더하므로, 제목을 덧붙이면 "제목 #N 제목"으로 중복돼 지저분해진다 (실측 지적).
- 번호·제목은 커밋 subject 가 아니라 **gh 에서** 받는다 (긴 한글 subject 는 표시가 잘리고 `#N` 추출도 깨진다):
  ```bash
  gh pr list --base bundle/{bundleVersion} --state merged --json number,title --limit 60 \
    --jq '.[] | "\(.number)\t\(.title)"'
  ```
  제목 prefix 로 카테고리 분류: `[Feature]`→🚀 Features, `[Bugfix]`/`[Fix]`→🐛 Bug Fixes, `[Refactor]`→♻️ Refactoring, `[Chore]`/`[Docs]`→🔧 Chores & Docs.
- 병합 범위 산정에서 **patch-id 로 이미 release 에 있어 제외된 PR** 은 목록에서 빼고, 본문에 "이미 반영돼 제외(#NNNN)" 한 줄로 명시.
- PR 없는 직접 커밋은 `- (PR 없는 직접 커밋) {짧은 제목}`.
- 정합 수정([Chore] 커밋)·기타 후속(폴더블 등)은 `## 통합 후속 커밋` 에 한 줄씩 적어 리뷰어가 rebase 외 변경을 알게 한다.

```bash
gh pr create --base release/{releaseVersion} --head bundle-merge/{bundleVersion} \
  --title "[{bundleVersion}] merge to {releaseVersion}" --body-file <body.md>
gh pr edit {N} --add-reviewer getmiso/miso-app
gh pr edit {N} --add-label "Application"
gh pr view {N} --json mergeable,mergeStateStatus   # MERGEABLE 확인 (CONFLICTING 이면 re-rebase)
```

### 6. 정리

```bash
git worktree remove <scratch>/wt-bundle-merge --force
git branch -D tmp/bundle-merge-{bundleVersion}
```

## Safety Guardrails (강제)

- **번들 원본 보존**: `bundle/{bundleVersion}` 직접 머지 금지. 항상 복사본에서 작업.
- **base 는 `origin/release/{releaseVersion}` 만**: 로컬 `release/*` 신뢰 금지, `ls-remote` 로 원격 실재 확인.
- **fresh fetch 후 판단**: stale ref 로 센 커밋 수/충돌은 거짓.
- **rebase 깨끗해도 typecheck + 전 패키지 test 필수**: 시맨틱 충돌을 잡는 진짜 게이트.
- **release 이동 대비**: push 직전 fetch → 이동했으면 re-rebase + 재검증, push 후 mergeable 확인.
- **worktree 격리** + `npm_config_verify_deps_before_run=false` (pod install 우회).
- **충돌 진단 우선**: 자동 전략·맹목적 skip 금지. 합집합 기본.
- **Husky 우회 금지**.
- **범위 0건이면 STOP**.

## Related

- `release-branch-cut` — `release/{현재}` + `bundle/{직전}` 동시 cut (이 스킬의 선행).
- `bundle-backport` — 한 번들 → **다른 번들들** cherry-pick (가로). 이 스킬은 번들 → **릴리즈**(세로).
- `create-pr` / `release-create` / `release-to-main` / `release-tickets-done`.
- `.claude/docs/GIT_WORKFLOW.md`.

## 사용 예시 (실측 — 2026-06, bundle/6.2606.1 → release/6.2606.2, PR #1547)

```
[Pre-flight] fresh fetch. 로컬 release/6.2606.1 은 stale(출시·삭제) → 무시, origin/release/6.2606.2 사용.

[범위 산정] 처음엔 stale origin/bundle 로 "5커밋" 판단 → 사용자 지적으로 재-fetch →
  --cherry-pick --right-only 로 실제 22커밋(release 에 없는 OTA 작업) 확정. (stale ref 함정)

[rebase] 22커밋 replay. 텍스트 충돌: PRD-6612 딥링크, IBP-896 won-count, MPP-3221 결제,
  IBP-919 등 → 진단 후 합집합/재구현.

[검증 — 핵심] rebase 는 깨끗했지만 typecheck/test 가 다수 실패:
  · query-key-factory 제거 → booking/rfqPayment/rfq queryKeys 를 queries.ts 로 재구현
  · 제거된 moment → formatDate, raw axios → partnerWebApiClient 인터셉터 확장
  · 옛 구현 검증하던 기존 테스트(MisoWebApi)도 새 구현에 맞게 수정
  → [Chore] 정합 커밋 1개로 모음. typecheck 7/7 + 전 패키지 test ~3,394개 통과.

[push] push 직전 release 가 또 전진(MIS-3899 폴더블 7커밋) → CONFLICTING →
  최신 tip 으로 re-rebase(rerere 가 기존 해소 재현) → MIS-3899 와 겹친 4파일 추가 해소 →
  재검증 → force-push. PR mergeable=MERGEABLE 확인.
```

실제 출력은 단계별 규약과 일치하면 된다.
