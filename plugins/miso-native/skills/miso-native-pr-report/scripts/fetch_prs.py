#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FE 챕터 PR 리포트 — GitHub 수집기.

여러 repo의 해당 월 생성 PR과 각 PR의 리뷰를 모아 raw.json 으로 저장한다.
페이지네이션·리뷰 호출·100파일 캡을 여기서 처리한다 — gh api 를 직접 부르지 않는다.

  python3 scripts/fetch_prs.py --month 2026-08 --out raw.json \
      --repo getmiso/miso-native --repo getmiso/design-tokens ...
  python3 scripts/fetch_prs.py --month 2026-08 --out raw.json --repos-file repos.txt

repos.txt 는 한 줄에 하나씩 `org/repo` (# 주석 허용).
gh CLI 인증이 필요하다: gh auth status
"""
import argparse, calendar, json, subprocess, sys, datetime as dt

FIELDS = ("number,title,author,state,additions,deletions,createdAt,mergedAt,"
          "baseRefName,headRefName,reviews,files,labels,isDraft")
FILE_CAP = 100          # gh 가 PR당 반환하는 파일 수 상한
CHUNK_DAYS = 7          # 주간 청크로 나눠 수집 후 단일콜과 합집합 대조


def sh(args, timeout=300):
    p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"{' '.join(args[:4])}… 실패\n{p.stderr.strip()[:800]}")
    return p.stdout


def month_range(month):
    y, m = (int(x) for x in month.split("-"))
    return dt.date(y, m, 1), dt.date(y, m, calendar.monthrange(y, m)[1])


def chunks(a, b, days):
    cur = a
    while cur <= b:
        end = min(cur + dt.timedelta(days=days - 1), b)
        yield cur, end
        cur = end + dt.timedelta(days=1)


def pr_list(repo, lo, hi):
    out = sh(["gh", "pr", "list", "--repo", repo, "--state", "all", "--limit", "1000",
              "--search", f"created:{lo}..{hi}", "--json", FIELDS])
    return json.loads(out or "[]")


def full_files(repo, number):
    """100파일 캡에 걸린 PR은 REST 로 전체 재수집한다."""
    out = sh(["gh", "api", f"repos/{repo}/pulls/{number}/files", "--paginate",
              "--jq", "[.[] | {path: .filename, additions, deletions}]"])
    files = []
    for line in out.strip().splitlines():
        if line.strip():
            files.extend(json.loads(line))
    return files


def collect(repo, month, verbose=True):
    lo, hi = month_range(month)
    seen, capped = {}, 0
    # 주간 청크
    for a, b in chunks(lo, hi, CHUNK_DAYS):
        for pr in pr_list(repo, a, b):
            seen[pr["number"]] = pr
    # 단일콜과 합집합 대조 (청크 경계 누락 방지)
    single = {pr["number"]: pr for pr in pr_list(repo, lo, hi)}
    only_single = set(single) - set(seen)
    only_chunk = set(seen) - set(single)
    seen.update(single)
    if verbose and (only_single or only_chunk):
        print(f"    대조: 단일콜에만 {len(only_single)}건 · 청크에만 {len(only_chunk)}건 → 합집합 사용",
              file=sys.stderr)
    # 100파일 캡 보정
    for n, pr in seen.items():
        if len(pr.get("files") or []) >= FILE_CAP:
            try:
                pr["files"] = full_files(repo, n)
                pr["_files_refetched"] = True
                capped += 1
            except Exception as e:
                pr["_files_refetch_error"] = str(e)[:200]
    for pr in seen.values():
        pr["repo"] = repo
    if verbose:
        print(f"  {repo}: {len(seen)}건 (100파일 캡 재수집 {capped}건)", file=sys.stderr)
    return list(seen.values()), capped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", required=True, help="YYYY-MM")
    ap.add_argument("--out", required=True)
    ap.add_argument("--repo", action="append", default=[], help="org/repo (여러 번)")
    ap.add_argument("--repos-file")
    a = ap.parse_args()

    repos = list(a.repo)
    if a.repos_file:
        for line in open(a.repos_file):
            line = line.split("#")[0].strip()
            if line:
                repos.append(line)
    if not repos:
        ap.error("--repo 또는 --repos-file 필요")

    try:
        sh(["gh", "auth", "status"], timeout=30)
    except Exception:
        print("gh 인증 안 됨 — `gh auth login` 먼저 실행하세요.", file=sys.stderr)
        return 2

    prs, capped, errs = [], 0, []
    print(f"{a.month} · {len(repos)} repo 수집", file=sys.stderr)
    for r in repos:
        try:
            rows, c = collect(r, a.month)
            prs += rows
            capped += c
        except Exception as e:
            errs.append({"repo": r, "error": str(e)[:400]})
            print(f"  {r}: 실패 — {str(e)[:200]}", file=sys.stderr)

    payload = {
        "meta": {
            "month": a.month,
            "repos": repos,
            "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "pr_count": len(prs),
            "file_cap_refetched": capped,
            "errors": errs,
        },
        "prs": prs,
    }
    with open(a.out, "w") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print(f"→ {a.out}  PR {len(prs)}건" + (f" · repo 실패 {len(errs)}건" if errs else ""),
          file=sys.stderr)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
