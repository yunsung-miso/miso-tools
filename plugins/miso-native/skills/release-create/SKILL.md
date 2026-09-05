---
name: release-create
description: 심사 준비가 끝난 release/{version} 브랜치 tip에 v{version} 태그를 붙여 push 한다. 이 push 로 앱 심사 제출(store submit)과 production 리모트 배포가 실행되고, GitHub Release 도 함께 만든다(기본 publish). test app 섹션의 빌드 번호와 TestFlight 링크 placeholder 는 나중에 사람이 채운다. `--draft` 로 draft 생성도 된다. "앱 심사 진행", "스토어 제출", "릴리즈 올려줘" 요청은 이 스킬로 처리한다.
---

# Release Create Skill

심사 준비가 끝난 `release/{version}` 브랜치 tip에 **v{version} 태그를 붙여 push** 한다. `release.yml` 이 이 태그를 보고 host store submit 과 리모트 배포를 실행한다. 같은 흐름에서 그 버전의 GitHub Release 노트도 만든다.

**앱 심사 제출은 태그 push 다.** 심사를 올릴 때는 이 스킬을 쓴다.

## 릴리즈 파이프라인에서의 위치

```
release-branch-cut → (주차 개발) → bundle-to-release-merge
  → ★ release-create (태그 push = 심사 제출 + 리모트 배포)
  → 심사 통과·스토어 배포
  → release-finish (release-to-main → main 머지 → tickets-done → 다음 주차 컷)
```

`release-finish` 는 심사 통과·배포 뒤의 마무리를 묶어 돌리는 스킬이다. 심사 제출과는 무관하다.

태그는 **main 머지 전에** release 브랜치 tip에 붙인다. main 머지는 심사를 통과한 뒤 `release-finish` 안의 `release-to-main` 단계에서 한다.

실측(v6.2608.1): 태그는 `003d282d6`(release/6.2608.1 tip, 2026-08-21), release→main PR #2034 의 머지 커밋은 `8787572`(2026-08-24). 서로 다른 커밋이고 태그가 3일 앞선다.

## 이 스킬이 하는 일

1. **태그 push 로 출시 워크플로우 실행** — `release.yml` 은 `push: tags: v[0-9]*` 에 반응한다.
2. **Release 노트 생성** — `.github/release.yml` 의 카테고리 설정과 `.github/release-template.md` 를 적용한 본문을 만든다.
3. 두 가지를 한 흐름에 묶어서, 빌드·배포·노트를 따로 챙기지 않게 한다.

## When to use

- `release/{version}` 준비가 끝나 **앱 심사를 올릴 때** (store submit 과 production remote 배포가 같이 실행된다)
- 이미 만든 태그가 엉뚱한 커밋을 가리켜 옮겨야 할 때 (출시가 끝난 뒤의 단순 정렬이면 워크플로우가 다시 도는 부작용을 먼저 확인한다)

## 하지 말 것: build-host-app 수동 실행

"심사 올려줘" 요청에 `build-host-app.yml` 을 `stage=store` 로 직접 실행하면 안 된다. `release.yml` 은 잡 두 개를 함께 돌린다.

| 잡 | 하는 일 |
|---|---|
| `host-build` | build-host-app (both / store / cdn) |
| `deploy-remotes` | customer·partner·auth·chat production 배포, `target_host_version={version}` |

`build-host-app` 만 직접 돌리면 `deploy-remotes` 가 실행되지 않는다. 새 host 버전을 받는 production 리모트 없이 바이너리만 심사에 올라가고, 태그도 릴리즈 노트도 남지 않는다.

## Pre-flight Checks

1. **release 브랜치 tip 확정**: `git fetch origin --tags` 후 `git rev-parse origin/release/{version}`. 이 커밋에 태그를 붙인다.
2. **번들 핫픽스 확인**: 직전 번들(`bundle/{이전버전}`)의 OTA 핫픽스를 `bundle-to-release-merge` 로 얹었는지 본다. 보통 release tip 이 `[{이전버전}] merge to {version}` PR 의 결과다.
3. **release 가 main 을 모두 담고 있는지**: `git log origin/release/{version}..origin/main` 이 비어야 한다. 남아 있으면 main 의 변경이 이번 바이너리에서 빠진다.
4. **열린 PR 없음**: `gh pr list --base release/{version} --state open` 으로 심사에 태울 작업이 남았는지 본다.
5. **버전 정합성**: 태그 커밋의 Android `versionName` 과 iOS `MARKETING_VERSION` 이 `{version}` 과 같아야 `release.yml` 의 validate 를 통과한다. 다르면 워크플로우가 거기서 실패한다.
6. **이전 태그 확인**: `git tag --sort=-creatordate | head -5` 로 직전 버전 태그를 본다 (compare URL 용).
7. **스토어 노출 문구**: `packages/host/{ios,android}/fastlane/release-notes/` 의 문구를 이번 버전용으로 바꿀지 확인한다. 태그를 민 다음 바꾸려면 다시 빌드해야 한다.

## Step-by-Step Flow

### 1. 기본 변수 수집

```bash
VERSION=<릴리즈 버전, 예: 6.2609.1>
TAG="v${VERSION}"

# 태그 타깃 = release 브랜치 tip
git fetch origin --tags -q
TARGET_COMMIT=$(git rev-parse "origin/release/${VERSION}")
COMMIT_SHORT="${TARGET_COMMIT:0:8}"
```

> 출시가 끝난 버전의 태그를 main 머지 커밋으로 **옮기기만** 하는 예외라면 `TARGET_COMMIT` 을 `gh pr view <PR> --json mergeCommit --jq '.mergeCommit.oid'` 로 바꾼다. 이때는 태그 push 로 store submit 이 다시 도니까 새 run 을 바로 cancel 한다.

`PREV_TAG` 는 Step 3 에서 구한다. 태그를 만든 뒤라야 순서가 맞다.

### 2. 태그 만들고 push (여기서 출시가 시작된다)

이 단계가 **스킬의 핵심**이다. 태그를 push 하면 `release.yml` 이 host store submit 과 리모트 배포를 실행한다.

```bash
# 신규 태그 (일반 케이스) — force 금지
git fetch --tags origin
git tag "$TAG" "$TARGET_COMMIT"
git push origin "$TAG"

# 기존 태그를 옮기는 예외 케이스만 -f / --force
# git tag -f "$TAG" "$TARGET_COMMIT"
# git push origin "$TAG" --force
```

push 후 GitHub Actions 에서 `Release` 워크플로우 run을 확인:

```bash
gh run list --workflow=release.yml --limit 1
```

`Validate Release Tag` 가 success 면 버전 정합성이 맞은 것이다. 이어서 `Host Store Submit`(iOS/Android)과 `Deploy Remote Apps` 가 같이 도는지 본다. 둘 중 하나만 보이면 잘못된 경로로 올린 것이다.

⚠️ **출시가 끝난 버전의 태그를 옮기기만 하는 경우**(release tip → 머지 커밋): force-push 직후 새 run 을 **직접 cancel 한다.** `release.yml` 의 concurrency 는 `cancel-in-progress: false` 라, 그룹에 맡기면 취소되지 않고 앞 run 이 끝난 뒤 실행된다. hook 우회는 금지다.

### 3. 직전 릴리즈 태그 계산 (compare URL 용)

태그를 만든 뒤, 새 태그를 뺀 가장 최신 정식 릴리즈 태그를 찾는다. 새 태그가 정렬 맨 위에 오므로 두 번째 항목이 직전 태그다.

```bash
PREV_TAG=$(git tag --sort=-version:refname | grep '^v[0-9]' | grep -v 'rc' | head -2 | tail -1)
```

> Step 2 를 건너뛰고 release 만 다시 만드는 드문 경우에는 이 명령이 현재 태그가 아니라 그 이전 태그를 준다. 그때는 `PREV_TAG` 를 직접 적는다.

### 4. 릴리즈 노트 자동 생성

`.github/release.yml` 의 카테고리 설정을 적용한 changelog 를 GitHub API 로 받는다.

```bash
AUTO_NOTES=$(gh api -X POST repos/:owner/:repo/releases/generate-notes \
  -f tag_name="$TAG" \
  -f previous_tag_name="$PREV_TAG" \
  -f target_commitish="$TARGET_COMMIT" \
  --jq '.body')
```

### 4-A. OTA 선출시 항목 표시

AUTO_NOTES 의 PR 항목 중 `ota/*` 태그로 이미 사용자에게 나간 작업(번들 forward-port)에 출처를 붙인다. 이번 바이너리에서 처음 나가는 작업과 OTA 로 먼저 나간 작업을 노트에서 구분하려는 것이다.

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

`ota/*` 태그가 하나도 없으면 이 단계는 통째로 건너뛴다. AUTO_NOTES 는 그대로 둔다.

AUTO_NOTES 후처리. 각 `* {title} by @user in {url}` 줄의 title 을 같은 규칙으로 정규화하고, 일치하면 뒤에 표시를 붙인다.

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
    # 번들→릴리즈 통합 PR 제목("[X] merge to Y")은 ota 범위에도 그대로 들어있어
    # 무조건 매칭된다. 개별 작업이 아니므로 표시 대상에서 제외한다.
    if m and not re.match(r'^\[[\d.]+\] merge to ', m.group(2)):
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

`.github/release-template.md` 을 읽어서 `{{...}}` placeholder 를 바꾼다.

| Placeholder | 값 |
|---|---|
| `{{AUTO_NOTES}}` | API 에서 받은 changelog |
| `{{VERSION}}` | 예: `6.2605.1` |
| `{{TAG}}` | 예: `v6.2605.1` |
| `{{COMMIT_SHORT}}` | 태그 타깃 커밋 short SHA |

빌드 번호와 TestFlight 링크 placeholder(`{{ANDROID_VERSION_CODE_PROD}}` 등)는 **그대로 둔다.** release 를 publish 하고 빌드 결과가 나온 뒤에 사람이 채운다.

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

(sed 로도 되지만 AUTO_NOTES 에 특수문자가 많아서 python 이 안전하다.)

### 6. Release 생성

기본은 **publish 상태**로 만든다. 본문에 남은 placeholder 는 나중에 채운다.

```bash
echo "$BODY" > /tmp/release-body.md
gh release create "$TAG" \
  --title "$TAG" \
  --notes-file /tmp/release-body.md \
  --target "$TARGET_COMMIT"
```

리뷰를 한 번 거치려면 `--draft` 를 붙인다.

```bash
gh release create "$TAG" \
  --title "$TAG" \
  --notes-file /tmp/release-body.md \
  --target "$TARGET_COMMIT" \
  --draft
```

> 이 repo 의 `release.yml` 은 release publish 가 아니라 **tag push** 에만 반응한다. draft 여부는 워크플로우 실행과 무관하고, 노출·배지·알림만 달라진다.

### 7. 나중에 채울 placeholder 안내

만든 release URL 과 함께, 사용자가 직접 채울 항목을 알려준다.

- `{{ANDROID_VERSION_CODE_PROD}}` / `{{ANDROID_VERSION_CODE_STAGING}}` — Android versionCode
- `{{IOS_BUILD_NUMBER_PROD}}` / `{{IOS_BUILD_NUMBER_STAGING}}` — iOS buildNumber (YYMMDDhhmmss)
- `{{TESTFLIGHT_PROD_URL}}` / `{{TESTFLIGHT_STAGING_URL}}` — TestFlight 그룹 링크

빌드 번호는 App Store Connect, Play Console, 사내 빌드 워크플로우 로그에서 찾는다. 빌드가 끝나면 release 페이지에서 바로 고치면 된다.

## Safety Guardrails

- **태그를 force-push 하기 전에 묻기**: 태그가 이미 다른 커밋을 가리키고 있으면, 옮기는 게 맞는지 사용자에게 한 번 확인한다.
- **Husky pre-push**: 태그를 push 할 때도 pre-push 훅이 돈다. 환경이 깨져 있으면 사용자에게 `pnpm install` 을 안내한다.
- **출시 후 태그를 옮길 때**: store 출시가 끝난 버전이라면 force-push 로 store submit 과 배포가 다시 돈다. 새 run 을 직접 cancel 한다. `release.yml` 의 concurrency 는 `cancel-in-progress: false` 라 그룹이 대신 취소해 주지 않는다. hook 우회는 금지다.
- **버전 정합성**: 태그 커밋의 iOS `MARKETING_VERSION` 과 Android `versionName` 이 같아야 `release.yml` 의 validate 를 통과한다. 다르면 워크플로우가 실패하니 push 전에 확인한다.
- **draft 옵션**: 기본은 publish 다. 리뷰를 한 번 거칠 때만 `--draft` 를 붙인다.
- **태그 push 는 되돌리기 어렵다**: iOS 는 `submit_for_review: true` 라 App Store 심사에 자동 제출되고, Android 는 Play `production` 트랙에 올라간다. production 리모트 4종도 같이 배포된다. push 전에 사용자 확인을 받는다.
- **심사에 `build-host-app` 을 직접 쓰지 않는다**: 리모트 배포와 태그, 릴리즈 노트가 전부 빠진다. 위 "하지 말 것" 절을 본다.

## Related

- `.github/release.yml` — 자동 생성 노트의 카테고리 설정 (`feature`/`bugfix`/`refactoring` 등 라벨 기준)
- `.github/release-template.md` — 본문 템플릿
- `.github/workflows/release.yml` — 태그를 push 하면 store submit 과 remote deploy 를 실행한다 (release 자동 생성 단계는 빠졌다)
- `bundle-to-release-merge` — 앞 단계. 직전 번들의 OTA 핫픽스를 release 에 얹는다.
- `release-finish` / `release-to-main` — 뒤 단계. 심사를 통과한 뒤 main 머지, 티켓 정리, 다음 주차 브랜치 컷.
