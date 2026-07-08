---
name: release-branch-cut
description: main 에서 다음 릴리즈 브랜치 release/{version} 과 번들 브랜치 bundle/{version} 을 동시에 따서 원격 푸시. release 브랜치는 `yarn set-versionName` 으로 버전 범프 후 "Set version to {version}" 커밋까지. "릴리즈 브랜치 따줘", "release/X.X.X bundle/X.X.X 만들어줘", "다음 주차 릴리즈 브랜치 생성", "set version 브랜치" 같은 요청에 사용.
---

# Release Branch Cut Skill

출시 사이클 시작 시 필요한 두 브랜치를 `main` 에서 한 번에 따서 푸시한다.

1. **`release/{releaseVersion}`** — 다음 출시 브랜치. `yarn set-versionName` 으로 Android/iOS/package.json 버전을 올리고 `Set version to {releaseVersion}` 커밋 후 푸시.
2. **`bundle/{bundleVersion}`** — 직전 출시 바이너리 위에 OTA 번들 작업을 쌓을 브랜치. 커밋 없이 `main` tip 을 가리킨 채 푸시.

전형적으로 `release-create` → `release-to-main` → `release-tickets-done` 로 한 주차 출시를 마친 직후, 다음 주차를 시작할 때 쓴다.

## 입력

- `releaseVersion` — 새로 시작하는 릴리즈 버전 (예: `6.2606.2`). 브랜치는 `release/{releaseVersion}`.
- `bundleVersion` — 방금 출시된(= 현재 `main` 의) 바이너리 버전 (예: `6.2606.1`). 브랜치는 `bundle/{bundleVersion}`.

버전 스킴은 `6.{YYWW}.{N}`. 두 값의 관계가 고정은 아니다(같은 주 patch 증가 `6.2606.1→6.2606.2` 일 수도, 다음 주 `6.2607.1` 일 수도). **둘 중 하나라도 모호하면 사용자에게 물어본다.** 기본 추론:

- `bundleVersion` = 현재 `main` 의 `package.json` version (= 직전 출시본). `git show origin/main:package.json | grep '"version"'`.
- `releaseVersion` = 보통 그 patch +1. 단 주차 롤오버는 사람이 판단 → 확신 없으면 질문.

> 한쪽만 필요할 때도 있다(번들 브랜치만, 혹은 릴리즈 브랜치만). 요청에 없는 브랜치는 만들지 않는다.

## Pre-flight Checks

1. **원격 최신화**: `git fetch origin main -q`. 모든 작업은 `origin/main` 기준.
2. **중복 방지**: 두 브랜치가 원격에 이미 있는지 확인 — 있으면 멈추고 사용자에게 보고(덮어쓰기 금지).
   ```bash
   git ls-remote --heads origin "release/{releaseVersion}" "bundle/{bundleVersion}"
   ```
3. **작업트리 정리(중요)**: 현재 작업트리에 무관한 변경이 있으면 버전 범프 커밋에 섞일 위험 + 브랜치 체크아웃 시 따라붙음. **stash 해두고 끝나면 복원**한다.
   ```bash
   git stash push -m "wip: parked for release branch cut" -- <변경 파일들>   # 변경 있을 때만
   ```
4. **현재 브랜치 기억**: 작업 끝나고 원래 브랜치로 복귀해야 하므로 `git branch --show-current` 저장.

## 핵심 사실 (검증됨)

- 버전 범프 스크립트는 **`yarn set-versionName {version}`** (camelCase, `scripts/setVersionName.sh`). `setVersionname`/`set-version` 아님 — 오타 주의.
- 이 스크립트가 바꾸는 파일은 **정확히 3개**:
  - `package.json` (`"version"`)
  - `packages/host/android/app/build.gradle` (`versionName`)
  - `packages/host/ios/miso.xcodeproj/project.pbxproj` (`MARKETING_VERSION`, 2곳)
- 커밋 메시지 컨벤션: **`Set version to {version}`** (소문자 version + "to") + 빈 줄 + `Co-Authored-By: Claude <noreply@anthropic.com>`. 티켓 prefix 없는 기계적 커밋이라 `[Type/TICKET]` 포맷 미적용.
- 푸시는 **Husky pre-push** 발화 → 절대 우회 금지(`--no-verify`/`HUSKY=0` 금지). 환경 깨지면 `yarn install` 안내.

## Step-by-Step Flow

### 1. 변수 + pre-flight

```bash
RELEASE_VERSION=<예: 6.2606.2>
BUNDLE_VERSION=<예: 6.2606.1>
ORIG_BRANCH=$(git branch --show-current)
git fetch origin main -q
git ls-remote --heads origin "release/${RELEASE_VERSION}" "bundle/${BUNDLE_VERSION}"   # 비어 있어야 함
```

무관한 작업트리 변경이 있으면 stash (Pre-flight 3).

### 2. bundle 브랜치 (커밋 없음) 생성 + 푸시

체크아웃 없이 ref 만 만들어 푸시 — 작업트리 안 건드림.

```bash
git branch "bundle/${BUNDLE_VERSION}" origin/main
git push -u origin "bundle/${BUNDLE_VERSION}"
```

### 3. release 브랜치 생성 + 버전 범프 + 커밋 + 푸시

```bash
git checkout -b "release/${RELEASE_VERSION}" origin/main
yarn set-versionName "${RELEASE_VERSION}"

# 정확히 3개 파일만 스테이지 (stash 안 한 잔여 변경 섞임 방지)
git add package.json \
        packages/host/android/app/build.gradle \
        packages/host/ios/miso.xcodeproj/project.pbxproj

# 버전 문자열만 바뀌었는지 한 번 확인 후 커밋
git commit -m "Set version to ${RELEASE_VERSION}

Co-Authored-By: Claude <noreply@anthropic.com>"

git push -u origin "release/${RELEASE_VERSION}"
```

### 4. 원복 + 검증

```bash
git checkout "${ORIG_BRANCH}"
git stash pop          # stash 했을 때만
git ls-remote --heads origin "release/${RELEASE_VERSION}" "bundle/${BUNDLE_VERSION}"   # 둘 다 떠야 함
```

`release/{version}` tip 은 `Set version to {version}` 커밋, `bundle/{version}` tip 은 `origin/main` 과 동일 SHA 여야 정상.

## Safety Guardrails

- **Husky 우회 절대 금지** — pre-push 실패 시 원인 수정 후 동일 push 재시도.
- **버전 범프 커밋엔 3개 파일만** — `git add -A`/`git commit -a` 금지. 잔여 변경 섞임 방지.
- **이미 존재하는 브랜치 force 금지** — 원격에 있으면 멈추고 사용자 확인.
- **버전 추론 모호하면 질문** — 주차 롤오버(`.2606.2` vs `.2607.1`)는 사람이 결정.
- **작업 끝나면 원래 브랜치 복귀 + stash 복원** — 다른 작업 중이던 컨텍스트를 망치지 않는다.
- 한쪽 브랜치만 요청되면 다른 쪽은 만들지 않는다.

## Related

- `release-create` / `release-to-main` / `release-tickets-done` — 한 주차 출시 마무리 3종. 이 스킬은 그 다음 주차의 **시작**.
- `scripts/setVersionName.sh` — Android/iOS/package.json 버전 동기 변경.
- `.claude/docs/GIT_WORKFLOW.md` — 브랜치/커밋 컨벤션.
