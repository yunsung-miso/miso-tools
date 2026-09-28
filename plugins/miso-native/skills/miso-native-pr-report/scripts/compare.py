#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 도입(2026-05) 전후 비교 + DORA. delivery.json · metrics-*.json · raw9-*.json만 읽는다.

  python3 compare.py > compare.md   (JSON은 compare.json)

기간·기준 규칙 (2026-09 리포트에서 고정)
- 도입 전 1~4월, 도입 후 6~9월. 5월은 도입 달이라 뺀다
- miso-native는 1~3월이 재구축기(첫 스토어 태그 4/1)라 native 도입 전 = 4월만
- 기능은 시작한 달(첫 PR 생성월) 기준으로 기간에 넣는다
- 개인 전후 비교는 같은 repo 기준: 그 사람이 두 기간 모두 작업한 repo만 쓴다(기준 repo 열로 표기)
- 도입 전 기준이 없는 repo(nexus 4/27 · design-tokens 6월 시작)는 6~9월 현황 표에만 둔다
- 9월은 26일치라 월평균 분모에 26/30을 쓴다
"""
import json, os, statistics, sys
from collections import defaultdict
sys.path.insert(0, os.path.join(os.environ.get("CLAUDE_SKILL_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "scripts"))
import aggregate as A  # noqa: E402

H = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(H)
names = json.load(open(os.path.join(ROOT, "names.json")))
roster = json.load(open(os.path.join(ROOT, "roster.json")))
disp = lambda l: names.get(l, l)
APP = [disp(x) for x in roster["app_chapter"]]
EXEMPT = {r.split("/")[1] for r in roster.get("review_exempt_repos", {})}
BEFORE, AFTER = ["2026-01", "2026-02", "2026-03", "2026-04"], ["2026-06", "2026-07", "2026-08", "2026-09"]
NATIVE = "miso-native"
MW = {m: (26 / 30 if m == "2026-09" else 1.0) for m in BEFORE + AFTER}
U = json.load(open(os.path.join(H, "delivery.json")))

med = lambda xs: round(statistics.median(xs), 1) if xs else None
pct = lambda a, b: round(a / b * 100) if b else None


def period_months(repo, period):
    if period == "before":
        return ["2026-04"] if repo == NATIVE else BEFORE
    return AFTER


def weight(repo, period):
    return sum(MW[m] for m in period_months(repo, period))


# 개인·repo별 고유 작업(백포트·봇 제외) — raw9에서 repo 단위로 다시 센다
uniq = defaultdict(lambda: defaultdict(int))   # (dev, repo) -> {month: n}
for m in BEFORE + AFTER:
    for p in json.load(open(os.path.join(H, f"raw9-{m}.json")))["prs"]:
        t = p.get("title") or ""
        if A.is_merge_pr(p) or A.is_bot(p["author"]["login"]) or A.BACKPORT_PAT.search(t):
            continue
        uniq[(disp(p["author"]["login"]), p["repo"].split("/")[1])][m] += 1


def rate(dev, repo, period):
    return sum(uniq[(dev, repo)].get(m, 0) for m in period_months(repo, period)) / weight(repo, period)


def base_repos(dev):
    repos = {r for (d, r) in uniq if d == dev}
    return sorted(r for r in repos if rate(dev, r, "before") > 0 and rate(dev, r, "after") > 0)


def feature_units(dev, repos, period):
    return [u for u in U if u["owner"] == dev and u["type"] == "Feature" and u["repos"][0] in repos
            and u["created_month"] in period_months(u["repos"][0], period)]


def delivery_stats(us, period):
    shipped = [u for u in us if u["shipped"]]
    failed = [u for u in shipped if u["failed"]]
    return dict(shipped=len(shipped),
                deploy_pm=round(sum(1 / weight(u["repos"][0], period) for u in shipped), 1),
                dev=med([u["dev_days"] for u in shipped if u["dev_days"] is not None]),
                lead=med([u["lead_days"] for u in shipped if u["lead_days"] is not None]),
                wait=med([u["wait_days"] for u in shipped if u["wait_days"] is not None]),
                failed=len(failed), cfr=pct(len(failed), len(shipped)),
                mttr=med([u["restore_days"] for u in failed if u["restore_days"] is not None]),
                test=pct(sum(u["test"] for u in shipped), len(shipped)),
                no_rev_no_test=sum(1 for u in shipped if not u["human_review"] and not u["test"]
                                   and not EXEMPT.intersection(u["repos"])))


out = dict(devs={}, current={}, repos={}, monthly={})
for d in APP:
    base = base_repos(d)
    row = dict(base=base)
    for p in ("before", "after"):
        row[p] = dict(uniq_pm=round(sum(rate(d, r, p) for r in base), 1),
                      **delivery_stats(feature_units(d, base, p), p))
    out["devs"][d] = row
# 6~9월 현황 (모든 repo, 전후 비교 없음)
for d in APP:
    repos = sorted({r for (dd, r) in uniq if dd == d and rate(d, r, "after") > 0})
    us = feature_units(d, repos, "after")
    out["current"][d] = dict(repos=repos, uniq_pm=round(sum(rate(d, r, "after") for r in repos), 1),
                             **delivery_stats(us, "after"))
for r in [NATIVE, "partner-native", "strapi-client", "salesforce", "miso-nexus", "design-tokens"]:
    out["repos"][r] = {p: delivery_stats([u for u in U if u["type"] == "Feature" and u["repos"][0] == r
                                          and u["created_month"] in period_months(r, p)], p)
                       for p in ("before", "after")}
for m in BEFORE + ["2026-05"] + AFTER:
    us = [u for u in U if u["type"] == "Feature" and u["created_month"] == m
          and u["repos"][0] not in ("design-tokens", "miso-nexus") and not (u["repos"][0] == NATIVE and m < "2026-04")]
    s = delivery_stats(us, "after")
    out["monthly"][m] = {k: s[k] for k in ("shipped", "dev", "lead", "cfr", "mttr", "test", "failed")}
json.dump(out, open(os.path.join(H, "compare.json"), "w"), ensure_ascii=False, indent=1)

f = lambda v: "–" if v is None else v
print("## 개인 전후 (같은 repo 기준, Feature)\n| 개발자 | 기준 repo | 고유/월 전→후 | 반영/월 전→후 | 개발 구간(일) 전→후 | 실패 전→후 | 테스트 전→후 |\n|---|---|---|---|---|---|---|")
for d, v in out["devs"].items():
    if not v["base"]:
        print(f"| {d} | – | 도입 후 합류 또는 도입 전 작업 없음 | | | | |"); continue
    a, b = v["before"], v["after"]
    print(f"| {d} | {' · '.join(v['base'])} | {a['uniq_pm']} → {b['uniq_pm']} | {a['deploy_pm']} → {b['deploy_pm']} | "
          f"{f(a['dev'])} → {f(b['dev'])} | {a['failed']}/{a['shipped']} → {b['failed']}/{b['shipped']} | {f(a['test'])}% → {f(b['test'])}% |")
print("\n## 6~9월 현황 (전 repo)\n| 개발자 | repo | 고유/월 | 반영/월 | 개발 구간 | 실패 | 테스트 | 리뷰·테스트 없이 반영 |\n|---|---|---:|---:|---:|---:|---:|---:|")
for d, v in out["current"].items():
    print(f"| {d} | {' · '.join(v['repos'])} | {v['uniq_pm']} | {v['deploy_pm']} | {f(v['dev'])} | {v['failed']}/{v['shipped']} | {f(v['test'])}% | {v['no_rev_no_test']} |")
print("\n## repo별 DORA\n| repo | 반영/월 전→후 | 리드 전→후 | 대기 전→후 | 실패 전→후 | 복구 후 | 테스트 전→후 |\n|---|---|---|---|---|---|---|")
for r, v in out["repos"].items():
    a, b = v["before"], v["after"]
    print(f"| {r} | {a['deploy_pm']} → {b['deploy_pm']} | {f(a['lead'])} → {f(b['lead'])} | {f(a['wait'])} → {f(b['wait'])} | "
          f"{a['failed']}/{a['shipped']} → {b['failed']}/{b['shipped']} | {f(b['mttr'])} | {f(a['test'])}% → {f(b['test'])}% |")
print("\n## 월별 (시작월, nexus·design-tokens·재구축기 native 제외)\n| 월 | 반영 | 개발 구간 | 리드 | 실패 | 테스트 |\n|---|---:|---:|---:|---:|---:|")
for m, v in out["monthly"].items():
    print(f"| {m} | {v['shipped']} | {f(v['dev'])} | {f(v['lead'])} | {v['failed']} | {f(v['test'])}% |")
