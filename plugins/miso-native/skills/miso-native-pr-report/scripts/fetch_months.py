#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""스킬 fetch_prs.py 와 같은 출력(raw-YYYY-MM.json)을 여러 달 순차로 만든다.

  python3 fetch_months.py repos.txt 2026-05 2026-06 2026-07 2026-08 2026-09

차이: 504 재시도 + 실패 시 기간 반분할, 단일콜 대조 실패는 청크 합집합으로 대체,
repo 단위 캐시(cache/YYYY-MM/<repo>.json)로 재실행 시 이어받기.
"""
import calendar, datetime as dt, json, os, subprocess, sys, time

FIELDS = ("number,title,author,state,additions,deletions,createdAt,mergedAt,"
          "baseRefName,headRefName,reviews,files,labels,isDraft")
FILE_CAP = 100
CHUNK_DAYS = 7
HERE = os.path.dirname(os.path.abspath(__file__))


def sh(args, timeout=300):
    for attempt in range(4):
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        if p.returncode == 0:
            return p.stdout
        err = p.stderr.lower()
        if any(c in err for c in ("504", "502", "503", "stream", "timeout")):
            time.sleep(3 * (attempt + 1))
            continue
        if "rate limit" in err:
            time.sleep(60)
            continue
        break
    raise RuntimeError(p.stderr.strip()[:400])


def pr_list(repo, lo, hi):
    try:
        out = sh(["gh", "pr", "list", "--repo", repo, "--state", "all", "--limit", "1000",
                  "--search", f"created:{lo}..{hi}", "--json", FIELDS])
        return json.loads(out or "[]")
    except RuntimeError:
        if lo >= hi:
            raise
        mid = lo + (hi - lo) // 2
        return pr_list(repo, lo, mid) + pr_list(repo, mid + dt.timedelta(days=1), hi)


def full_files(repo, number):
    out = sh(["gh", "api", f"repos/{repo}/pulls/{number}/files", "--paginate",
              "--jq", "[.[] | {path: .filename, additions, deletions}]"])
    files = []
    for line in out.strip().splitlines():
        if line.strip():
            files.extend(json.loads(line))
    return files


def collect(repo, month):
    y, m = (int(x) for x in month.split("-"))
    lo, hi = dt.date(y, m, 1), dt.date(y, m, calendar.monthrange(y, m)[1])
    seen, cur = {}, lo
    while cur <= hi:
        end = min(cur + dt.timedelta(days=CHUNK_DAYS - 1), hi)
        for pr in pr_list(repo, cur, end):
            seen[pr["number"]] = pr
        cur = end + dt.timedelta(days=1)
    try:
        single = {pr["number"]: pr for pr in pr_list(repo, lo, hi)}
        extra = set(single) - set(seen)
        if extra:
            print(f"    대조: 단일콜에만 {len(extra)}건 → 합집합", file=sys.stderr)
        seen.update(single)
    except RuntimeError:
        print("    대조: 단일콜 실패 → 청크 합집합만 사용", file=sys.stderr)
    capped = 0
    for n, pr in seen.items():
        if len(pr.get("files") or []) >= FILE_CAP:
            try:
                pr["files"] = full_files(repo, n)
                pr["_files_refetched"] = True
                capped += 1
            except Exception as e:
                pr["_files_refetch_error"] = str(e)[:200]
        pr["repo"] = repo
    return list(seen.values()), capped


def main():
    repos = [l.split("#")[0].strip() for l in open(sys.argv[1]) if l.split("#")[0].strip()]
    for month in sys.argv[2:]:
        cdir = os.path.join(HERE, "cache", month)
        os.makedirs(cdir, exist_ok=True)
        prs, capped, errs = [], 0, []
        print(f"{month} · {len(repos)} repo", file=sys.stderr)
        for r in repos:
            path = os.path.join(cdir, r.replace("/", "__") + ".json")
            if os.path.exists(path):
                rows, c = json.load(open(path))
            else:
                try:
                    rows, c = collect(r, month)
                    json.dump([rows, c], open(path, "w"), ensure_ascii=False)
                except Exception as e:
                    errs.append({"repo": r, "error": str(e)[:400]})
                    print(f"  {r}: 실패 — {str(e)[:200]}", file=sys.stderr)
                    continue
            prs += rows; capped += c
            print(f"  {r}: {len(rows)}건 (캡 재수집 {c})", file=sys.stderr)
        meta = dict(month=month, repos=repos, pr_count=len(prs), file_cap_refetched=capped,
                    errors=errs, fetched_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))
        json.dump({"meta": meta, "prs": prs},
                  open(os.path.join(HERE, f"raw-{month}.json"), "w"), ensure_ascii=False, indent=1)
        print(f"→ raw-{month}.json  PR {len(prs)}건" + (f" · 실패 {len(errs)}" if errs else ""),
              file=sys.stderr)


if __name__ == "__main__":
    main()
