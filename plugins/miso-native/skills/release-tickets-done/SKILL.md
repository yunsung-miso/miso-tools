---
name: release-tickets-done
description: main 의 두 커밋 SHA 범위(앞 SHA..뒤 SHA)에서 PR 제목의 Linear 티켓 ID 를 모두 뽑아, 해당 티켓들을 Linear 에서 일괄 `Done` 으로 옮긴다. "출시된 티켓 done 처리", "릴리즈 끝난 티켓 정리", "이번 main 머지된 티켓들 close" 같은 요청에 사용. 보통 `release-to-main` PR 머지 후 마지막 단계.
---

# Release Tickets Done Skill

릴리즈가 main 까지 머지된 뒤, 그 사이에 들어간 PR 들의 Linear 티켓을 일괄 `Done` 으로 옮긴다. `release-to-main` 의 후속 단계.

## 입력

- `fromSha`: 범위의 시작 커밋 (이전 릴리즈의 첫 커밋, 보통 `Set version to {prev}` 같은 release-create 커밋). **포함**.
- `toSha`: 범위의 끝 커밋 (이번 릴리즈 마지막으로 main 에 들어간 커밋). **포함**.

→ git 범위로는 `fromSha^..toSha` (또는 `fromSha~1..toSha`). main 의 first-parent 만.

사용자가 SHA 대신 "지난번 릴리즈부터 지금까지" 같이 말하면 PR/tag 로부터 SHA 를 역추적한다.

## 절차

### 1. 범위 안의 PR/커밋 나열 + 티켓 추출

```bash
git log --format='%H%x09%s' --first-parent "{fromSha}~1..{toSha}"
```

> `main` 을 positional 로 붙이면 `B OR main` 합집합으로 해석돼 `{toSha}` 이후 main 에 들어간 커밋이 끼어들 수 있다. 범위는 반드시 `~1..` 형식 + 더블 쿼트 (zsh extended_glob 의 `^` 충돌 회피).

티켓 prefix 정규식 (현 프로젝트에서 쓰이는 팀들):

```
(PRD|MIS|IBP|MPP|AIP)-[0-9]+
```

같은 티켓이 여러 번 등장할 수 있다 — `sort -u` 로 unique 화.

> **티켓 prefix 누락 커밋**도 자주 있다 (`[Bugfix] ...`, `docs:`, `chore:`, `Migrate ...` 등 — 보통 작은 hotfix / 인프라 변경). 진행 전 사용자에게 **"티켓 prefix 가 없는 커밋 N건은 자동 매칭 불가, 어떻게 처리할까요?"** 한 번 묻고 무시할지/수동 매핑할지 결정.

### 2. 팀 매핑

| 티켓 prefix | Linear team name |
|---|---|
| `PRD` | Product |
| `AIP` | AI Product |
| `IBP` | IB Product |
| `MPP` | MP Product |
| `MIS` | Miso-All |

`Done` 상태는 **모든 팀에 동일하게 존재** (확인 완료, 2026-05-28). state 인자로 `"Done"` 만 넘기면 됨.

### 3. 현재 상태 일괄 조회 (skip 판단)

각 티켓에 대해 `mcp__linear-server__get_issue` 병렬 호출. status 분류:

| 현재 status | 처리 |
|---|---|
| `Done` (statusType: completed) | **skip** — 이미 Done |
| `Test Passed` (statusType: completed) | → `Done` 이동 (QA 만 통과한 상태, 출시 됐으니 마무리) |
| `Ready to Deploy` (statusType: completed) | → `Done` |
| `In Review` / `In Testing` / `Ready for QA` / `In Progress` (statusType: started) | → `Done` |
| `Backlog` / `Todo` (statusType: unstarted) | **사용자 확인 필요** — 보통 PR 만 들어가고 티켓 상태는 안 옮긴 경우지만, 의도된 케이스도 있어서 한 번 물어본다 |
| `Canceled` / `Duplicate` | **skip** + 사용자에게 보고 — PR 은 들어갔는데 티켓이 취소돼 있는 건 비정상, 확인 필요 |

### 4. 사용자 확인 (필수)

외부 시스템 일괄 변경이라 사전 승인 받는다. 다음을 표로 보여준다:

- 이동 대상 N개 (티켓 + 현재 status)
- skip M개 (이미 Done)
- 모호 케이스 K개 (Backlog/Todo/Canceled 등)

승인 후에만 mutation 진행.

### 5. 일괄 Done 처리

```ts
mcp__linear-server__save_issue({ id: 'PRD-XXXX', state: 'Done' })
```

각 티켓마다 호출. 같은 응답에서 병렬로 묶어 보낸다. 응답에서 `status: "Done"` 확인.

### 6. 결과 보고

표로 정리:

| 티켓 | 이전 상태 | 결과 |
|---|---|---|
| PRD-6504 | Test Passed | ✅ Done |
| PRD-6497 | In Review | ✅ Done |
| ... | ... | ... |

skip 된 것도 같이 나열 (왜 skip 했는지 사유 포함).

## 가드레일

- **외부 시스템 변경** — 반드시 step 4 의 사용자 승인을 받은 뒤에만 `save_issue` 호출.
- prefix 가 없는 커밋은 **자동 매칭하지 않는다** — 추측 금지.
- 같은 티켓이 여러 PR 에 걸려 있어도 (cherry-pick fan-out 등) 한 번만 Done 으로 옮긴다.
- 이미 `Canceled` / `Duplicate` 인 티켓은 건드리지 않는다 — 의도한 종료 상태일 수 있음.
- 팀이 새로 생기면 step 2 의 매핑 표를 업데이트한다 — `mcp__linear-server__list_teams` 로 확인.

## release-to-main 과의 관계

전형적인 흐름:

1. `release-to-main` 으로 release/{version} → main PR 생성
2. PR 머지
3. **이 스킬** 로 그 PR 묶음에 들어간 티켓들 일괄 Done

`fromSha` 는 보통 이전 릴리즈의 `Set version to {prev}` 커밋, `toSha` 는 이번 머지의 마지막 커밋.

## 참고

- 첫 사용 시점 (2026-05-28): release/6.2605.2 → main 머지 (3eda87491..74ed7645e 범위, 38 티켓 추출, 17 skip / 18 Done 이동 / 3 prefix 없음 보고)
- Linear MCP: `mcp__linear-server__get_issue`, `mcp__linear-server__save_issue`, `mcp__linear-server__list_issue_statuses`
- 팀 ID 캐시 (자주 안 바뀜, 변경 시 list_teams 로 갱신):
  - Product `fda6c954-ea47-4038-a1e0-a2ee74168355`
  - AI Product `03bfede6-1721-4685-af09-87d2c3915714`
  - IB Product `7d1e851a-054d-4a63-a813-827233419e24`
  - MP Product `baeef7ec-2144-469e-b7cf-460bc5618473`
  - Miso-All `10d81c42-445b-4d5b-b1ca-913fc21715bb`
