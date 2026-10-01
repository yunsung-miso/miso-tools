#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부분월로 발행한 달을 말일 기준으로 다시 낼 때 쓰는 두 단계 도구.

  python3 remonth.py snapshot <월폴더> YYYY-MM <태그>   # 발행본 보존 + 그 달 캐시 이동(재수집되게)
  python3 remonth.py diff     <월폴더> YYYY-MM <태그>   # snapshot-<태그> vs 현재 — 바뀐 값만 * 표시

snapshot 뒤 순서: fetch_months.py <repos.txt> YYYY-MM → fetch_extra.py <repos.txt> YYYY-MM
→ analyze.py (1월부터 전부) → delivery.py → compare.py → diff. 다른 달 지표가 바뀌면 멈추고 원인부터 찾는다.
"""
import json, os, shutil, sys
from collections import Counter

KEEP = ["raw-{m}.json", "raw9-{m}.json", "extra-{m}.json", "metrics-{m}.json", "extras.json",
        "delivery.json", "compare.json"]


def snapshot(w, m, tag):
    s = os.path.join(w, f"snapshot-{tag}")
    os.makedirs(s, exist_ok=True)
    for f in os.listdir(w):
        if f.endswith((".md", ".html")) or f.startswith("metrics-") or f in [k.format(m=m) for k in KEEP]:
            shutil.copy2(os.path.join(w, f), s)
    for d in ("cache", "cache-extra"):
        src = os.path.join(w, d, m)
        if os.path.exists(src):
            shutil.move(src, os.path.join(s, f"{d}-{m}"))
    print("보존:", sorted(os.listdir(s)))


def diff(w, m, tag):
    s = os.path.join(w, f"snapshot-{tag}")
    L = lambda d, f: json.load(open(os.path.join(d, f)))
    o, n = L(s, f"metrics-{m}.json"), L(w, f"metrics-{m}.json")
    eo, en = L(s, "extras.json")[m], L(w, "extras.json")[m]
    co, cn = L(s, "compare.json"), L(w, "compare.json")
    row = lambda k, a, b: print(f"{'  ' if a == b else '* '}{k}: {a} → {b}")
    sec = lambda t: print(f"## {t}")
    sec("summary")
    for k in n["summary"]:
        row(k, o["summary"].get(k), n["summary"][k])
    sec("extras")
    for k in ("concentration", "review_top3_pct", "first_review_h", "lead_h", "app_unique"):
        row(k, eo.get(k), en.get(k))
    sec("repos (total/counted/unique/merge/backport)")
    f = lambda d: d and (d["total"], d["counted"], d["unique"], d["merge_rate_pct"], d["backport"])
    for r in n["repos"]:
        row(r, f(o["repos"].get(r)), f(n["repos"][r]))
    sec("devs (pr/unique/backport/merge/add/dele/add_dedup/del_dedup/repos) + types")
    f = lambda v: v and (v["pr"], v["unique"], v["backport"], v["merge_rate_pct"], v["add"], v["dele"],
                         v["add_dedup"], v["del_dedup"], len(v["repos"]))
    for d in sorted(set(o["devs"]) | set(n["devs"])):
        row(d, f(o["devs"].get(d)), f(n["devs"].get(d)))
        row(f"  {d} types", (o["devs"].get(d) or {}).get("types"), (n["devs"].get(d) or {}).get("types"))
    row("types", o["types"], n["types"])
    sec("per_repo_dev")
    for r in en["per_repo_dev"]:
        row(r, eo["per_repo_dev"].get(r), en["per_repo_dev"][r])
    sec("reviews (events/prs/approve/comment/changes)")
    f = lambda v: v and (v["events"], v["prs"], v["approve"], v["comment"], v["changes"])
    for d in sorted(set(o["reviews"]) | set(n["reviews"])):
        row(d, f(o["reviews"].get(d)), f(n["reviews"].get(d)))
    for k in ("no_review_by_repo", "bot_reviews"):
        sec(k)
        for r in sorted(set(o[k]) | set(n[k])):
            row(r, o[k].get(r), n[k].get(r))
    sec("refactor")
    f = lambda xs: [(r["repo"], r["number"], r["author"], r["add"], r["dele"]) for r in xs]
    row("refactor", f(o["refactor"]), f(n["refactor"]))
    for k in ("devs", "current", "repos", "monthly"):
        sec(f"compare {k}")
        for d in cn[k]:
            row(d, co[k].get(d), cn[k][d])
    raw = L(w, f"raw9-{m}.json")["prs"]
    print("## raw state", dict(Counter(p["state"] for p in raw)))
    for mm in sorted(f[8:15] for f in os.listdir(w) if f.startswith("metrics-") and f[8:15] != m):
        if os.path.exists(os.path.join(s, f"metrics-{mm}.json")) and L(s, f"metrics-{mm}.json")["summary"] != L(w, f"metrics-{mm}.json")["summary"]:
            print(f"⚠ {mm} summary가 바뀌었다 — 다른 달은 그대로여야 한다")


if __name__ == "__main__":
    cmd, w, m, tag = sys.argv[1:5]
    {"snapshot": snapshot, "diff": diff}[cmd](os.path.abspath(w), m, tag)
