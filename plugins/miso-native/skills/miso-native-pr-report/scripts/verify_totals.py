#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FE 챕터 PR 리포트 — 수치 교차검증. HTML을 만들기 전에 돌린다.

"다 됐다"는 검증이 아니다. 단정문을 돌려서 0건이 나와야 통과다.

쓰는 법:
  1) FACTS 블록을 그 달 백데이터 md 수치로 채운다
  2) python3 scripts/verify_totals.py
  3) 불일치 0건이 아니면 원인을 찾아 보고한다 (숫자를 맞추려고 서술을 고치지 않는다)
"""
import sys, math

# ══════════════════════════ FACTS ══════════════════════════
FACTS = dict(
    total_pr        = 599,   # 전체 PR
    counted         = 594,   # 집계 대상
    unique          = 546,   # 고유 작업
    backport        = 36,
    bots            = 12,
    human_pr        = 582,   # 사람 PR
    no_review       = 214,   # 사람 리뷰 0건으로 머지
    merge_rate_pct  = 91,
    refactor        = 21,
    top1            = 327,
)
# repo별 (repo, 집계대상, 고유작업, 머지율%)
REPOS = [("miso-native", 253, 218, 91), ("design-tokens", 213, 202, 97),
         ("miso-nexus", 89, 89, 84), ("salesforce", 12, 12, 75),
         ("partner-native", 12, 11, 83), ("strapi-client", 5, 5, 100),
         ("miso-rfq-admin", 5, 5, 60), ("partner-web", 3, 3, 67), ("backoffice", 2, 1, 50)]
# 개발자별 고유 작업
DEVS = {"개발자A": 327, "개발자B": 50, "개발자C": 43, "개발자D": 35, "개발자E": 28, "개발자F": 21,
        "개발자G": 14, "개발자H": 10, "개발자I": 6, "개발자J": 4, "개발자K": 3, "개발자L": 2,
        "개발자M": 1, "개발자N": 1, "개발자O": 1}
# 작업유형 5그룹: {대상: [값...]} — 행별 합이 그 사람 고유 작업과 같아야 한다
TYPE_ROWS = {}
TYPE_SCOPE = None   # 유형이 다른 기준이면 그 총합을 넣는다(repo별 분해 불가 시). 아니면 None
# 스택/막대 폭 검증용: {차트명: (값목록, 최대값)}
CHARTS = {}
# ══════════════════════════════════════════════════════════

fails, checks = [], 0
def ck(label, got, want, tol=0.0):
    global checks
    checks += 1
    if isinstance(got, bool):
        ok = got
    else:
        ok = abs(got - want) <= tol
    if not ok:
        fails.append((label, got, want))

F = FACTS
ck("고유 작업 = 집계대상 − 백포트 − 봇", F["counted"] - F["backport"] - F["bots"], F["unique"])
ck("사람 PR = 집계대상 − 봇", F["counted"] - F["bots"], F["human_pr"])
ck("전체 PR ≥ 집계대상", F["total_pr"] >= F["counted"], True)
ck("리뷰 0건 ≤ 사람 PR", F["no_review"] <= F["human_pr"], True)
ck("리뷰 0건 비율 0~100%", 0 <= F["no_review"] / F["human_pr"] * 100 <= 100, True)

ck("repo 집계대상 합", sum(r[1] for r in REPOS), F["counted"])
ck("repo 고유작업 합", sum(r[2] for r in REPOS), F["unique"])
merged = sum(r[1] * r[3] / 100 for r in REPOS)
ck("머지율 재계산", merged / sum(r[1] for r in REPOS) * 100, F["merge_rate_pct"], 0.6)

ck("개발자별 고유작업 합", sum(DEVS.values()), F["unique"])
ck("상위 1인 = DEVS 최대", max(DEVS.values()), F["top1"])
ck("Refactor ≤ 고유 작업", F["refactor"] <= F["unique"], True)

for name, vals in TYPE_ROWS.items():
    if name == "전체":
        ck("유형 전체 합", sum(vals), TYPE_SCOPE or F["unique"])
    else:
        ck(f"유형 행 합 — {name}", sum(vals), DEVS.get(name, sum(vals)))

for cname, (vals, mx) in CHARTS.items():
    ck(f"차트 최대값 — {cname}", max(vals) <= mx, True)

print(f"{checks}건 검증 · 불일치 {len(fails)}건")
for label, got, want in fails:
    print(f"  MISMATCH  {label}: got {got}, want {want}")
print()
print("── 수동 확인 (스크립트로 못 잡는 것) ──")
print("  □ 요약 서술의 주장이 상세 표와 일치하는가")
print("     (예: '나머지 전원 감소'라고 썼는데 표에 증가한 사람이 있는지)")
print("  □ 본문에 인용한 모든 비율을 원래 숫자로 되돌려 검산했는가")
print("  □ 재계산·정정·'X를 뺀 값' 같은 과정 서술이 남지 않았는가")
print("  □ 퇴사자의 부분월 데이터에 각주를 달았는가")
sys.exit(1 if fails else 0)
