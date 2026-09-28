#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FE 챕터 PR 리포트 — 집계기. SKILL.md §1의 불변 정의를 코드로 고정한다.

  python3 scripts/aggregate.py --in raw.json --out metrics.json [--names names.json]

정의를 바꾸면 과거 리포트와 비교 불가능해진다. 사용자가 명시적으로 요청하지 않는 한
아래 상수만 보수적으로 확장한다. 합계 검증을 내장하며 불일치 시 경고를 낸다.
"""
import argparse, json, re, sys
from collections import defaultdict

# ── 봇 (SKILL §1). `[bot]` 접미사가 없는 봇을 반드시 여기 넣는다.
BOTS = {"dependabot", "gemini-code-assist", "cursor", "copilot", "copilot-pull-request-reviewer",
        "chatgpt-codex-connector", "cubic-dev-ai", "git-configurator", "datadog-official"}
def is_bot(login):
    l = (login or "").lower()
    return (l in BOTS or l.endswith("[bot]") or l.startswith("app/")
            or any(b in l for b in ("dependabot", "copilot", "codex", "cubic-dev", "datadog")))

# ── 릴리즈/번들 병합 PR
MERGE_PAT = [re.compile(p, re.I) for p in (
    r"^release/[\d.]+\s+to\s+", r"^\[[\d.]+\]\s*merge\s+to\s+", r"\[bundle/[\d.]+\]\s*병합",
    r"^merge\s+release/", r"^\[release\]\s*merge")]
# 제목이 제각각이라("[Bundle/x] 릴리즈 브랜치 병합", "[Release] release x to master") 브랜치로도 판정한다
MERGE_HEAD = re.compile(r"^(release|bundle|codepush)/", re.I)
MERGE_BASE = re.compile(r"^(main|master|release/|bundle/|codepush/)", re.I)


def is_merge_pr(pr):
    title = pr.get("title") or ""
    if any(p.search(title) for p in MERGE_PAT):
        return True
    return bool(MERGE_HEAD.match(pr.get("headRefName") or "") and MERGE_BASE.match(pr.get("baseRefName") or ""))

# ── 백포트 접미사
BACKPORT_PAT = re.compile(r"\((?:bundle|release|codepush)/\d+[\d.]*\)\s*$|\(\d+\.\d[\d.]*\)\s*$", re.I)

# ── 작업유형: [Feature/TICKET] 대괄호 안쪽 첫 토큰
TYPE_MAP = {"feature": "Feature", "feat": "Feature", "bugfix": "Bugfix", "bugix": "Bugfix",
            "bug": "Bugfix", "fix": "Fix", "hotfix": "Fix", "chore": "Chore", "ci": "Chore",
            "build": "Chore", "deps": "Chore", "refactor": "Refactor", "docs": "Docs",
            "doc": "Docs", "test": "Test", "tests": "Test"}
BRACKET = re.compile(r"^\s*\[([^\]]+)\]")
COLON = re.compile(r"^\s*([A-Za-z]+)(?:\([^)]*\))?!?\s*[:/]")   # feat: · feat(host): · Feature/…
TICKET_ONLY = re.compile(r"^[A-Z]{2,}-\d+$")

# ── 의미 LOC 제외
SKIP_PARTS = ("/dist/", "/build/", "/generated/", "/__snapshots__/", "/vendor/", "/pods/",
              "node_modules/", "/.next/", "/coverage/")
SKIP_NAMES = ("package-lock.json", "yarn.lock", "pnpm-lock.yaml", "gemfile.lock",
              "podfile.lock", "cargo.lock", "composer.lock")
SKIP_SUFFIX = (".min.js", ".min.css", ".map", ".pbxproj", ".lock", ".snap")
DATA_EXT = (".json", ".yaml", ".yml", ".svg", ".css", ".csv", ".xml")
DATA_LINE_CAP = 2000     # 단일 파일 2,000줄 이상 데이터 파일 제외

STACK_BASE = re.compile(r"^[a-z]+/([A-Z]{2,}-\d+)(?:/|$)")


def meaningful(f):
    p = (f.get("path") or "").lower()
    if any(s in p for s in SKIP_PARTS) or p.rsplit("/", 1)[-1] in SKIP_NAMES:
        return False
    if p.endswith(SKIP_SUFFIX):
        return False
    if p.endswith(DATA_EXT) and (f.get("additions", 0) + f.get("deletions", 0)) >= DATA_LINE_CAP:
        return False
    return True


def work_type(title):
    m = BRACKET.match(title or "")
    if m:
        inner = m.group(1).split("/")[0].strip()
        if TICKET_ONLY.match(inner) or re.match(r"^[A-Z]{2,}-\d+$", inner):
            return "미표기"
        t = TYPE_MAP.get(inner.lower())
        return t or "기타"
    m = COLON.match(title or "")
    if m:
        return TYPE_MAP.get(m.group(1).lower(), "기타")
    return "기타"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--names", help='{"github-id": "실명"} JSON')
    a = ap.parse_args()

    raw = json.load(open(a.src))
    prs, meta = raw["prs"], raw.get("meta", {})
    names = json.load(open(a.names)) if a.names else {}
    disp = lambda l: names.get(l, l)

    warn = []
    counted, merge_prs, bot_prs, backports = [], [], [], []

    for pr in prs:
        title = pr.get("title") or ""
        login = (pr.get("author") or {}).get("login", "")
        if is_merge_pr(pr):
            merge_prs.append(pr); continue
        if is_bot(login):
            bot_prs.append(pr); pr["_bot"] = True
        pr["_type"] = work_type(title)
        pr["_backport"] = bool(BACKPORT_PAT.search(title))
        if pr["_backport"]:
            backports.append(pr)
        pr["_author"] = disp(login)
        f = [x for x in (pr.get("files") or []) if meaningful(x)]
        pr["_add"] = sum(x.get("additions", 0) for x in f)
        pr["_del"] = sum(x.get("deletions", 0) for x in f)
        counted.append(pr)

    unique = [p for p in counted if not p["_backport"] and not p.get("_bot")]
    human = [p for p in counted if not p.get("_bot")]

    # ── repo 집계
    repos = defaultdict(lambda: dict(total=0, counted=0, unique=0, merged=0, backport=0))
    for pr in counted:
        r = repos[pr["repo"]]
        r["counted"] += 1
        r["merged"] += 1 if pr.get("mergedAt") else 0
        if pr["_backport"]:
            r["backport"] += 1
        elif not pr.get("_bot"):
            r["unique"] += 1
    for pr in prs:
        repos[pr["repo"]]["total"] += 1

    # ── 개발자 집계
    devs = defaultdict(lambda: dict(pr=0, unique=0, backport=0, merged=0, add=0, dele=0,
                                    repos=set(), types=defaultdict(int)))
    for pr in counted:
        if pr.get("_bot"):
            continue
        d = devs[pr["_author"]]
        d["pr"] += 1
        d["merged"] += 1 if pr.get("mergedAt") else 0
        d["repos"].add(pr["repo"])
        if pr["_backport"]:
            d["backport"] += 1
        else:
            d["add"] += pr["_add"]; d["dele"] += pr["_del"]   # 의미 LOC는 원작업만 (백포트는 같은 코드의 복제)
            d["unique"] += 1
            d["types"][pr["_type"]] += 1

    # ── 스택 PR 중복 제거 (repo, 작성자, 티켓) 그룹의 최대 diff로 근사
    groups = defaultdict(list)
    for pr in unique:
        m = STACK_BASE.match(pr.get("baseRefName") or "")
        if m:
            groups[(pr["repo"], pr["_author"], m.group(1))].append(pr)
    dedup = defaultdict(lambda: [0, 0])
    stacked = 0
    for (repo, author, _), g in groups.items():
        if len(g) < 2:
            continue
        stacked += len(g)
        dedup[author][0] += max(p["_add"] for p in g) - sum(p["_add"] for p in g)
        dedup[author][1] += max(p["_del"] for p in g) - sum(p["_del"] for p in g)

    # ── 리뷰 (셀프·봇 제외)
    rev = defaultdict(lambda: dict(events=0, prs=set(), approve=0, comment=0, changes=0))
    botrev = defaultdict(lambda: dict(events=0, repos=defaultdict(int), approve=0))
    no_review = defaultdict(int)
    for pr in human:
        author = (pr.get("author") or {}).get("login", "")
        human_reviewed = False
        for r in (pr.get("reviews") or []):
            rl = (r.get("author") or {}).get("login", "")
            if not rl or rl == author:
                continue
            st = (r.get("state") or "").upper()
            if is_bot(rl):
                b = botrev[rl]; b["events"] += 1; b["repos"][pr["repo"]] += 1
                if st == "APPROVED":
                    b["approve"] += 1
                continue
            human_reviewed = True
            e = rev[disp(rl)]
            e["events"] += 1; e["prs"].add((pr["repo"], pr["number"]))
            if st == "APPROVED": e["approve"] += 1
            elif st == "CHANGES_REQUESTED": e["changes"] += 1
            else: e["comment"] += 1
        if not human_reviewed:
            no_review[pr["repo"]] += 1

    human_by_repo = defaultdict(int)
    for pr in human:
        human_by_repo[pr["repo"]] += 1

    # ── 검증 (SKILL §8-1)
    def chk(label, got, want):
        if got != want:
            warn.append(f"{label}: {got} != {want}")
    chk("개발자별 PR 합 = 사람 PR", sum(d["pr"] for d in devs.values()), len(human))
    chk("고유 + 백포트 + 봇 = 집계 대상",
        len(unique) + len(backports) + len([p for p in counted if p.get("_bot")]), len(counted))
    chk("repo 고유작업 합 = 고유 작업", sum(r["unique"] for r in repos.values()), len(unique))
    chk("유형 분포 합 = 고유 작업",
        sum(sum(d["types"].values()) for d in devs.values()), len(unique))
    nr, hp = sum(no_review.values()), len(human)
    if hp and not (0 <= nr <= hp):
        warn.append(f"리뷰 커버리지 범위 이상: {nr}/{hp}")

    types_total = defaultdict(int)
    for d in devs.values():
        for t, c in d["types"].items():
            types_total[t] += c

    out = dict(
        meta=dict(month=meta.get("month"), repos=meta.get("repos", []),
                  fetched_at=meta.get("fetched_at"), warnings=warn,
                  stacked_prs=stacked, excluded_merge_prs=len(merge_prs)),
        summary=dict(total_pr=len(prs), counted=len(counted), human_pr=len(human),
                     bot_pr=len([p for p in counted if p.get("_bot")]),
                     unique=len(unique), backport=len(backports),
                     merged=sum(1 for p in counted if p.get("mergedAt")),
                     merge_rate_pct=round(sum(1 for p in counted if p.get("mergedAt")) /
                                          len(counted) * 100) if counted else 0,
                     authors=len(devs), reviewers=len(rev),
                     human_review_events=sum(e["events"] for e in rev.values()),
                     bot_review_events=sum(b["events"] for b in botrev.values()),
                     no_human_review=nr,
                     no_human_review_pct=round(nr / hp * 100) if hp else 0,
                     changes_requested=sum(e["changes"] for e in rev.values())),
        repos={k: dict(v, merge_rate_pct=round(v["merged"] / v["counted"] * 100) if v["counted"] else 0)
               for k, v in sorted(repos.items(), key=lambda x: -x[1]["unique"])},
        devs={k: dict(pr=v["pr"], unique=v["unique"], backport=v["backport"],
                      merge_rate_pct=round(v["merged"] / v["pr"] * 100) if v["pr"] else 0,
                      add=v["add"], dele=v["dele"],
                      add_dedup=v["add"] + dedup[k][0], del_dedup=v["dele"] + dedup[k][1],
                      repos=sorted(v["repos"]), types=dict(v["types"]))
              for k, v in sorted(devs.items(), key=lambda x: -x[1]["unique"])},
        types=dict(sorted(types_total.items(), key=lambda x: -x[1])),
        reviews={k: dict(events=v["events"], prs=len(v["prs"]), approve=v["approve"],
                         comment=v["comment"], changes=v["changes"])
                 for k, v in sorted(rev.items(), key=lambda x: -len(x[1]["prs"]))},
        bot_reviews={k: dict(events=v["events"], approve=v["approve"],
                             repos=dict(sorted(v["repos"].items(), key=lambda x: -x[1])))
                     for k, v in sorted(botrev.items(), key=lambda x: -x[1]["events"])},
        give_take={k: dict(wrote=devs[k]["pr"], reviewed=rev[k]["prs"] and len(rev[k]["prs"]) or 0,
                           gt=round((len(rev[k]["prs"]) / devs[k]["pr"]), 1) if devs[k]["pr"] else None)
                   for k in devs},
        no_review_by_repo={k: dict(no_review=v, human_pr=human_by_repo[k],
                                   pct=round(v / human_by_repo[k] * 100) if human_by_repo[k] else 0)
                           for k, v in sorted(no_review.items(), key=lambda x: -x[1])},
        refactor=[dict(repo=p["repo"], number=p["number"], author=p["_author"],
                       add=p["_add"], dele=p["_del"], title=p["title"])
                  for p in unique if p["_type"] == "Refactor"],
    )
    with open(a.out, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    s = out["summary"]
    print(f"→ {a.out}", file=sys.stderr)
    print(f"  집계 대상 {s['counted']} (사람 {s['human_pr']} + 봇 {s['bot_pr']}) · "
          f"고유 작업 {s['unique']} · 백포트 {s['backport']} · 머지율 {s['merge_rate_pct']}%",
          file=sys.stderr)
    print(f"  사람 리뷰 {s['human_review_events']} · 봇 리뷰 {s['bot_review_events']} · "
          f"리뷰 없이 머지 {s['no_human_review']}/{s['human_pr']} = {s['no_human_review_pct']}% · "
          f"CR {s['changes_requested']}", file=sys.stderr)
    if warn:
        print("  ⚠ 합계 불일치 — 원인을 찾아 보고할 것:", file=sys.stderr)
        for w in warn:
            print(f"    {w}", file=sys.stderr)
    return 1 if warn else 0


if __name__ == "__main__":
    sys.exit(main())
