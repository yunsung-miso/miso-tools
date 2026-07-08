---
name: bundle-release-status
description: 번들 브랜치(bundle/X.X.X) 작업의 출시 가시성 조회. --gaps(기본)는 번들 전용 커밋이 현재 release 브랜치/main에 수록됐는지 patch-id+제목 매칭으로 판정해 누락을 적발하고, --history <티켓|PR번호>는 번들 머지 → OTA 출시(ota/* 태그) → 정식 v릴리즈 수록까지 타임라인을 보여준다. "번들 누락 확인", "OTA 출시 이력", "번들 작업이 릴리즈에 들어갔는지" 같은 요청에 사용.
---

# Bundle Release Status Skill

번들 브랜치 작업이 실제 릴리즈로 어떻게 출시되는지 조회한다. 두 모드:

- `--gaps` (기본): 미수록 작업 적발 (미래향 — 다음 바이너리 회귀 방지)
- `--history <티켓|PR번호>`: 출시 이력 타임라인 (과거향 — 성과 측정·회고)

## 사용법

```
/bundle-release-status                          # gaps, 모든 활성 번들
/bundle-release-status --gaps bundle/6.2605.2   # gaps, 특정 번들만
/bundle-release-status --history PRD-6560       # 티켓 이력
/bundle-release-status --history 1391           # PR 번호 이력
```

## 공통: 제목 정규화 (normalize)

backport·forward-port 커밋은 PR 번호와 브랜치 표시만 다르므로 비교 전 제거한다. cherry-pick 커밋은 끝에 `(#원본PR) (#새PR)` 연쇄 suffix가 생길 수 있어 반복 그룹으로 제거한다.

```bash
normalize() {
  sed -E 's/( \(#[0-9]+\))+$//; s/ \((bundle|release)\/[0-9.]+\)//g; s/^[[:space:]]+//; s/[[:space:]]+$//'
}
```

## 사전 준비 (양쪽 모드 공통)

```bash
git fetch origin --prune --tags -q
# 비교 타겟: 최신 release 브랜치 자동 감지
RELEASE=$(git branch -r --list 'origin/release/*' | sed 's|.*origin/||' | sort -V | tail -1)
```

## --gaps 모드

### 1. 대상 번들 결정

인자로 번들이 지정되면 그것만, 없으면 `git branch -r --list 'origin/bundle/*'` 전부를 대상으로 한다.

### 2. 번들별 판정

각 번들 `bundle/{X}`에 대해 (기준 태그 `V="v{X}"`):

```bash
X="6.2605.2"; V="v${X}"; B="origin/bundle/${X}"
git rev-parse --verify -q "$V" >/dev/null || { echo "기준 태그 ${V} 없음 — fail-stop (번들 브랜치는 v태그 릴리즈 후 생성되는 것이 정상)"; exit 1; }

# (a) patch-id 판정 — git cherry: '+' = upstream에 동등 패치 없음, '-' = 있음
git cherry "origin/${RELEASE}" "$B" "$V" > /tmp/cherry_release.txt
git cherry origin/main          "$B" "$V" > /tmp/cherry_main.txt

# (b) 비교 측 제목 사전 (release 브랜치 + vX 이후 main)
git log --no-merges --format='%s' "origin/${RELEASE}" origin/main --not "$V" \
  | normalize | sort -u > /tmp/upstream_titles.txt
```

판정 순서 (커밋별, merge 커밋 제외):

1. `/tmp/cherry_release.txt`에서 `-` → `✅ 수록(release)` — 수록 PR 번호는 아래 release PR 맵에서 정규화 제목으로 조회해 표기
2. `/tmp/cherry_main.txt`에서 `-` → `✅ 수록(main)` — 이미 이전 v릴리즈로 출시된 작업
3. 둘 다 `+`이고 정규화 제목이 `/tmp/upstream_titles.txt`에 존재 → `~ 제목일치` (cherry-pick 충돌 해소로 patch-id가 바뀐 케이스 — 검토 권장)
4. 어디에도 없음 → `❌ 누락`

수록 PR 번호 맵 (한 번만 구축, --history 타임라인에서도 재사용):

```bash
# 정규화 제목 → release 측 마지막 (#N) 매핑 (Python 일괄 — 프로세스 포크 제거,
# 정규화 규칙은 위 normalize() 와 동일)
git log --no-merges --format='%s' "origin/${RELEASE}" --not "$V" | python3 -c '
import sys, re
def normalize(t):
    t = re.sub(r"( \(#[0-9]+\))+$", "", t)
    t = re.sub(r" \((bundle|release)/[0-9.]+\)", "", t)
    return t.strip()
for line in sys.stdin:
    line = line.rstrip("\n")
    if not line:
        continue
    prs = re.findall(r"#[0-9]+", line)
    print(normalize(line) + "\t" + (prs[-1] if prs else ""))
' > /tmp/release_pr_map.tsv

# 조회: awk -F'\t' -v t="{정규화 제목}" '$1==t {print $2; exit}' /tmp/release_pr_map.tsv
```

### 3. OTA 출시 여부 병기

각 커밋이 어느 OTA로 유저에게 나갔는지 표기:

```bash
git tag --sort=creatordate --contains "{sha}" --list 'ota/*' | head -1
# 결과 없으면 "(미배포)" — 번들에 머지됐지만 아직 OTA 안 나간 작업
```

### 4. 출력

번들별 테이블 + 요약. `❌ 누락`과 `~ 제목일치`를 상단에 배치한다.

```
## bundle/6.2605.2 → release/6.2606.1 수록 현황

| 상태 | 커밋 | 제목 | OTA 출시 | 수록 |
|---|---|---|---|---|
| ❌ 누락 | abc1234 | [Feature/XXX-1] ... | ota/6.2605.2-2 | — |
| ~ 제목일치 | def5678 | [Bugfix/YYY-2] ... | ota/6.2605.2-1 | release (검토 권장) |
| ✅ | 0395f49 | [Fix/AIP-951] ... | ota/6.2605.2-3 | release #1452 |
| ✅ | 5c0a50f | [Feature/PRD-6560] ... | ota/6.2605.2-1 | main → v6.2605.2 |

요약: 총 18건 — ✅ 15 / ~ 2 / ❌ 1
```

`❌ 누락`이 있으면 마지막에 명시: "다음 바이너리(release/{R})에서 이 기능이 사라집니다. forward-port PR을 만들거나, 번들 전용 작업(의도적 미수록)이면 무시하세요."

## --history 모드

### 1. 입력 파싱

- `[A-Z]+-\d+` 패턴 (예: `PRD-6560`) → 티켓 모드: `--grep="{티켓}"`
- 숫자만 (예: `1391`) → PR 모드: `--grep="(#1391)"` — git log --grep 기본 BRE에서 괄호는 literal이라 이스케이프 불필요. `-F`/`--fixed-strings`를 추가하지 말 것 (티켓 모드 패턴 매칭과 충돌)
- 그 외 → 키워드 모드: `--grep="{입력}"`

### 2. 커밋 수집

```bash
git log --all --no-merges --grep="{패턴}" --format='%H%x09%cs%x09%s'
```

각 커밋에 대해 위치 분류:

```bash
git branch -r --contains "{sha}" | sed 's/^[* ]*origin\///' \
  | grep -E '^(bundle/|release/|main$)'
```

### 3. 출시 지점 산출

- **OTA 출시**: 번들 커밋에 대해 `git tag --sort=creatordate --contains "{sha}" --list 'ota/*' | head -1` → 태그명 + `git log -1 --format=%cs "{태그}"` 날짜
- **정식 수록**: main에 도달한 커밋(동일 정규화 제목 포함)에 대해 `git tag --sort=v:refname --contains "{sha}" --list 'v[0-9]*' | head -1`
- **release 수록 PR 번호**: gaps 모드의 `/tmp/release_pr_map.tsv`를 동일하게 구축해 정규화 제목으로 조회

### 4. 타임라인 출력

```
PRD-6560 출시 이력

- 5c0a50f [Feature/PRD-6560] customer CS 챗봇 지원 서비스에 세차/딥클린/이사 추가 (#1391)
  bundle/6.2605.2 머지 (2026-05-26)
  → OTA 출시: ota/6.2605.2-3 (2026-05-28)
  → release/6.2606.1 수록: #1452 (2026-06-02)
  → 정식 릴리즈: v6.2606.1 (2026-06-11)
```

단계가 아직 없으면 `→ (미도달)`로 표기한다.

## 가드레일

- read-only 스킬 — 어떤 ref도 생성/수정하지 않는다.
- patch-id `-` 판정은 확정, 제목 매칭은 `~`로 신뢰도를 구분해 표기한다.
- `git cherry`의 limit 인자(`$V`)를 빼먹으면 번들 전체 역사가 비교돼 결과가 오염된다 — 반드시 포함.
- 제목 사전 범위는 `--not $V`로 제한한다 (main 전체 역사 비교 금지 — 성능·오탐).
- per-commit `--contains` 조회는 번들당 커밋 ~20개 수준에서 허용. 대상 커밋이 수백 건이면 태그/브랜치 조회를 배치로 묶을 것.
