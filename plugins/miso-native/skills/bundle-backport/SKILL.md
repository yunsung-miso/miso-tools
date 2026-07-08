---
name: bundle-backport
description: 한 번들 브랜치(예 bundle/6.2604.2)에 머지/오픈된 PR의 변경을 다른 번들 브랜치들(예 bundle/6.2603.1, bundle/6.2604.3)에도 cherry-pick + 푸시 + 새 PR 생성으로 자동 복제. 같은 수정/기능을 여러 릴리즈 번들에 한꺼번에 반영해야 할 때 사용.
---

# Bundle Backport Skill

한 번들 브랜치(예: `bundle/6.2604.2`)에 머지/오픈된 PR과 동일한 작업을 사용자가 지정한 다른 번들 브랜치들로 자동 cherry-pick 한 뒤 각각 PR까지 생성한다. 인자 없이 호출하면 원본 PR 번호와 타겟 번들을 순차로 묻는다.

## 사용법

```bash
/bundle-backport
/bundle-backport 1078
/bundle-backport https://github.com/getmiso/miso-native/pull/1078
/bundle-backport a1b2c3d
```

인자가 없으면 원본 PR 번호와 타겟 번들 목록을 순차 대화로 입력받아 진행한다.

인자가 있고 공백 trim 후 비어있지 않으면 Step 1의 인터랙티브 prompt를 건너뛰고 인자값을 그대로 Step 1 파서로 넘긴다 (PR 번호 / PR URL / 머지 커밋 SHA 모두 허용). 인자 모드에서 파싱이 실패하면 fail-stop (재질문 없음 — 명시적으로 인자를 전달한 사용자의 의도를 보존). 타겟 번들 선택은 인자 모드에서도 인터랙티브로 진행한다 (Step 3).

## 개요

이미 한 번들 브랜치(예: `bundle/A`)에서 작업되어 PR이 존재할 때, 동일한 작업을 다른 번들 브랜치(`bundle/B`, `bundle/C`, …)에도 반영해야 하는 경우 사용한다.

각 타겟 번들마다 다음을 수행한다.

1. 신규 cherry-pick 브랜치를 분기
2. 원본 브랜치(또는 머지 커밋)의 변경을 순서대로 cherry-pick
3. push 후 PR 생성 (원본 본문 미러링 + 출처 안내 한 줄)

## 진행 로그 및 진행 상태 업데이트 계약

오래 걸릴 수 있는 명령이므로, 각 단계의 시작/완료를 출력하고 10–15초 이상 출력이 끊기면 짧은 진행 상태 업데이트를 남긴다. 실패 시에는 실패 단계, 마지막 성공 단계, 다음 액션을 즉시 출력한다.

## 선택지 입력 컨벤션 (강제)

모든 closed-set 질문은 `AskUserQuestion` 또는 동등한 단일/다중 선택 위젯으로 제시한다. "1 또는 2 입력", "y/N" 같은 손 타이핑 요구 금지. 옵션이 위젯 한도(4개)를 초과하는 경우 다음 우선순위로 처리한다.

1. **페이지네이션 가능 여부 확인** — 후보가 명확한 순서(예: 최신→과거 버전)를 가지면 페이지네이션 위젯 루프로 처리한다. Step 3 타겟 번들 선택이 이 경로다.
2. **평문 fallback** — 페이지네이션이 부자연스러운 경우(순서 없음·총량 가변·즉시 입력이 더 빠른 경우)에만 평문 목록 + 공백 구분 텍스트 입력으로 폴백한다.

## 사전 조건

- `gh` CLI 인증 완료.
- `gh auth status`의 **active account**가 대상 저장소에 read+write 권한 보유 (PR 조회·생성 필요). 원본 PR 제목 수정은 사용자 동의 후 선택적으로 시도되며, 권한이 없으면 경고 후 "신규 backport PR에만 번들 표시 붙이는 경로"로 자동 폴백한다. 권한 전환이 필요하면 `gh auth switch --user {account}`로 전환 후 재실행.
- 원본 PR이 접근 가능 (OPEN/MERGED 모두 허용, CLOSED면 경고 후 사용자 확인).
- 타겟 번들 브랜치가 origin에 존재.

## 입력 인터랙션 (모두 순차)

### Step 0. 사전 검증 (자동)

다음을 자동 검사한다. 어느 하나라도 실패하면 즉시 fail-stop.

```bash
# 0-1. 작업 트리 clean
git status --porcelain
# → 출력이 비어있어야 함. 비어있지 않으면 사용자에게 stash/commit 안내 후 중단.

# 0-2. gh CLI 인증
gh auth status
```

### Step 1-pre. 호출 인자 처리 (자동)

스킬이 시작되면 가장 먼저 호출 인자 유무를 본다. 다음 두 분기 중 하나로 정확히 동작한다.

#### 분기 A — 인자가 있고 trim 후 비어있지 않다

1. 첫 번째 토큰을 `rawInput`으로 채택한다. 두 번째 이상의 토큰이 있으면 trace 로그에 `추가 인자 무시: {나머지}` 한 줄을 남기고 버린다.
2. `rawInput`을 Step 1의 입력값 파싱 규칙(PR 번호 / PR URL / 머지 커밋 SHA)으로 즉시 분류한다.
3. 분류 결과에 따라 메타 조회 명령을 곧바로 실행한다.
   - PR 모드: `gh pr view {N} --json ...` + `git fetch origin --prune`
   - direct SHA 모드: `git fetch origin --prune` + `git rev-parse --verify {sha}^{commit}` + `git show -s --format='%P %s' {sha}`
4. 메타 조회 결과를 Step 2 컨텍스트 표 형식으로 곧바로 출력한다. **이 출력이 분기 A에서 사용자가 보는 최초의 화면이다.**
5. 분류 또는 메타 조회가 실패하면 fail-stop. 실패 메시지에는 무엇이 실패했는지(파싱 형식 / gh 조회 / rev-parse 등)만 적고, 사용자에게 입력을 다시 받는 prompt는 만들지 않는다.

#### 분기 B — 인자가 없거나 trim 후 빈 문자열이다

1. Step 1의 인터랙티브 prompt(`> 원본 PR 번호 / URL 또는 머지 커밋 SHA를 입력해 주세요. ...`)를 출력한다.
2. 사용자 입력을 받아 Step 1 파서로 진행하고, 그 다음은 분기 A의 3~5 단계와 동일하게 메타 조회 → Step 2 표 출력 → 실패 시 fail-stop.

#### 분기 A·B 공통 규칙

- `rawInput`을 받은 시점부터 Step 2 표를 출력하기 전까지 **사용자에게 출력하는 prompt를 새로 만들지 않는다.** 분기 A에는 입력이 이미 있으므로 prompt 자체가 없어야 하고, 분기 B의 prompt는 Step 1의 한 번뿐이다.
- 잘못된 입력에 대한 사용자 확인 기회는 **Step 2 메타 표 + Step 4-C 진행/취소 위젯** 두 지점이 담당한다. Step 1-pre에서 별도의 "맞는지 확인" 단계를 추가하지 않는다.

### Step 1. 원본 입력 수집 + 메타 조회

평문 질문으로 묻는다. **PR 번호 / PR URL / 머지 커밋 SHA** 셋 다 허용한다.

> 원본 PR 번호 / URL 또는 머지 커밋 SHA를 입력해 주세요.
> 예: `1078` / `https://github.com/getmiso/miso-native/pull/1078` / `a1b2c3d`

입력값 파싱 규칙 (우선순위 순서):

- 입력이 숫자만으로 구성되면 그대로 PR 번호로 사용한다. → **PR 모드**
- 입력에 `/pull/{N}` 패턴이 포함되면 (예: `https://github.com/{owner}/{repo}/pull/1078`, 쿼리/프래그먼트 포함 가능) `{N}` 부분을 추출해 PR 번호로 사용한다. URL의 `owner/repo` 부분은 검증·사용하지 않고, PR 번호만 사용한다 (이 스킬은 현재 워킹 디렉토리의 origin 저장소를 대상으로 동작). → **PR 모드**
- 입력이 16진수 7~40자 패턴(`^[0-9a-fA-F]{7,40}$`)이면 **direct SHA 모드**로 진입한다.
  - `git rev-parse --verify <input>^{commit}`으로 검증하고 full SHA로 정규화한다. 검증 실패 시 fail-stop.
  - direct SHA 모드는 PR이 닫혔거나 처음부터 PR 없이 머지된 squash 커밋을 fan-out할 때 사용한다. 1-A·1-B는 SHA 전용 경로로 분기한다 (아래 참조).
- 어느 패턴에도 매칭되지 않으면 fail-stop하고 사용자에게 형식을 다시 안내한다.

PR 번호를 얻으면 즉시 메타를 조회하고 원격 ref를 fetch 한다. **direct SHA 모드는 `gh pr view` 호출 없이 `git fetch origin --prune`만 수행한다.**

```bash
# 1-1. PR 메타 (PR 모드에서만)
gh pr view {N} --json number,headRefName,baseRefName,title,body,state,url,mergeCommit,mergedAt,headRefOid,commits

# 1-2. 원격 ref fetch (한 번에, 양쪽 모드 공통)
git fetch origin --prune
```

PR 모드에서는 조회 결과에서 다음을 추출/판정한다.

- `headRefName` (예: `bugfix/IBP-311/base`) — 원본 브랜치
- `baseRefName` (예: `bundle/6.2604.2`) — 원본 베이스
- `title`, `body`, `state`
- `commits.length` — `MERGED + origin head 부재` 케이스에서 단일 `mergeCommit.oid`와 `refs/pull/{N}/head` fallback을 가르는 분기 기준
- 원본 브랜치명을 `{issue-type}/{issue-number}/{branch-name}` 으로 파싱

direct SHA 모드에서는 PR 메타 대신 다음만 보유한다.

- 정규화된 full SHA (`{sha}`), short SHA(앞 7자) — 표시·PR 제목용
- `git show -s --format='%P %s' {sha}` 로 `parents`(개수)와 `subject`(첫 줄)를 산출
- 1-A에서 `git branch -r --contains {sha}` 결과로 `bundle/{A-version}` 후보를 결정 (아래 1-A 참조)

#### 1-A. 베이스 검증

**PR 모드**: `baseRefName`이 `bundle/`로 시작하지 않으면 fail-stop하고 사용자에게 보고한다 (이 스킬은 번들 브랜치 backport 전용).

**direct SHA 모드**: PR 메타가 없으므로 `baseRefName`을 알 수 없다. 대신 SHA가 도달 가능한 `origin/bundle/*` 브랜치를 origin baseline 후보로 산출한다.

```bash
git branch -r --contains {sha} | sed 's/^[* ]*//' | grep -E '^origin/bundle/' | sed 's|^origin/||'
```

- 0건 → fail-stop ("이 SHA는 어떤 `origin/bundle/*`에도 포함되지 않습니다. 번들 브랜치에 머지된 커밋만 backport 가능합니다.")
- 1건 → 그 번들을 `bundle/{A-version}`(=originBundle)으로 자동 채택.
- 다건 → AskUserQuestion으로 어떤 번들을 origin baseline으로 사용할지 단일 선택. (같은 SHA가 이미 여러 번들에 cherry-pick된 상태일 수 있다.)

산출된 `bundle/{A-version}`은 이후 Step 2 표시, Step 3 후보 제외, Step 5 PR 본문 출처 안내에 모두 사용한다.

#### 1-B. cherry-pick source 결정

| 조건 | source | cherry-pick 명령 |
|---|---|---|
| `state == OPEN` 이고 `origin/{headRefName}` 가 존재 | `origin/{base}..origin/{head}` 범위 | `git cherry-pick origin/{base}..origin/{head}` |
| `state == MERGED` 이고 `origin/{headRefName}` 가 존재 | `origin/{base}..origin/{head}` 범위 | `git cherry-pick origin/{base}..origin/{head}` |
| `state == MERGED` 이고 `origin/{headRefName}` 가 존재하지 않음 + `commits.length == 1` | `mergeCommit.oid` 단일 커밋 | `git cherry-pick {mergeCommit}` (머지 커밋이면 `-m 1` 자동 부여) |
| `state == MERGED` 이고 `origin/{headRefName}` 가 존재하지 않음 + `commits.length > 1` | `refs/pull/{N}/head` 우선 fallback 후 count 재판정 (1-B-1 참조) | pull ref range count가 `> 0`이면 `git cherry-pick origin/{base}..origin/pull-{N}-head`, `0`이면 `git cherry-pick {mergeCommit}` (`parents=2`면 `-m 1`) |
| `state == CLOSED` | 사용자에게 진행 여부 재확인 후 위 규칙 적용 | — |
| **direct SHA 모드** (PR 메타 없음) | 입력 SHA 단일 커밋 | `parents>=2`면 `git cherry-pick -m 1 {sha}`, 아니면 `git cherry-pick {sha}` |
| 어느 source도 결정 불가 | fail-stop | — |

머지 커밋의 부모가 2개 이상이면 (true merge) `git cherry-pick -m 1 {sha}` 사용. 1개면 일반 cherry-pick.

체리픽 대상 커밋 수 표시:
- 범위 모드: `git rev-list --count origin/{base}..origin/{head}`
- 단일 커밋 모드: 1
- pull ref fallback 모드: `commits.length` (gh API에서 받은 값) 또는 `git rev-list --count origin/{base}..origin/pull-{N}-head`

> **주의**: cherry-pick 범위와 rev-list 범위는 반드시 `origin/` 접두사를 사용한다. `git fetch origin --prune` 직후 리모트 트래킹 ref(`refs/remotes/origin/...`)는 최신이지만 로컬 브랜치(`refs/heads/...`)는 stale하거나 부재할 수 있다 (특히 PR 머지 후 head 자동 삭제). 접두사를 빼면 cherry-pick이 실패하거나 잘못된 범위를 silently 적용할 위험이 있다.

> **빈 범위 가드**: 모든 범위 기반 cherry-pick 직전 `git rev-list --count`를 확인한다. `origin/{base}..origin/{head}` 가 `0`이면 즉시 fail-stop한다. 이는 원본 PR이 "Create a merge commit"으로 머지되고 head 브랜치가 보존된 경우(GitHub auto-delete OFF), base의 머지 커밋이 head를 두 번째 부모로 포함해 차집합이 ∅이 될 수 있기 때문이다. `origin/{base}..origin/pull-{N}-head` 가 `0`이면 empty cherry-pick을 실행하지 말고, pull ref가 이미 base에서 reachable한 create-merge 케이스로 보고 `mergeCommit.oid` 경로로 재판정한다 (`parents=2`면 `git cherry-pick -m 1 {mergeCommit.oid}`).
>
> `origin/{base}..origin/{head}` 가 `0`인 경우 사용자 메시지: "cherry-pick 범위가 비어있습니다. 원본 PR이 'Create a merge commit'으로 머지되고 head 브랜치가 보존된 경우일 수 있습니다. 머지 방식을 확인하고, 그렇다면 head 브랜치를 삭제하거나 수동으로 cherry-pick 처리해 주세요."

#### 1-B-1. `refs/pull/{N}/head` fallback (rebase-merge 안전장치)

GitHub은 PR 머지 후 head 브랜치가 삭제되어도 `refs/pull/{N}/head` ref를 영구 보존한다. 이 ref는 PR head 브랜치의 마지막 커밋(머지 직전 시점)을 가리킨다.

`state == MERGED` + origin head 부재 + `commits.length > 1` 조건에서 단순히 `mergeCommit.oid` 단일 커밋만 cherry-pick하면 머지 방식에 따라 사일런트 데이터 로스가 발생할 수 있다.

| 머지 방식 | mergeCommit.oid | 단일 cherry-pick 결과 | pull ref fallback 결과 |
|---|---|---|---|
| Squash | 압축 커밋 1개 (전체 변경 포함) | ✅ 정상 (단, 1커밋) | ✅ 원본 N커밋 그대로 적용 (추적성 더 좋음) |
| Rebase | 마지막 커밋만 가리킴 | ❌ N-1 커밋 누락 | ✅ 원본 N커밋 모두 적용 |
| Create merge | 2-parent 머지 커밋 | ✅ `-m 1`로 정상 | ⚠️ `origin/{base}..origin/pull-{N}-head` 가 `0`일 수 있으므로 empty range를 실행하지 말고 `mergeCommit.oid` 경로로 재판정 |

→ 위험 케이스(`commits.length > 1`)에서는 자동으로 pull ref를 fetch한 뒤 range count를 먼저 판정:

```bash
git fetch origin "+refs/pull/{N}/head:refs/remotes/origin/pull-{N}-head"
git rev-list --count origin/{baseRefName}..origin/pull-{N}-head
# count > 0 이면
git cherry-pick origin/{baseRefName}..origin/pull-{N}-head
# count == 0 이면 (create-merge reachability 케이스)
git cherry-pick -m 1 {mergeCommit.oid}
```

`commits.length == 1`인 경우(원본 PR이 진짜로 1커밋이었던 경우)는 머지 방식과 무관하게 `mergeCommit.oid` 단일 cherry-pick으로 충분하므로 fallback을 사용하지 않는다. `commits.length > 1`이라도 pull ref range count가 `0`이면 create-merge로 인해 pull ref가 이미 base에서 reachable한 상태일 가능성이 높으므로, 이때도 range cherry-pick 대신 `mergeCommit.oid` 경로를 사용한다.

### Step 2. 컨텍스트 확인 표시

```
| 항목                  | 값                                            |
|----------------------|-----------------------------------------------|
| 원본 PR              | #{N} ({state})                                |
| 헤드 브랜치           | {headRefName} (origin 존재: yes/no)           |
| 베이스 번들           | {baseRefName}                                 |
| 타이틀(끝)            | (bundle/{A-version}) 또는 "(없음)"            |
| Cherry-pick source   | range {base}..{head} / commit {sha}           |
| 대상 커밋 수          | N                                             |
```

**direct SHA 모드**에서는 PR 메타가 없으므로 표를 아래처럼 채운다.

```
| 항목                  | 값                                            |
|----------------------|-----------------------------------------------|
| 원본 PR              | (N/A — direct SHA)                            |
| 헤드 브랜치           | (N/A — direct SHA)                            |
| 베이스 번들           | bundle/{A-version} (git branch -r --contains) |
| 타이틀(끝)            | (해당 없음 — SHA 모드)                         |
| Cherry-pick source   | commit {short-sha} ({subject 첫 줄})           |
| 대상 커밋 수          | 1                                             |
```

### Step 2-A. 원본 PR 제목에 번들 표시 붙이기 (조건부)

> direct SHA 모드에서는 원본 PR이 없으므로 이 단계 전체를 skip한다. Step 4-A의 신규 PR 제목 베이스는 `{원본 커밋 subject} (bundle/{A-version})` 형식으로 메모리 안에서만 구성한다.

원본 PR 제목 끝이 정규식 `\s*\(bundle/[^)]+\)\s*$`와 매칭되면 이미 번들 표시가 있다는 뜻이므로 이 단계를 skip.

매칭되지 않으면 사용자에게 **실제 제목을 그대로 보여주면서** 다음과 같이 묻는다.

질문 템플릿:

> 원본 PR #{N} 제목:
> `{원본 제목}`
>
> 끝에 어느 번들 브랜치 작업인지 표시 ` (bundle/{A-version})`가 없어 backport PR들과 구분이 어렵습니다. 표시를 붙일까요?

선택지(직접 선택 위젯):

- **신규 backport PR에만 표시 추가 (Recommended)** — 원본 PR #{N}은 그대로 두고, 새로 만들 PR 제목에만 ` (bundle/{X-version})`을 붙인다.
- **원본 PR도 같이 수정** — 원본 #{N} 제목 끝에도 ` (bundle/{A-version})`을 붙인다 (원작자 알림이 갈 수 있음, 권한 필요).

처리:

- "신규 backport PR에만" 선택 → 원본은 건드리지 않고, 메모리 안에서만 ` (bundle/{A-version})`이 붙은 제목을 Step 4-A의 치환 베이스로 사용한다.
- "원본 PR도 같이 수정" 선택 → 원격 수정 시도:

  ```bash
  # 우선 시도
  gh pr edit {원본 PR 번호} --title "{원본 제목} (bundle/{A-version})"

  # GraphQL 오류 발생 시 REST API fallback
  gh api repos/{owner}/{repo}/pulls/{원본 PR 번호} --method PATCH \
    --field title="{원본 제목} (bundle/{A-version})"
  ```

  - 성공 시 변경 전/후 제목을 trace로 출력하고 Step 3으로 진행.
  - 실패 시(권한 부족 등) → **fail-stop 하지 않음**. 경고만 출력하고 위 "신규 backport PR에만" 경로와 동일하게 메모리 안 제목으로 backport를 계속 진행한다.

### Step 3. 타겟 번들 선택

```bash
git branch -r --list 'origin/bundle/*'
```

원본 베이스 번들(`bundle/{A-version}`)을 제외하고 후보 목록을 **최신 버전 내림차순**으로 정렬한다 (Step 3-A와 동일한 튜플 파싱·정렬 규칙). 정렬된 후보를 다음 규칙으로 사용자에게 묻는다.

- **후보 0개**: 사용자에게 후보 없음을 알리고 fail-stop.
- **후보 1개**: 단일 선택지(예/아니오) 위젯으로 해당 후보로 진행할지 확인.
- **후보 2–4개**: 한 번의 multiSelect 위젯으로 받는다.
- **후보 5개 이상**: 페이지네이션 위젯 루프로 받는다. 후보 개수에 의존하지 않는 동적 알고리즘이며, 후보가 몇 개로 늘어나든 동일하게 동작해야 한다.
  1. 정렬된 후보 배열을 `remaining`이라 하고, 누적 선택 결과를 `selected = []`로 초기화한다.
  2. `remaining`이 비어있지 않은 동안 다음을 반복한다.
     a. `pageSize = min(4, remaining.length)`. 첫 `pageSize`개를 떼서 `page`로 만든다.
     b. multiSelect 위젯으로 `page`를 노출한다. 라벨은 1라운드는 "타겟 번들 선택 (최신 N개)", 2라운드 이후는 "더 오래된 후보도 추가할까요? (추가하지 않으려면 아무것도 선택하지 말고 제출)"로 한다. **위젯에는 번들 후보만 노출하며, "추가 안 함" 같은 제어 옵션을 함께 두지 않는다.** (제어 옵션과 데이터 옵션을 multiSelect에 섞으면 모순 입력이 가능하고 위젯 4옵션 한도와 충돌하므로 금지.)
     c. 사용자가 고른 항목을 `selected`에 누적한다.
     d. **루프 종료 조건** (셋 중 하나라도 만족하면 즉시 종료):
        - `chosen.length === 0` (빈 선택 = 추가하지 않음 의사 표시)
        - `chosen.length < page.length` (일부만 선택 = 더 보지 않겠다는 의사 표시)
        - `chosen.length === page.length` 이지만 `remaining`이 비었음 (더 보여줄 후보 없음)
     e. 위 종료 조건에 해당하지 않으면(모두 선택 + 잔여 1개 이상) 다음 라운드로 진행.
  3. 후보 총량과 `pageSize`는 매 호출 시점에 다시 계산하므로, 후보가 향후 N개로 늘어나도 동일 알고리즘이 적용된다 (하드코딩한 라운드 수·후보 수 가정 금지).

선택 결과(또는 단일 후보 확인 결과)를 타겟 번들 배열로 확정한다. **확정된 배열이 비어있으면**(예: 페이지네이션 1라운드에서 사용자가 0개 제출, 단일 후보 yes/no 위젯에서 거절) "선택된 타겟이 없어 backport를 진행하지 않습니다."를 출력하고 즉시 fail-stop한다. Step 4 이후 단계로 진입하지 않는다 (빈 미리보기 표·공허한 결과 보고를 만들지 않기 위함).

### Step 3-A. 타겟 정렬 (역순 fan-out, 자동)

선택된 타겟 번들 배열을 **최신 버전부터 내림차순**으로 정렬한 뒤 Step 4·5·6에 그대로 사용한다.

- 각 `bundle/X.YYYY.Z` 항목을 `[X, YYYY, Z]` 숫자 튜플로 파싱한다.
- 튜플을 사전식 내림차순(major desc → year-month desc → patch desc)으로 정렬한다.
- 파싱 실패(비표준 번들명) 시 즉시 fail-stop하고 어느 번들이 패턴을 어겼는지 보고한다.

이 순서로 진행하면 누락이나 충돌이 가장 최신 번들에서 먼저 드러나, 후속 하위 번들 작업을 fail-stop으로 끊을 수 있다.

### Step 4. Preflight + 실행 계획 미리보기 + 최종 확인

#### 4-A. 신규 식별자 산출

각 타겟 `X`에 대해 다음을 계산한다.

- 신규 브랜치명: **원본 브랜치 base**의 마지막 segment 앞에 `{X-version}-` 삽입
  - PR 모드의 원본 브랜치 base = `headRefName` 그대로
  - direct SHA 모드의 원본 브랜치 base = 아래 **4-A-1**에서 derive
  - 예: `bugfix/IBP-311/base` + `6.2603.1` → `bugfix/IBP-311/6.2603.1-base`
  - 예: `feature/IBP-319/settlement-tax-fields` + `6.2604.3` → `feature/IBP-319/6.2604.3-settlement-tax-fields`
- 신규 PR 제목: 번들 표시가 붙은 원본 제목의 ` (bundle/{A-version})` 부분을 ` (bundle/{X-version})`으로 치환

#### 4-A-1. direct SHA 모드의 원본 브랜치 base derive

PR 모드와 달리 `headRefName`이 없으므로, commit subject를 1차 시도하고 실패 시 폴백 후 사용자 확인을 받는다.

1. **1차 시도 — subject prefix 파싱**: commit subject 시작에 `^\[(?<type>[A-Za-z]+)/(?<id>[A-Z]+-\d+)\]` 패턴 매칭.
   - 매칭되면: derived base = `{type-소문자}/{id}/base`
   - 예: `[Bugfix/IBP-311] 결제 실패 토스트 누락 수정 (bundle/6.2604.2)` → `bugfix/IBP-311/base`
   - 예: `[Chore/PRD-6330] /bundle-backport 개선 (#1234)` → `chore/PRD-6330/base`
2. **2차 폴백 — 파싱 실패 시**: derived base = `backport/sha-{short-sha}/base`
   - 예: `a1b2c3d` → `backport/sha-a1b2c3d/base`
3. **사용자 확인** (`AskUserQuestion`): commit subject 전문과 derived base를 함께 표시하고 단일 선택지 제시.
   - **"이대로 사용 (Recommended)"** → derived base를 확정.
   - **"수정"** → 자유 입력으로 사용자가 base를 지정 (`{type}/{id}/base` 형식 권장, 끝이 `/base` 아니어도 허용).
4. 확정된 derived base는 PR 모드의 `headRefName` 자리에 그대로 들어가 위 4-A 본 규칙(마지막 segment 앞에 `{X-version}-` 삽입)에 적용된다.
   - 예: derived `bugfix/IBP-311/base` + X=6.2603.1 → `bugfix/IBP-311/6.2603.1-base`
   - 예: derived `backport/sha-a1b2c3d/base` + X=6.2603.1 → `backport/sha-a1b2c3d/6.2603.1-base`

#### 4-B. 충돌 사전 점검

각 타겟별로 아래 3가지를 점검한다.

```bash
# 1) 로컬 브랜치 존재 여부
git rev-parse --verify --quiet {신규 브랜치명}

# 2) 원격 브랜치 존재 여부
git ls-remote --heads origin {신규 브랜치명}

# 3) 동일 head로 열린 PR 존재 여부
gh pr list --head {신규 브랜치명} --state all --json number,state
```

타겟별 상태(`status`)를 산출:
- `clean`: 모두 존재하지 않음 → 정상 진행 가능
- `local-exists`: 로컬 브랜치만 존재
- `remote-exists`: 원격 브랜치 존재
- `pr-exists`: 같은 head로 PR이 이미 있음

#### 4-C. 미리보기 + 충돌 처리

```
| 타겟 번들          | 신규 브랜치                                | PR 타이틀(끝)        | 상태               |
|-------------------|-------------------------------------------|---------------------|-------------------|
| bundle/{X1-ver}   | {issue-type}/{issue-num}/{X1}-{branch}    | (bundle/{X1-ver})   | clean             |
| bundle/{X2-ver}   | ...                                        | ...                 | pr-exists (#NNNN) |
```

`clean`이 아닌 타겟이 1개 이상이면 사용자에게 직접 단일 선택지를 제시한다:
- **충돌 타겟 skip 후 진행 (Recommended)**: clean 타겟만 진행
- **전체 취소**: fail-stop

전부 `clean`이면 단일 선택지(`진행 / 취소`)만 묻는다.

### Step 5. 실행 (clean 타겟 대상, 순차)

각 clean 타겟 `X`에 대해 아래를 순서대로 수행한다. **fail-stop**: 어느 한 단계라도 실패하면 즉시 전체 중단하고 사용자에게 보고한다. 남은 타겟은 진행하지 않는다.

#### 5-1. 베이스 최신화

```bash
git checkout bundle/{X-ver}
git pull --ff-only origin bundle/{X-ver}
```

#### 5-2. 신규 브랜치 생성

```bash
git checkout -b {신규 브랜치명}
```

(Step 4-B에서 `clean`으로 판정된 타겟만 여기 도달함.)

#### 5-3. 체리픽

Step 1-B에서 결정한 source에 따라:

```bash
# 범위 모드
git cherry-pick origin/{원본 base}..origin/{원본 head}

# 단일 커밋 모드 (머지 커밋, parents=2일 때)
git cherry-pick -m 1 {mergeCommit.oid}

# 단일 커밋 모드 (squash 머지 또는 원본이 1커밋이었던 경우)
git cherry-pick {mergeCommit.oid}

# pull ref fallback 모드 (MERGED + origin head 부재 + commits.length > 1)
git fetch origin "+refs/pull/{원본 PR 번호}/head:refs/remotes/origin/pull-{원본 PR 번호}-head"
git rev-list --count origin/{원본 base}..origin/pull-{원본 PR 번호}-head
# count > 0 이면
git cherry-pick origin/{원본 base}..origin/pull-{원본 PR 번호}-head
# count == 0 이면 (create-merge reachability 케이스)
git cherry-pick -m 1 {mergeCommit.oid}
```

- author 보존(git 기본 동작) — committer만 현재 사용자로 기록.
- 충돌 발생 시 → **자동 abort 후 즉시 전체 중단**:

  ```bash
  # 1. working tree 복구 (충돌 마커, CHERRY_PICK_HEAD 제거)
  git cherry-pick --abort
  # 2. 사용자에게 보고: 충돌 파일 목록, git status 출력, abort 완료 사실
  ```

  `--abort`를 수행하지 않으면 working tree에 충돌 마커 + `.git/CHERRY_PICK_HEAD`가 남아 다음 실행 시 Step 0의 `git status --porcelain` 검사가 실패하고, 일반적인 stash/commit 안내로는 복구가 불가능해 스킬이 재실행 불가 상태에 빠진다. `cherry-pick --abort`는 아직 기록되지 않은 cherry-pick 시도를 되돌리는 것이라 destructive 동작이 아니다 (커밋·푸시·브랜치 삭제 같은 영구 변경 없음).

  abort 이후 5-2에서 만든 신규 브랜치는 그대로 남는다. 사용자가 재실행하면 Step 4-B에서 `local-exists`로 잡혀 skip 또는 abort 선택지가 제시된다.
- `--strategy-option=theirs/ours` 등 자동 해결 옵션 사용 금지.

#### 5-4. 푸시

```bash
git push -u origin {신규 브랜치명}
```

- Husky pre-push 검사 자동 실행.
- **실패 시 → 즉시 전체 중단**, 에러 로그 그대로 보고.
- `--no-verify`, `HUSKY=0`, `SKIP_HUSKY=1` 등 우회 절대 금지.

#### 5-5. PR 생성

원본 본문 최상단에 출처 안내 한 줄을 삽입해 stdin으로 바로 전달한다 (임시 파일 미사용 — cleanup 의무 없음).

**PR 모드**:

```bash
{
  printf '> 🔁 This PR mirrors #%s for bundle/%s.\n\n' "{원본 PR 번호}" "{X-ver}"
  gh pr view {원본 PR 번호} --json body --jq .body
} | gh pr create \
  --base bundle/{X-ver} \
  --head {신규 브랜치명} \
  --title "{치환된 신규 타이틀}" \
  --body-file -
```

**direct SHA 모드**:

원본 PR이 없으므로 출처 안내 한 줄을 SHA 형식으로 변형하고, 본문 자리에는 커밋 메시지 전문(`git show -s --format=%B`)을 사용한다.

```bash
{
  printf '> 🔁 This PR mirrors commit %s from bundle/%s.\n\n' "{short-sha}" "{A-version}"
  git show -s --format=%B {sha}
} | gh pr create \
  --base bundle/{X-ver} \
  --head {신규 브랜치명} \
  --title "{치환된 신규 타이틀}" \
  --body-file -
```

PR URL을 결과 배열에 누적한다.

### Step 6. 결과 보고

```
| 타겟 번들          | 상태                  | 신규 브랜치              | PR URL                          |
|-------------------|----------------------|-------------------------|---------------------------------|
| bundle/{X1-ver}   | created              | {신규 브랜치 1}          | https://github.com/.../pull/... |
| bundle/{X2-ver}   | skipped (pr-exists)  | -                       | (existing #NNNN)                |
| bundle/{X3-ver}   | failed (push)        | {신규 브랜치 3}          | -                               |
```

성공/스킵/실패를 모두 구분하여 정리한다.

## 안전 수칙 (강제)

- **fail-stop**: 단계 실패 시 전체 중단. 후속 타겟 진행 금지.
- **author 보존**: `git cherry-pick` 기본 동작 유지.
- **Husky 우회 금지**: `--no-verify`, `HUSKY=0`, `SKIP_HUSKY=1` 등 사용 금지.
- **Destructive 동작 금지**: `git push --force`, `git reset --hard`, 브랜치 강제 삭제 등 금지. (단, cherry-pick 충돌 시 `git cherry-pick --abort`는 destructive 아님 — 아직 기록되지 않은 시도를 되돌리는 것이므로 허용·필수.)
- **추측 금지**: 충돌 자동 해결, 자동 머지 전략 적용 금지.
- **본문 변형 금지**: 출처 안내 한 줄을 제외하면 원본 본문(또는 SHA 모드의 커밋 메시지)은 그대로 미러링.
- **사전 검증 우회 금지**: Step 0/1-A/4-B 검증을 임의 생략 금지.
- **SHA 경로 베이스 매칭**: `git branch -r --contains` 결과의 `origin/bundle/*` ref만 사용 (로컬 ref 사용 금지). 결과가 0건이면 fail-stop.

## 산출물 요약

- 타겟 N개 × {신규 브랜치 1개 + PR 1개} (skip 제외, Step 3-A에서 정렬한 최신 번들부터 역순으로 실행)
- 모든 PR 본문:
  - PR 모드: `> 🔁 This PR mirrors #{원본} for bundle/{X-ver}.\n\n` + 원본 PR 본문
  - direct SHA 모드: `> 🔁 This PR mirrors commit {short-sha} from bundle/{A-version}.\n\n` + `git show -s --format=%B {sha}`
- 모든 PR 제목 = 번들 표시가 붙은 원본 제목의 번들 버전만 치환 (SHA 모드는 `{원본 커밋 subject} (bundle/{X-version})` 형식)

## 사용 예시 (참고)

원본 PR `#1078` (헤드: `bugfix/IBP-311/base`, 베이스: `bundle/6.2604.2`, 상태: MERGED, 타이틀: `[Bugfix/IBP-311] 결제 실패 토스트 누락 수정`)을 `bundle/6.2603.1`, `bundle/6.2604.3`로 backport 하는 흐름이다.

```
사용자: /bundle-backport

[Step 0] 사전 검증
  - git status --porcelain → clean ✅
  - gh auth status → ok ✅

[Step 1] 원본 PR 번호 또는 URL을 입력해 주세요.
        예: 1078 또는 https://github.com/getmiso/miso-native/pull/1078
사용자: https://github.com/getmiso/miso-native/pull/1078
  → URL의 /pull/1078에서 PR 번호 1078 추출

[Step 1] 메타 조회 + fetch
  - state: MERGED, headRefName: bugfix/IBP-311/base, baseRefName: bundle/6.2604.2
  - origin/bugfix/IBP-311/base 존재 → range 모드 (base..head, 3 커밋)

[Step 2] 컨텍스트
  | 항목                | 값                                      |
  |--------------------|------------------------------------------|
  | 원본 PR            | #1078 (MERGED)                           |
  | 헤드 브랜치        | bugfix/IBP-311/base (origin: yes)        |
  | 베이스 번들        | bundle/6.2604.2                          |
  | 제목 끝 표시        | "(없음)" → 번들 표시 추가 필요           |
  | Cherry-pick source | range origin/bundle/6.2604.2..origin/bugfix/IBP-311/base |
  | 대상 커밋 수       | 3                                        |

[Step 2-A] 원본 PR 제목에 번들 표시 붙이기
  - 끝에 (bundle/...) 표시 없음 → 사용자에게 묻기 (AskUserQuestion 위젯):

    원본 PR #1078 제목:
      [Bugfix/IBP-311] 결제 실패 토스트 누락 수정
    끝에 어느 번들 작업인지 표시 ' (bundle/6.2604.2)'가 없어 backport PR들과 구분이 어렵습니다. 표시를 붙일까요?
      • 신규 backport PR에만 표시 추가 (Recommended)
      • 원본 PR도 같이 수정

  사용자: "신규 backport PR에만 표시 추가" 선택
  - → 원본 PR #1078은 그대로 유지, 신규 PR 제목만 (bundle/{X-version}) 붙여서 만든다

[Step 3] 타겟 번들 선택
  후보 3개 (원본 베이스 제외), 최신순:
    - bundle/6.2605.1
    - bundle/6.2604.3
    - bundle/6.2603.1
  → 4개 이하이므로 한 번의 multiSelect 위젯으로 묻기
  사용자: bundle/6.2603.1, bundle/6.2604.3 선택

[Step 3 (대안 예시) — 후보 6개일 때 페이지네이션]
  후보는 매번 origin/bundle/* 에서 동적으로 산출하므로 개수는 가변이다. 아래는 6개일 때의 동작 예시일 뿐이며, 알고리즘 자체는 N개에 대해 동일하게 적용된다.

  후보 6개 (원본 베이스 제외), 최신순:
    bundle/6.2605.2, bundle/6.2605.1, bundle/6.2604.3, bundle/6.2604.2, bundle/6.2604.1, bundle/6.2603.1

  라운드 1: pageSize=min(4, 6)=4 → 상위 4개 multiSelect (6.2605.2 / 6.2605.1 / 6.2604.3 / 6.2604.2)
    - 케이스 ①: 사용자가 2개만 선택 → 일부 선택이므로 즉시 종료
    - 케이스 ②: 사용자가 0개 선택 (빈 제출) → 종료 (= "추가 안 함" 의사)
    - 케이스 ③: 사용자가 4개 모두 선택 → 다음 라운드 진입
        라운드 2: pageSize=min(4, 2)=2 → 남은 2개 multiSelect (6.2604.1 / 6.2603.1).
                  라벨에 "추가하지 않으려면 아무것도 선택하지 말고 제출"을 명시.
          - 0개 선택 → 라운드 1 결과만 확정하고 종료
          - 1개만 선택 → 종료
          - 2개 모두 선택 → remaining=0이므로 종료

  후보가 9개라면: 라운드 1(4) → 모두 선택 시 라운드 2(4) → 모두 선택 시 라운드 3(1). 알고리즘 변경 없이 자동 확장.

[Step 3-A] 타겟 정렬 (자동)
  입력 순서: bundle/6.2603.1 bundle/6.2604.3
  정렬 후 실행 순서: bundle/6.2604.3 → bundle/6.2603.1 (역순)

[Step 4] 미리보기
  | 타겟              | 신규 브랜치                          | PR 타이틀(끝)        | 상태   |
  |-------------------|--------------------------------------|---------------------|--------|
  | bundle/6.2604.3   | bugfix/IBP-311/6.2604.3-base         | (bundle/6.2604.3)   | clean  |
  | bundle/6.2603.1   | bugfix/IBP-311/6.2603.1-base         | (bundle/6.2603.1)   | clean  |
  → 진행 / 취소? : 진행

[Step 5] 실행 (역순, 순차, fail-stop)
  bundle/6.2604.3 (최신 번들부터)
    ✅ pull --ff-only
    ✅ checkout -b bugfix/IBP-311/6.2604.3-base
    ✅ cherry-pick origin/bundle/6.2604.2..origin/bugfix/IBP-311/base (3 커밋)
    ✅ push -u origin (Husky pre-push 통과)
    ✅ gh pr create → https://github.com/.../pull/2002
  bundle/6.2603.1
    ... 동일 ...
    ✅ gh pr create → https://github.com/.../pull/2001

[Step 6] 결과
  | 타겟              | 상태     | 신규 브랜치                    | PR URL                          |
  |-------------------|----------|--------------------------------|---------------------------------|
  | bundle/6.2604.3   | created  | bugfix/IBP-311/6.2604.3-base   | https://github.com/.../pull/2002 |
  | bundle/6.2603.1   | created  | bugfix/IBP-311/6.2603.1-base   | https://github.com/.../pull/2001 |
```

이 예시는 동작 이미지를 잡기 위한 참고용이며, 실제 출력 형식은 단계별 규약과 일치하면 된다.
