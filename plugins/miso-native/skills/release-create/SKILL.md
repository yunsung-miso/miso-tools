---
name: release-create
description: 머지된 release/{version} 브랜치 기준으로 v{version} 태그를 main 머지 커밋에 두고 GitHub Release를 자동 생성(기본 publish). test app 섹션의 빌드 번호/TestFlight 링크 placeholder는 사후 edit으로 채움. `--draft` 옵션으로 draft 생성도 가능.
---

# Release Create Skill

릴리즈 브랜치가 main으로 머지된 직후, **v{version} 태그를 main 머지 커밋에 만들어 push** 함으로써 `release.yml`(host store submit + remote deploy)을 트리거하고, 동시에 그 버전의 GitHub Release 노트를 자동 생성/publish 하는 스킬.

## 핵심 목적

1. **태그 push로 출시 워크플로우 발화** — `release.yml`은 `push: tags: v[0-9]*` 트리거이므로, 태그 push가 곧 출시 액션 발화.
2. **Release 노트 생성** — `.github/release.yml` 카테고리화 + `.github/release-template.md` 적용한 body를 자동 생성.
3. 두 작업을 한 흐름으로 묶어, 출시 담당자가 빌드/배포/노트를 따로 챙기지 않게 함.

## When to use

- `release/{version}` 브랜치가 `main`에 머지된 직후, **출시 액션(store submit + remote deploy)을 발화시키고 싶을 때**
- 이미 만들어진 태그가 잘못된 commit을 가리키고 있어서 main 머지 커밋으로 정렬해야 할 때 (이미 출시가 끝난 후 단순 정렬이라면 워크플로우 재실행 부작용 확인 필수)

## Pre-flight Checks

1. **PR 머지 확인**: `gh pr view <pr> --json mergeCommit,state,baseRefName` — state는 MERGED, baseRefName은 main이어야 함.
2. **머지 커밋 확인**: PR의 mergeCommit SHA를 메인 타깃 커밋으로 사용.
3. **태그 정합성**:
   - 태그 commit이 Android `versionName`과 iOS `MARKETING_VERSION`에 일치해야 release.yml validate 통과 → 만약 태그 commit이 main에 없거나 정합성 안 맞으면 build 실패.
   - 일반적으로 머지 커밋(main에 올라간 직후)을 태그 위치로 쓰면 안전.
4. **이전 태그 확인**: `git tag --sort=-creatordate | head -5` 로 직전 버전 태그 확인 (compare URL용).

## Step-by-Step Flow

### 1. 기본 변수 수집

```bash
PR_NUMBER=<릴리즈 머지 PR 번호>
VERSION=<릴리즈 버전, 예: 6.2605.1>
TAG="v${VERSION}"

# main 머지 커밋 추출
MERGE_COMMIT=$(gh pr view $PR_NUMBER --json mergeCommit --jq '.mergeCommit.oid')
COMMIT_SHORT="${MERGE_COMMIT:0:8}"
```

`PREV_TAG` 는 Step 3 에서 계산 — 태그 생성 후가 시점적으로 정확함.

### 2. 태그 생성/이동 + push (출시 액션 발화)

이 단계가 **스킬의 핵심**. 태그 push 가 `release.yml` 을 트리거해서 host store submit + remote deploy 가 돌아감.

```bash
# 로컬에서 태그 만들기 (또는 이미 있으면 머지 커밋으로 옮기기)
git fetch --tags origin
git tag -f "$TAG" "$MERGE_COMMIT"

# 원격 푸시 → release.yml 발화
rtk proxy git push origin "$TAG" --force
# (RTK 없는 환경이면 일반 git push origin "$TAG" --force)
```

push 후 GitHub Actions 에서 `Release` 워크플로우 run을 확인:

```bash
gh run list --workflow=release.yml --limit 1
```

⚠️ **이미 출시가 끝난 버전을 단순히 정렬하는 경우** (예: 태그를 release tip 에서 머지 커밋으로 옮기기): 재실행을 원치 않으면 force-push 직후 새 run 을 즉시 cancel 하거나 `concurrency` 그룹이 cancel 하도록 둘 것. 절대 hook bypass 금지.

### 3. 직전 릴리즈 태그 계산 (compare URL 용)

태그 생성 후, 새 태그를 제외한 가장 최신 정식 릴리즈 태그를 찾음. 새 태그가 sort 결과 최상위에 있으므로 두 번째 항목이 직전 태그.

```bash
PREV_TAG=$(git tag --sort=-version:refname | grep '^v[0-9]' | grep -v 'rc' | head -2 | tail -1)
```

> 만약 Step 2 를 건너뛰고 release 만 다시 만드는 케이스라면 (드물지만), 위 명령은 현재 태그가 아닌 그 이전 태그를 반환하므로 의도와 다름. 이 경우 `PREV_TAG` 를 수동 지정.

### 4. Auto-generate release notes

`.github/release.yml` 카테고리화 설정이 적용된 changelog를 GitHub API로 생성.

```bash
AUTO_NOTES=$(gh api -X POST repos/:owner/:repo/releases/generate-notes \
  -f tag_name="$TAG" \
  -f previous_tag_name="$PREV_TAG" \
  -f target_commitish="$MERGE_COMMIT" \
  --jq '.body')
```

### 4-A. OTA 선출시 항목 표시

AUTO_NOTES의 PR 항목 중 이미 `ota/*` 태그로 유저에게 나간 작업(번들 forward-port)에 출처를 표시한다. 바이너리 신규 작업과 OTA 기수록 작업이 노트에서 구분된다.

```bash
# ota 태그별 번들 전용 커밋 제목 수집 (정규화) — TSV: {정규화 제목}\t{번들 버전}
git fetch --tags -q
: > /tmp/ota_shipped.tsv
git tag -l 'ota/*' | while read -r t; do
  bv=$(echo "$t" | sed -E 's|^ota/([0-9.]+)-[0-9]+$|\1|')
  git rev-parse --verify -q "v${bv}" >/dev/null || { echo "WARN: v${bv} 태그 없음 — ${t} 건너뜀" >&2; continue; }
  git log --no-merges --format='%s' "v${bv}..${t}" \
    | sed -E 's/( \(#[0-9]+\))+$//; s/ \((bundle|release)\/[0-9.]+\)//g; s/^[[:space:]]+//; s/[[:space:]]+$//' \
    | awk -v bv="${bv}" '{print $0 "\t" bv}' >> /tmp/ota_shipped.tsv
done
sort -u /tmp/ota_shipped.tsv -o /tmp/ota_shipped.tsv
```

`ota/*` 태그가 하나도 없으면 이 단계 전체를 skip한다 (AUTO_NOTES 무변형).

AUTO_NOTES 후처리 — 각 `* {title} by @user in {url}` 라인의 title을 같은 규칙으로 정규화해 일치하면 suffix를 붙인다:

```bash
if [ -s /tmp/ota_shipped.tsv ]; then
export AUTO_NOTES
AUTO_NOTES=$(python3 - <<'PY'
import os, re

shipped = {}
with open('/tmp/ota_shipped.tsv') as f:
    for line in f:
        line = line.rstrip('\n')
        if '\t' not in line:
            continue
        title, ver = line.rsplit('\t', 1)
        shipped.setdefault(title, ver)

def normalize(t):
    t = re.sub(r'( \(#\d+\))+$', '', t)
    t = re.sub(r' \((?:bundle|release)/[\d.]+\)', '', t)
    return t.strip()

out = []
for line in os.environ['AUTO_NOTES'].splitlines():
    m = re.match(r'^(\* )(.+)( by @\S+ in \S+)$', line)
    if m:
        ver = shipped.get(normalize(m.group(2)))
        if ver:
            line = f"{m.group(1)}{m.group(2)} (OTA 선출시: {ver}){m.group(3)}"
    out.append(line)
print('\n'.join(out))
PY
)
fi
```

### 5. Template 채우기

`.github/release-template.md`을 읽어서 `{{...}}` placeholder를 치환:

| Placeholder | Value |
|---|---|
| `{{AUTO_NOTES}}` | API에서 받은 changelog |
| `{{VERSION}}` | 예: `6.2605.1` |
| `{{TAG}}` | 예: `v6.2605.1` |
| `{{COMMIT_SHORT}}` | 머지 커밋 short SHA |

빌드 번호와 TestFlight 링크 placeholder(`{{ANDROID_VERSION_CODE_PROD}}` 등)는 **그대로 둠** — release publish 후 빌드 결과 나오면 사람이 edit 으로 채움.

```bash
TEMPLATE=$(cat .github/release-template.md)
export AUTO_NOTES VERSION TAG COMMIT_SHORT
BODY=$(printf "%s" "$TEMPLATE" \
  | python3 -c "
import sys, os
t = sys.stdin.read()
t = t.replace('{{AUTO_NOTES}}', os.environ['AUTO_NOTES'])
t = t.replace('{{VERSION}}', os.environ['VERSION'])
t = t.replace('{{TAG}}', os.environ['TAG'])
t = t.replace('{{COMMIT_SHORT}}', os.environ['COMMIT_SHORT'])
print(t)
")
```

(작은 치환이라 sed로도 가능. AUTO_NOTES에 특수문자가 많으니 python이 안전.)

### 6. Release 생성

기본은 **publish 상태**로 생성. body 안 placeholder는 사후 edit으로 채움.

```bash
echo "$BODY" > /tmp/release-body.md
gh release create "$TAG" \
  --title "$TAG" \
  --notes-file /tmp/release-body.md \
  --target "$MERGE_COMMIT"
```

리뷰 게이트가 필요하면 `--draft` 추가:

```bash
gh release create "$TAG" \
  --title "$TAG" \
  --notes-file /tmp/release-body.md \
  --target "$MERGE_COMMIT" \
  --draft
```

> 이 repo의 `release.yml`은 release publish 이벤트가 아니라 **tag push**에만 반응하므로, draft 여부는 액션 트리거와 무관. 단순히 노출/배지/알림 차이.

### 7. 사용자에게 사후 채울 placeholder 안내

생성된 release URL과 함께 사용자가 edit으로 채울 항목 명시:

- `{{ANDROID_VERSION_CODE_PROD}}` / `{{ANDROID_VERSION_CODE_STAGING}}` — Android versionCode
- `{{IOS_BUILD_NUMBER_PROD}}` / `{{IOS_BUILD_NUMBER_STAGING}}` — iOS buildNumber (YYMMDDhhmmss)
- `{{TESTFLIGHT_PROD_URL}}` / `{{TESTFLIGHT_STAGING_URL}}` — TestFlight 그룹 링크

빌드 번호는 App Store Connect / Play Console / 사내 빌드 워크플로우 로그에서 확인. 빌드가 끝난 후 release 페이지에서 직접 edit 하면 됨.

## Safety Guardrails

- **태그 force-push 전 확인**: 이미 태그가 다른 커밋을 가리키면, 옮기는 게 정말 의도된 것인지 사용자에게 한 번 묻기.
- **Husky pre-push**: 태그 push 도 pre-push 훅 발화. 환경이 깨져 있으면 사용자에게 `yarn install` 안내.
- **출시 후 정렬용 force-push**: 이미 store 출시가 끝난 버전을 단순 정렬하는 경우, 태그 force-push 가 store submit + deploy 를 재실행시키므로 새 run 을 즉시 cancel 하거나 concurrency 그룹이 cancel 하도록 둠. 절대 hook bypass 금지.
- **버전 정합성**: `MARKETING_VERSION`(iOS)과 `versionName`(Android)이 태그 commit 에서 일치해야 `release.yml` validate 통과. 안 맞으면 워크플로우 실패하므로 push 전에 확인.
- **draft 옵션**: 기본은 publish 상태로 생성. 리뷰 게이트가 필요한 경우만 `--draft` 추가.

## Related

- `.github/release.yml` — auto-generated notes 카테고리화 (`feature`/`bugfix`/`refactoring` 등 라벨 기준)
- `.github/release-template.md` — body 템플릿
- `.github/workflows/release.yml` — 태그 push 시 store submit + remote deploy 트리거 (release 자동 생성 단계는 제거됨)
