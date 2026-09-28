#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""기능 단위 리드타임(첫 커밋 → 사용자 반영)과 테스트 동반률.

  python3 delivery.py 2026-01 2026-02 ... 2026-09

입력: raw9-YYYY-MM.json(analyze.py 산출) · extra-YYYY-MM.json(fetch_extra.py 산출)
출력: delivery.json

정의 (2026-09 리포트에서 고정)
- 기능 단위 = 티켓. 같은 티켓의 원본·스택·롤백·백포트 PR을 하나로 묶는다. 티켓이 없으면 PR 1건이 단위.
  담당자 = 가장 먼저 만든 원작업(백포트 아님) PR의 작성자. 유형도 그 PR 기준.
- 시작 = 묶인 PR 전체 커밋 중 가장 이른 작성 시각(authoredDate)
- 반영 = 묶인 PR 중 가장 먼저 사용자에게 나간 시각
    miso-native · partner-native: 머지 커밋을 처음 담은 스토어·OTA 태그 시각 (codepush/ base는 머지 시각)
    웹·기타: main/master 머지 시각
    배포 브랜치가 아닌 base(에픽·스택)는 그 base를 head로 가진 PR의 반영 시각을 따른다
- 변경 실패 = 첫 머지(또는 반영 중 이른 시점) 후 14일 안에 같은 티켓으로 (a) 제목에 롤백·revert·hotfix가 있는 PR 또는
  (b) 앱 긴급 수정 경로(bundle/·codepush/)로 들어간 Bugfix·Fix가 온 경우. 복구 시간 = 반영 → 그 수정의 반영
- 테스트 동반 = 원작업 PR 중 하나라도 테스트 파일을 바꿨는가. 단위(jest·Apex Test)와 e2e(maestro·playwright)를 나눈다
- 월 귀속 = 반영된 달. 아직 반영 전이면 '미반영'으로 첫 PR 생성 달에 센다
"""
import json, os, re, subprocess, sys, statistics, datetime as dt
from collections import defaultdict

H = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(H)
sys.path.insert(0, os.path.join(os.environ.get("CLAUDE_SKILL_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "scripts"))
import aggregate as A  # noqa: E402

names = json.load(open(os.path.join(ROOT, "names.json")))
disp = lambda l: names.get(l, l)
REPO_GIT = {
    "getmiso/miso-native": (os.environ.get("NATIVE_GIT") or os.path.join(ROOT, "_git", "miso-native"), r"^(v6\.|ota/)"),
    "getmiso/partner-native": (os.environ.get("PNATIVE_GIT") or os.path.join(ROOT, "_git", "partner-native"), r"^v4\.2"),
}
TICKET = re.compile(r"\b([A-Z][A-Z0-9]{1,9}-\d+)\b")
E2E = re.compile(r"(^|/)(\.maestro|e2e|e2e-mock|playwright)/|\.e2e\.[jt]sx?$", re.I)
UNIT = re.compile(r"(__tests__/|\.(test|spec)\.[jt]sx?$|Test\.cls$|(^|/)tests?/)", re.I)
DEPLOY_BRANCH = {"main", "master"}
FIX_TITLE = re.compile(r"롤백|되돌|revert|rollback|hotfix|핫픽스", re.I)


def ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def git(path, *args):
    return subprocess.run(["git", "-C", path, *args], capture_output=True, text=True, check=True).stdout


def tag_map(path, pattern):
    """커밋 → 그 커밋을 처음 담은 태그의 생성 시각."""
    if not path or not os.path.isdir(path):
        return {}
    rx = re.compile(pattern)
    rows = git(path, "for-each-ref", "--sort=creatordate",
               "--format=%(refname:short)\t%(creatordate:iso-strict)", "refs/tags").splitlines()
    first = {}
    for row in rows:
        name, when = row.split("\t")
        if not rx.search(name) or when < "2025-10":
            continue
        t = ts(when)
        for sha in git(path, "rev-list", name, "--since=2025-10-01").split():
            first.setdefault(sha, t)
    return first


def main():
    months = sys.argv[1:]
    prs, extra = [], {}
    for m in months:
        prs += json.load(open(os.path.join(H, f"raw9-{m}.json")))["prs"]
        extra.update(json.load(open(os.path.join(H, f"extra-{m}.json"))))
    tags = {r: tag_map(p, pat) for r, (p, pat) in REPO_GIT.items()}
    by_head = defaultdict(list)
    for p in prs:
        p["_x"] = extra.get(f"{p['repo']}#{p['number']}", {})
        by_head[(p["repo"], p.get("headRefName"))].append(p)

    def deployed_at(p, depth=0):
        if not p.get("mergedAt") or depth > 4:
            return None
        repo, base, merged = p["repo"], p.get("baseRefName") or "", ts(p["mergedAt"])
        if repo in REPO_GIT and REPO_GIT[repo][0]:
            if base.startswith("codepush/"):
                return merged
            t = tags[repo].get(p["_x"].get("merge_sha"))
            if t:
                return max(t, merged)
        elif base in DEPLOY_BRANCH:
            return merged
        parents = [q for q in by_head.get((repo, base), []) if q.get("mergedAt")]
        cands = [deployed_at(q, depth + 1) for q in parents]
        cands = [c for c in cands if c]
        return max(min(cands), merged) if cands else None

    def reviewed(p, depth=0):
        """(사람 리뷰 있음, CR 있음). 에픽·스택 base면 에픽 PR의 리뷰를 물려받는다."""
        hr = cr = False
        for r in p.get("reviews") or []:
            rl = (r.get("author") or {}).get("login")
            if rl and rl != p["author"]["login"] and not A.is_bot(rl):
                hr = True
                cr = cr or (r.get("state") or "").upper() == "CHANGES_REQUESTED"
        base = p.get("baseRefName") or ""
        if not hr and depth < 4 and base not in DEPLOY_BRANCH and not re.match(r"^(release|bundle|codepush)/", base):
            for q in by_head.get((p["repo"], base), []):
                h2, c2 = reviewed(q, depth + 1)
                hr, cr = hr or h2, cr or c2
        return hr, cr

    units = defaultdict(list)
    for p in prs:
        title = p.get("title") or ""
        if A.is_merge_pr(p) or A.is_bot(p["author"]["login"]):
            continue
        m = TICKET.search(title)
        units[m.group(1) if m else f"{p['repo']}#{p['number']}"].append(p)

    out = []
    for key, g in units.items():
        orig = sorted([p for p in g if not A.BACKPORT_PAT.search(p["title"])], key=lambda p: p["createdAt"])
        if not orig:
            continue
        lead = orig[0]
        files = [f.get("path") or "" for p in orig for f in p.get("files") or []]
        e2e = any(E2E.search(f) for f in files)
        unit = any(UNIT.search(f) and not E2E.search(f) for f in files)
        starts = [ts(p["_x"].get("first_commit_at")) for p in g if p["_x"].get("first_commit_at")]
        start = min(starts) if starts else ts(lead["createdAt"])
        merges = [ts(p["mergedAt"]) for p in orig if p.get("mergedAt")]
        deps = [d for d in (deployed_at(p) for p in g) if d]
        dep = min(deps) if deps else None
        first_merge = min(merges) if merges else None
        # DORA 변경 실패율·복구 시간: 반영 후 14일 안에 같은 티켓으로 롤백·Fix·Bugfix PR이 오면 실패
        failed, restore = False, None
        t0 = min(x for x in (dep, first_merge) if x) if (dep or first_merge) else None
        if t0 and not key.count("#"):
            fixes = [p for p in g if ts(p["createdAt"]) > t0
                     and ts(p["createdAt"]) - t0 <= dt.timedelta(days=14)
                     and (FIX_TITLE.search(p["title"])
                          or (A.work_type(p["title"]) in ("Bugfix", "Fix")
                              and re.match(r"^(bundle|codepush)/", p.get("baseRefName") or "")))]
            if fixes:
                failed = True
                fdeps = [d for d in (deployed_at(p) for p in fixes) if d]
                if fdeps:
                    restore = round((min(fdeps) - t0).total_seconds() / 86400, 2)
        human_rev = any(reviewed(p)[0] for p in orig)
        cr = any(reviewed(p)[1] for p in orig)
        out.append(dict(
            key=key, owner=disp(lead["author"]["login"]), type=A.work_type(lead["title"]),
            repos=sorted({p["repo"].split("/")[1] for p in g}), prs=len(g), orig_prs=len(orig),
            title=lead["title"], start=start.isoformat() if start else None,
            first_merge=first_merge.isoformat() if first_merge else None,
            deployed=dep.isoformat() if dep else None,
            month=(dep or ts(lead["createdAt"])).strftime("%Y-%m"), shipped=bool(dep),
            created_month=ts(lead["createdAt"]).strftime("%Y-%m"),
            lead_days=round((dep - start).total_seconds() / 86400, 2) if dep and start else None,
            dev_days=round((first_merge - start).total_seconds() / 86400, 2) if first_merge and start else None,
            wait_days=round((dep - first_merge).total_seconds() / 86400, 2) if dep and first_merge else None,
            test=unit or e2e, unit_test=unit, e2e_test=e2e,
            human_review=human_rev, changes_requested=cr, failed=failed, restore_days=restore))
    json.dump(out, open(os.path.join(H, "delivery.json"), "w"), ensure_ascii=False, indent=1)

    def med(xs):
        return round(statistics.median(xs), 1) if xs else None
    print(f"기능 단위 {len(out)} · 반영 {sum(u['shipped'] for u in out)} · 태그 맵 "
          + ", ".join(f"{k.split('/')[1]} {len(v)}" for k, v in tags.items()), file=sys.stderr)
    for m in months:
        f = [u for u in out if u["month"] == m and u["type"] == "Feature" and u["shipped"]]
        print(f"  {m} Feature 반영 {len(f)} · 리드 중앙 {med([u['lead_days'] for u in f])}일 · "
              f"테스트 동반 {sum(u['test'] for u in f)}/{len(f)}", file=sys.stderr)


if __name__ == "__main__":
    main()
