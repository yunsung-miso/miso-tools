---
name: release-to-main
description: 릴리즈 태그(v{version})의 GitHub 릴리즈 노트 하단 "test app" 섹션을 CI 로그에서 추출한 빌드번호/링크로 최신화하고, release/{version} → main 병합 PR을 생성. "릴리즈 노트 최신화", "release to main PR", "릴리즈 빌드번호 채워줘", "릴리즈 마무리" 같은 요청에 사용.
---

# Release to Main Skill

릴리즈 마무리 2종 세트를 자동화한다:

1. **릴리즈 노트 최신화** — GitHub 릴리즈 노트 하단 `## test app` 섹션을 채운다. 빌드번호·Firebase 링크는 CI 릴리즈 런 로그에서 추출하고, iOS TestFlight 링크와 staging 값만 사용자에게 입력받는다.
2. **release → main PR 생성** — `Release/{version} to main` 컨벤션으로 PR을 만든다 (예: PR #1332).

릴리즈 GitHub Action(`.github/workflows/release.yml`)이 만든 노트는 changelog만 있고 빌드 정보(`test app` 섹션)가 없어서, 그 부분을 사람이 채워야 한다. 이 스킬이 그 수작업을 대체한다.

## 입력

- `version`: 릴리즈 버전 (예: `6.2605.2`). 태그는 `v{version}`.
- 사용자에게 받아야 하는 값:
  - iOS production TestFlight 링크
  - iOS staging TestFlight 링크
  - (선택) staging 빌드번호 — store 릴리즈 런에는 없음 (아래 "staging 처리" 참고)

App Store Connect의 TestFlight 빌드 UUID는 CI 로그에 없으므로 **반드시 사용자에게 받는다.** 없이 진행하지 말 것.

## 자동 추출 가능 / 불가능 정리

| 값 | 출처 | 자동? |
|----|------|------|
| version | 태그 이름 | ✅ |
| commit (8자) | `git rev-parse --short=8 v{version}` | ✅ |
| iOS build number | 릴리즈 런 iOS Build 잡 로그 `generated_build_number:` | ✅ |
| Android versionCode | 릴리즈 런 Android Build 잡 로그 `created release {version} (NNNN)` | ✅ |
| Firebase 콘솔 링크 | 같은 로그의 다운로드 URL `releases/{releaseId}/binaries` | ✅ |
| iOS TestFlight 링크 | App Store Connect (로그에 없음) | ❌ 사용자 입력 |

## 절차

### 1. 사실 수집

```bash
# 태그 페치 + 커밋/버전 확인
git fetch --tags -q
git rev-parse --short=8 "v{version}"        # commit
git show "v{version}:packages/host/android/app/build.gradle" | grep versionName
```

### 2. 릴리즈 런과 빌드 잡 ID 찾기

```bash
# 해당 태그의 release 워크플로우 런 — 재시도가 있으면 여러 개 매칭되므로
# 최신(맨 위) 1개의 databaseId 만 안전하게 추출
gh run list --workflow=release.yml --limit 10 \
  --json databaseId,headBranch,conclusion \
  -q '[.[] | select(.headBranch=="v{version}")][0].databaseId'

# 그 런의 iOS / Android Build 잡 ID
gh run view {runId} --json jobs \
  -q '.jobs[] | select(.name|test("iOS Build|Android Build")) | "\(.databaseId)\t\(.name)"'
```

### 3. 빌드번호 / Firebase 링크 추출 — ⚠️ `gh api` 로그 엔드포인트 사용

> **중요 (검증된 함정):** `gh run view --job {id} --log`는 셋업 단계(~2800줄)에서 **잘려서** fastlane 출력이 안 나온다. 반드시 raw 로그 API를 써야 fastlane 빌드번호 줄(전체 ~3900줄, 40MB)이 나온다.

```bash
# iOS build number — stderr 는 살려둔다 (토큰 만료·권한·잘못된 Job ID 같은
# 실패를 "로그가 비었다"로 오판하지 않도록)
gh api /repos/getmiso/miso-native/actions/jobs/{iosJobId}/logs \
  | grep -oE 'generated_build_number: [0-9]+' | head -1
# → generated_build_number: 260527134300

# Android versionCode + Firebase releaseId
gh api /repos/getmiso/miso-native/actions/jobs/{androidJobId}/logs \
  | grep -E 'created release|releases/[a-z0-9]+/binaries' | head -5
# → "✅ Uploaded APK successfully and created release 6.2605.2 (2411)."
# → 다운로드 URL의 .../releases/2qqi1ibhh7aqg/binaries/... 에서 releaseId 추출
```

- Android versionCode: `created release {version} (NNNN)` 의 `NNNN`. (`new versionCode:` 줄은 여러 개 나오니 쓰지 말 것 — 마지막에 `1`로 찍히는 노이즈가 있음.)
- Firebase 콘솔 링크 조립: appId `1:477634197864:android:46092ffd91a1e44f`, releaseId는 위에서 추출.
  `https://appdistribution.firebase.google.com/testerapps/{appId}/releases/{releaseId}?utm_source=firebase-console`

### 4. staging 처리

`release.yml`의 host-build는 `stage: store`(production) **전용**이라 staging 빌드는 이 런에 없다. staging 값은:

- staging 빌드 런(별도)에서 같은 방식으로 추출하거나,
- 사용자에게 받거나,
- 값을 모르면 `(빌드번호)` 플레이스홀더로 두고 노트에 명시한다.

TestFlight/Firebase 링크는 보통 사용자가 준다.

### 5. 릴리즈 노트 최신화 — ⚠️ changelog 보존

> **중요 (검증된 사고):** 기존 본문을 `sed` 파이프로 자르다 실패하면 changelog(`## What's Changed`)가 통째로 날아간다. 안전 절차를 따를 것.

안전 절차:

1. 현재 본문을 파일로 받는다: `gh release view v{version} --json body -q .body > /tmp/rel_body.md`
2. `## test app` 직전(`---` 포함)부터 끝까지 잘라낸다. **fragile 한 `sed`/정규식 대신** 아래 Python 원라이너를 그대로 쓴다 (마커가 없으면 원본 유지):

   ```bash
   python3 - <<'PY'
   p = '/tmp/rel_body.md'
   b = open(p).read()
   if '## test app' in b:
       head = b.split('## test app')[0].rsplit('---', 1)[0].rstrip()
       open(p, 'w').write(head + '\n')
   PY
   ```
3. 잘라낸 결과에 `## What's Changed`가 **여전히 있는지 반드시 확인** 후 진행 (없으면 멈추고 본문을 다시 받는다).
4. 아래 섹션을 이어붙인다 (값 치환).
5. `gh release edit v{version} --notes-file /tmp/rel_body.md`
6. `gh release view v{version} --json body -q .body | head -5` 로 changelog가 살아있는지 확인.

`test app` 섹션 템플릿 (이전 릴리즈 v6.2605.1 / v6.2604.3 와 동일 포맷):

```markdown

---

## test app

### (1) production
- android
  - version : **{version} ({androidCode})**
  - commit : {commit}
  - note: Release v{version} ([firebase]({androidProdFirebaseUrl}))
- ios
  - version : **{version} ({iosBuild})**
  - commit : {commit}
  - note : "Release v{version}" ([testflight]({iosProdTestflightUrl}))


### (2) staging
- android
  - version : **{version} ({androidStagingCode})**
  - commit : {commit}
  - note: Release v{version} ([firebase]({androidStagingFirebaseUrl}))
- ios
  - version : **{version} ({iosStagingBuild})**
  - commit : {commit}
  - note : "v{version} staging" ([testflight]({iosStagingTestflightUrl}))
```

### 5-A. 번들 누락 점검

`bundle-release-status` 스킬의 gaps 판정을 release 브랜치 기준으로 실행해, 직전 번들 작업 중 이번 릴리즈에 미수록된 것을 적발한다.

```bash
git fetch origin --prune --tags -q
# 직전 번들 = 현재 릴리즈 버전({version})보다 낮은 번들 중 최신.
# release-branch-cut 이 release/X 와 bundle/X 를 동시에 만들므로,
# 자기 자신({version})이나 더 높은 번들을 고르면 안 된다.
# {version}을 목록에 끼워 sort -V 한 뒤 바로 앞 항목을 택하면, {version}이
# 번들 목록에 없어도(삭제/미생성) 항상 {version} 미만의 직전 번들이 잡힌다.
# {version}이 최소면 앞 항목이 없어 자기 자신이 잡히고, 아래 guard 에서 skip.
PREV_BUNDLE=$( { git branch -r --list 'origin/bundle/*' | sed 's|.*origin/bundle/||'; echo "{version}"; } \
  | sort -V | uniq | grep -B1 -xF "{version}" | head -1)

if [ -z "$PREV_BUNDLE" ] || [ "$PREV_BUNDLE" = "{version}" ]; then
  echo "직전 번들 없음 — 번들 점검 skip (첫 릴리즈이거나 비교 대상 번들 부재)"
else
  V="v${PREV_BUNDLE}"; B="origin/bundle/${PREV_BUNDLE}"
  if ! git rev-parse --verify -q "$V" >/dev/null; then
    echo "기준 태그 ${V} 없음 — 번들 점검 skip"
  else
    # patch-id 미수록 후보
    git cherry "origin/release/{version}" "$B" "$V" | awk '$1=="+" {print $2}' > /tmp/gap_candidates.txt

    # 제목 매칭으로 2차 필터 (정규화 규칙은 bundle-release-status 스킬과 동일)
    git log --no-merges --format='%s' "origin/release/{version}" origin/main --not "$V" \
      | sed -E 's/( \(#[0-9]+\))+$//; s/ \((bundle|release)\/[0-9.]+\)//g; s/^[[:space:]]+//; s/[[:space:]]+$//' | sort -u > /tmp/upstream_titles.txt

    # 후보를 git log --no-walk 로 한 번에 받아 Python 으로 일괄 필터 (프로세스 포크 제거).
    # 정규화 규칙은 upstream_titles 의 sed 와 동일해야 한다.
    if [ -s /tmp/gap_candidates.txt ]; then
      git log --no-merges --no-walk --format='%H%x09%s' $(cat /tmp/gap_candidates.txt) | python3 -c '
import sys, re
with open("/tmp/upstream_titles.txt") as f:
    upstream = set(l.rstrip("\n") for l in f)
def normalize(t):
    t = re.sub(r"( \(#[0-9]+\))+$", "", t)
    t = re.sub(r" \((bundle|release)/[0-9.]+\)", "", t)
    return t.strip()
for line in sys.stdin:
    line = line.rstrip("\n")
    if not line:
        continue
    sha, title = line.split("\t", 1)
    if normalize(title) not in upstream:
        print(sha[:7] + "\t" + title)
' > /tmp/gaps.txt
    else
      : > /tmp/gaps.txt
    fi

    echo "직전 번들: bundle/${PREV_BUNDLE}, 누락 $(wc -l < /tmp/gaps.txt)건"
  fi
fi
```

merge 커밋은 `git cherry`가 원래 제외하므로 별도 처리 불필요. 결과는 6번 PR 본문의 "번들 누락 점검" 섹션에 들어간다.

### 6. release → main PR 생성

- base: `main`
- head: `release/{version}`
- title: `Release/{version} to main`
- body: 머지 승인자가 어떤 빌드인지 한눈에 보도록 step 1–4 에서 모은 데이터(버전/커밋/빌드번호/배포 링크)를 본문에 같이 박는다. 16-PR-컨벤션.md 의 자연스러운 구어체 톤을 따른다.

본문 템플릿 (값 치환):

```markdown
## 출시 내용

`release/{version}` 을 `main` 에 병합합니다. iOS / Android 모두 앱 심사 제출과 출시까지 마쳤어요.

## 빌드 정보

| | iOS | Android |
|---|---|---|
| production | `{version} ({iosBuild})` · [TestFlight]({iosProdTestflightUrl}) | `{version} ({androidCode})` · [Firebase]({androidProdFirebaseUrl}) |
| staging | `{version} ({iosStagingBuild})` · [TestFlight]({iosStagingTestflightUrl}) | `{version} ({androidStagingCode})` · [Firebase]({androidStagingFirebaseUrl}) |

commit: [`{commit}`](https://github.com/getmiso/miso-native/commit/{commit})

## 번들 누락 점검

bundle/{직전버전} 작업의 release/{version} 수록 여부 (patch-id + 제목 매칭):

✅ 누락 없음 — 번들 작업 전부 수록 확인

## 참고

- [v{version} 릴리즈 노트](https://github.com/getmiso/miso-native/releases/tag/v{version}) — 이번에 들어간 PR 목록·새 컨트리뷰터 등 자세한 변경사항
```

누락이 있으면 "번들 누락 점검" 섹션을 아래로 대체한다 (5-A의 `/tmp/gaps.txt` 기반):

```markdown
## 번들 누락 점검

bundle/{직전버전} 작업의 release/{version} 수록 여부 (patch-id + 제목 매칭):

❌ 누락 {N}건 — 머지 전 forward-port 여부를 결정해 주세요:

| 커밋 | 제목 |
|---|---|
| {sha7} | {title} |
```

```bash
# 본문을 먼저 파일로 만든다 (--body 인라인은 줄바꿈/백틱/파이프 escaping 이슈가 있어
# 레포 컨벤션상 --body-file 사용)
cat > /tmp/release_pr_body.md <<'BODY'
... (위 템플릿을 값 치환해서 그대로 붙여넣음)
BODY

# release 브랜치가 push 되어 있는지 확인 후
gh pr create --base main --head "release/{version}" \
  --title "Release/{version} to main" \
  --body-file /tmp/release_pr_body.md
```

이미 PR이 있으면 새로 만들지 말고 같은 본문으로 **갱신**한다:

```bash
gh api /repos/getmiso/miso-native/pulls/{prNumber} --method PATCH \
  --field body=@/tmp/release_pr_body.md --jq '.html_url'
```

(`gh pr edit` 는 GraphQL deprecation 이슈가 있어 REST PATCH 사용.)

## 가드레일

- iOS TestFlight 링크를 추측/생성하지 말 것 — 사용자 입력 필수.
- 릴리즈 노트 편집 시 changelog(`## What's Changed`) 보존 검증 필수 (5번 절차).
- 빌드번호 추출은 `gh api .../jobs/{id}/logs` 사용 — `gh run view --log`는 잘림.
- PR 본문은 한글. release→main PR은 `Release/{version} to main` 포맷 고정.
- 값이 비면 `(빌드번호)` 플레이스홀더를 남기고 무엇이 비었는지 사용자에게 명시.
- 번들 누락 점검(5-A)을 건너뛰고 PR을 만들지 말 것 — 누락이 있으면 본문에 표로 명시하고 머지 판단은 사람에게 맡긴다.
