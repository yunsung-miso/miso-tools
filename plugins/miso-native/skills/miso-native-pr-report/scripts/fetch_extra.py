#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""리드타임용 추가 수집: PR별 커밋 작성 시각 · 머지 커밋 · head 브랜치.

  python3 fetch_extra.py ../repos.txt 2026-05 2026-06 2026-07 2026-08 2026-09

출력: extra-YYYY-MM.json  {"repo#number": {"first_commit_at", "merge_sha", "head", "commits"}}
fetch_months.py와 같은 청크·재시도·반분할 규칙. repo 단위 캐시(cache-extra/)로 이어받기.
"""
import calendar, datetime as dt, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_months import sh, CHUNK_DAYS  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


QUERY = """{ search(query: "repo:%s is:pr created:%s..%s", type: ISSUE, first: 50%s) {
  pageInfo { hasNextPage endCursor }
  nodes { ... on PullRequest { number headRefName mergeCommit { oid }
    commits(first: 100) { nodes { commit { authoredDate } } } } } } }"""


def pr_list(repo, lo, hi):
    """gh pr list --json commits는 commits×authors를 100×100으로 요청해 노드 한도를 넘는다.
    필요한 필드만 직접 GraphQL로 받는다 (50 PR × 100 커밋 = 5,000 노드)."""
    rows, after = [], ""
    while True:
        q = QUERY % (repo, lo, hi, f', after: "{after}"' if after else "")
        data = json.loads(sh(["gh", "api", "graphql", "-f", f"query={q}"]))["data"]["search"]
        for n in data["nodes"]:
            if not n:
                continue
            rows.append(dict(number=n["number"], headRefName=n.get("headRefName"),
                             mergeCommit=n.get("mergeCommit"),
                             commits=[c["commit"] for c in n["commits"]["nodes"]]))
        if not data["pageInfo"]["hasNextPage"]:
            return rows
        after = data["pageInfo"]["endCursor"]


def collect(repo, month):
    y, m = (int(x) for x in month.split("-"))
    lo, hi = dt.date(y, m, 1), dt.date(y, m, calendar.monthrange(y, m)[1])
    rows, cur = {}, lo
    while cur <= hi:
        end = min(cur + dt.timedelta(days=CHUNK_DAYS - 1), hi)
        for pr in pr_list(repo, cur, end):
            cs = pr.get("commits") or []
            dates = [c.get("authoredDate") for c in cs if c.get("authoredDate")]
            rows[f"{repo}#{pr['number']}"] = dict(
                first_commit_at=min(dates) if dates else None,
                merge_sha=(pr.get("mergeCommit") or {}).get("oid"),
                head=pr.get("headRefName"),
                commits=len(cs))
        cur = end + dt.timedelta(days=1)
    return rows


def main():
    repos = [l.split("#")[0].strip() for l in open(sys.argv[1]) if l.split("#")[0].strip()]
    for month in sys.argv[2:]:
        cdir = os.path.join(HERE, "cache-extra", month)
        os.makedirs(cdir, exist_ok=True)
        out, errs = {}, []
        for r in repos:
            path = os.path.join(cdir, r.replace("/", "__") + ".json")
            if os.path.exists(path):
                rows = json.load(open(path))
            else:
                try:
                    rows = collect(r, month)
                    json.dump(rows, open(path, "w"))
                except Exception as e:
                    errs.append(r)
                    print(f"  {month} {r}: 실패 — {str(e)[:200]}", file=sys.stderr)
                    continue
            out.update(rows)
            print(f"  {month} {r}: {len(rows)}건", file=sys.stderr)
        json.dump(out, open(os.path.join(HERE, f"extra-{month}.json"), "w"))
        print(f"→ extra-{month}.json {len(out)}건" + (f" · 실패 {errs}" if errs else ""), file=sys.stderr)


if __name__ == "__main__":
    main()
