---
name: ota-release
description: 번들 브랜치(bundle/X.X.X)의 OTA production 배포를 release 생성으로 발화한다. ota/{version}-{seq} prerelease를 만들면 그 태그 커밋의 ota-deploy.yml이 실행되어 배포된다. 다중 버전 입력 시 버전별 release를 일괄 생성(멀티 디스패치). "OTA 배포", "번들 배포해줘", "6.2605.2 customer 배포" 같은 요청에 사용.
---

# OTA Release Skill

번들 production 배포의 정식 진입점. release가 곧 배포 버튼이다 — 배포 기록(release)이 배포보다 먼저 존재하므로 기록 누락이 구조적으로 불가능하다.

## 사용법

```
/ota-release 6.2605.2 --apps customer,partner
/ota-release 6.2605.1,6.2605.2,6.2606.1 --apps customer        # 멀티 디스패치
/ota-release 6.2605.2 --apps partner --mandatory
```

- 버전: 쉼표/공백 구분 다중 입력. `bundle/` prefix가 붙어 있으면 떼고 해석.
- `--apps`: customer/partner/auth/chat 중 1개 이상. **없으면 추측하지 말고 사용자에게 묻는다.**
- `--mandatory`: 강제 업데이트. 명시 요청 시에만.

## 절차

### 1. 검증 — 모든 버전이 통과해야 생성 시작 (부분 생성 방지)

```bash
git fetch origin --prune --tags -q
```

각 버전 `{v}`에 대해:

```bash
sha=$(git rev-parse --verify -q "origin/bundle/{v}") \
  || { echo "bundle/{v} 브랜치 없음"; exit 1; }
git rev-parse --verify -q "v{v}" >/dev/null \
  || { echo "v{v} 태그 없음 — 번들 브랜치는 v릴리즈 후 생성되는 것이 정상"; exit 1; }
# release 이벤트는 태그 커밋의 워크플로우 파일을 실행한다 — 없으면 release를 만들어도 조용히 미발화
git cat-file -e "${sha}:.github/workflows/ota-deploy.yml" \
  || { echo "bundle/{v}에 ota-deploy.yml 없음 — /bundle-backport로 먼저 반영"; exit 1; }
```

### 2. 회차(seq)와 changelog 기준점 계산

```bash
max_seq=$(git tag --list "ota/{v}-*" | sed "s|^ota/{v}-||" | grep -E '^[0-9]+$' | sort -n | tail -1)
seq=$(( ${max_seq:-0} + 1 ))
start_tag=$([ -n "$max_seq" ] && echo "ota/{v}-${max_seq}" || echo "v{v}")
```

기준점이 직전 OTA 태그(첫 OTA면 v태그)라 changelog에 이번 OTA 신규분만 잡힌다.

### 3. release 생성 = 배포 발화 (버전별 1회)

```bash
gh release create "ota/{v}-${seq}" \
  --target "${sha}" \
  --prerelease \
  --title "OTA {v} #${seq} — {apps 표기}" \
  --generate-notes --notes-start-tag "${start_tag}" \
  --notes '<!-- ota-deploy
apps: {apps}
mandatory: {true|false}
-->'
```

태그 생성·publish·changelog를 이 한 명령이 처리한다. `--notes`의 메타 블록은 `ota-deploy.yml` resolve job이 읽는 배포 옵션으로, 자동 생성 changelog 앞에 붙는다. `already exists` 충돌(드문 동시 생성)이면 `git fetch origin --tags` 후 seq를 재계산해 1회만 재시도한다.

### 4. 발화 확인 및 보고

```bash
sleep 10
gh run list --workflow=ota-deploy.yml --limit {버전 수} --json displayTitle,url,status,createdAt
```

버전별로 `release URL | 트리거된 run URL | 상태` 표로 보고한다. run이 잡히지 않으면 순서대로 확인:

1. 태그 커밋에 `ota-deploy.yml`이 없음 (1의 가드를 우회한 경우)
2. release를 `GITHUB_TOKEN`(Actions 봇)으로 생성함 — 봇 토큰이 만든 release는 워크플로우를 발화시키지 않는다. 이 스킬은 사람 `gh` 토큰 전제.

## 가드레일

- `deploy-remote.yml`을 직접 dispatch하지 않는다 — 배포 기록 없는 배포가 된다.
- staging 배포는 대상 아님 (`deploy-remote-staging.yml` / multi dispatcher 사용).
- 메타 블록 키(apps/mandatory)는 `ota-deploy.yml` resolve job과의 계약 — 형식을 바꾸면 양쪽을 동시에 수정한다.
- 배포 결과(성공/실패 + run 링크)는 `ota-deploy.yml` report job이 release 본문에 덧붙인다 — 완료 확인은 release 페이지에서.
