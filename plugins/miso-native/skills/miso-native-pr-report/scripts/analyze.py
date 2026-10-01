#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""raw-YYYY-MM.json → ragent 제외 → 스킬 aggregate.py 정의로 월별 지표 + 추이용 파생 지표.

  python3 analyze.py 2026-05 2026-06 2026-07 2026-08 2026-09

출력: metrics-YYYY-MM.json (aggregate.py 결과) · extras.json (월별 파생 지표)
"""
import json, os, statistics, subprocess, sys, datetime as dt
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SKILL = (os.path.join(os.environ["CLAUDE_SKILL_DIR"], "scripts") if os.environ.get("CLAUDE_SKILL_DIR") else os.path.dirname(os.path.abspath(__file__)) if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "aggregate.py")) else os.path.expanduser("~/.claude/skills/miso-native-pr-report/scripts"))
sys.path.insert(0, SKILL)
import aggregate as A  # noqa: E402

roster = json.load(open(os.path.join(ROOT, "roster.json")))
EXCLUDED = set(roster["excluded_repos"])
names = json.load(open(os.path.join(ROOT, "names.json")))
disp = lambda l: names.get(l, l)
APP = {disp(x) for x in roster["app_chapter"]}


def ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def q(vals, p):
    if not vals:
        return None
    v = sorted(vals)
    return v[min(len(v) - 1, int(round(p * (len(v) - 1))))]


def extras(prs):
    counted, unique, human = [], [], []
    for pr in prs:
        title = pr.get("title") or ""
        if A.is_merge_pr(pr):
            continue
        login = (pr.get("author") or {}).get("login", "")
        bot = A.is_bot(login)
        bp = bool(A.BACKPORT_PAT.search(title))
        counted.append(pr)
        if not bot:
            human.append(pr)
            if not bp:
                unique.append(pr)
    by = defaultdict(int)
    for p in unique:
        by[disp(p["author"]["login"])] += 1
    top = sorted(by.values(), reverse=True)
    n = len(unique) or 1
    conc = {k: round(sum(top[:k]) / n * 100, 1) for k in (1, 2, 3, 5)}

    first, lead = [], []
    rev_prs = defaultdict(set)
    for pr in human:
        a = pr["author"]["login"]
        c = ts(pr.get("createdAt"))
        hs = [ts(r.get("submittedAt")) for r in pr.get("reviews") or []
              if (r.get("author") or {}).get("login") not in (None, "", a)
              and not A.is_bot((r.get("author") or {}).get("login")) and r.get("submittedAt")]
        if hs:
            first.append((min(hs) - c).total_seconds() / 3600)
        if pr.get("mergedAt"):
            lead.append((ts(pr["mergedAt"]) - c).total_seconds() / 3600)
        for r in pr.get("reviews") or []:
            rl = (r.get("author") or {}).get("login")
            if rl and rl != a and not A.is_bot(rl):
                rev_prs[disp(rl)].add((pr["repo"], pr["number"]))
    rtop = sorted((len(v) for v in rev_prs.values()), reverse=True)
    rtot = sum(rtop) or 1
    one_person_repos = []
    per_repo = defaultdict(lambda: defaultdict(int))
    for p in unique:
        per_repo[p["repo"]][disp(p["author"]["login"])] += 1
    for r, d in per_repo.items():
        tot = sum(d.values())
        mx = max(d.values())
        if tot >= 10 and mx / tot >= 0.9:
            one_person_repos.append(dict(repo=r, top=max(d, key=d.get), share=round(mx / tot * 100)))
    return dict(
        concentration=conc,
        review_top3_pct=round(sum(rtop[:3]) / rtot * 100, 1),
        first_review_h={k: (round(q(first, p), 2) if first else None)
                        for k, p in (("p25", .25), ("p50", .5), ("p75", .75), ("p90", .9))},
        lead_h={k: (round(q(lead, p), 2) if lead else None)
                for k, p in (("p25", .25), ("p50", .5), ("p75", .75), ("p90", .9))},
        one_person_repos=one_person_repos,
        per_repo_dev={r: dict(d) for r, d in per_repo.items()},
        app_unique=sum(v for k, v in by.items() if k in APP),
    )


def main():
    out = {}
    for month in sys.argv[1:]:
        raw = json.load(open(os.path.join(HERE, f"raw-{month}.json")))
        if raw["meta"].get("errors"):
            print(f"⚠ {month} 수집 오류: {raw['meta']['errors']}", file=sys.stderr)
        dropped = [p for p in raw["prs"] if p["repo"] in EXCLUDED]
        raw["prs"] = [p for p in raw["prs"] if p["repo"] not in EXCLUDED]
        raw["meta"]["repos"] = [r for r in raw["meta"]["repos"] if r not in EXCLUDED]
        raw["meta"]["excluded"] = {r: sum(1 for p in dropped if p["repo"] == r) for r in EXCLUDED}
        f9 = os.path.join(HERE, f"raw9-{month}.json")
        json.dump(raw, open(f9, "w"), ensure_ascii=False)
        subprocess.run([sys.executable, os.path.join(SKILL, "aggregate.py"), "--in", f9,
                        "--out", os.path.join(HERE, f"metrics-{month}.json"),
                        "--names", os.path.join(ROOT, "names.json")])
        out[month] = extras(raw["prs"])
        out[month]["excluded_prs"] = raw["meta"]["excluded"]
    json.dump(out, open(os.path.join(HERE, "extras.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
