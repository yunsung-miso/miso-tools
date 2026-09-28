# 데이터 스키마

## raw.json — `scripts/fetch_prs.py` 출력

```json
{
  "meta": {
    "month": "2026-08",
    "repos": ["getmiso/miso-native", "..."],
    "fetched_at": "2026-09-01T00:00:00+00:00",
    "pr_count": 599,
    "file_cap_refetched": 10,
    "errors": [{"repo": "...", "error": "..."}]
  },
  "prs": [
    {
      "repo": "getmiso/miso-native",
      "number": 1919,
      "title": "[Refactor/AB-1] 진입점 없는 화면 제거",
      "author": {"login": "dev-a"},
      "state": "MERGED",
      "createdAt": "2026-08-09T01:00:00Z",
      "mergedAt": "2026-08-09T04:00:00Z",
      "baseRefName": "main",
      "headRefName": "refactor/AB-1/cleanup",
      "additions": 12, "deletions": 2087,
      "files": [{"path": "src/a.ts", "additions": 0, "deletions": 2087}],
      "reviews": [{"author": {"login": "dev-b"}, "state": "APPROVED"}],
      "labels": [], "isDraft": false,
      "_files_refetched": true
    }
  ]
}
```

`state`: `MERGED` / `CLOSED` / `OPEN`.
`reviews[].state`: `APPROVED` / `CHANGES_REQUESTED` / `COMMENTED` / `DISMISSED`.
`files[].path`는 repo 루트 기준 상대 경로. 의미 LOC 판정에 쓰인다.

### 직접 데이터를 넣을 때

CSV 등을 받았으면 위 구조로 변환한다. 최소 필수 필드:

| 필드 | 없으면 |
|---|---|
| `repo` · `number` · `title` · `author.login` | 집계 불가 |
| `mergedAt` | 머지율이 0%로 나온다 |
| `baseRefName` | 스택 PR 중복 제거가 안 된다 |
| `files[]` | 의미 LOC가 0. `additions`/`deletions`만 있으면 원값으로 대체 |
| `reviews[]` | 리뷰 지표 전체가 비어 나온다 |

## names.json — 이름 매핑 (선택)

```json
{ "dev-a": "개발자A", "dev-b": "개발자B", "dev-c": "개발자C" }
```

`aggregate.py --names names.json` 으로 넘기면 산출물이 실명으로 나온다 (§10).
매핑에 없는 아이디는 아이디 그대로 출력되므로, 그게 곧 "실명 미확인" 목록이다.

## repos.txt — 대상 repo (선택)

```
# FE 챕터 대상 repo
getmiso/miso-native
getmiso/design-tokens
# getmiso/ragent      ← 담당자 퇴사로 제외 (SKILL §11)
```

## metrics.json — `scripts/aggregate.py` 출력

| 키 | 내용 |
|---|---|
| `meta` | month · repos · warnings(합계 불일치) · stacked_prs · excluded_merge_prs |
| `summary` | total_pr · counted · human_pr · bot_pr · unique · backport · merge_rate_pct · authors · reviewers · human_review_events · bot_review_events · no_human_review(+pct) · changes_requested |
| `repos` | repo별 total · counted · unique · backport · merge_rate_pct |
| `devs` | 실명별 pr · unique · backport · merge_rate_pct · add/dele · add_dedup/del_dedup · repos[] · types{} |
| `types` | 작업유형 전체 분포 |
| `reviews` | 리뷰어별 events · prs · approve · comment · changes |
| `bot_reviews` | 봇별 events · approve · repos{} — **범위 변경 시 repo별로 뺄 수 있는 유일한 리뷰 지표** |
| `give_take` | 실명별 wrote · reviewed · gt |
| `no_review_by_repo` | repo별 no_review · human_pr · pct |
| `refactor` | Refactor PR 전수 (repo · number · author · add · dele · title) |

`meta.warnings`가 비어 있지 않으면 **원인을 찾아 보고한다.** 숫자를 맞추려고 서술을 고치지 않는다.

### repo별 분해가 불가능한 지표 (SKILL §11)

`devs[].types` · `devs[].add/dele` · `reviews` · `give_take` 는 PR 단위로는 repo를 알지만
**리뷰 이벤트에는 repo 정보가 없다.** 범위가 바뀐 달에는 이전 기준을 유지하고 표기한다.
`bot_reviews[].repos` 와 `no_review_by_repo` 는 repo별 내역이 있어 재계산할 수 있다.
