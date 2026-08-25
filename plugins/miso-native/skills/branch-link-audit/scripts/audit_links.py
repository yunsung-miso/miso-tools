#!/usr/bin/env python3
"""Branch.io 딥링크 전수 조사.

입력: Branch 대시보드에서 export한 CSV(또는 한 줄당 URL 하나인 txt).
각 링크를 GET /v1/url 로 조회해 설정값을 수집한다.

출력(out 디렉토리):
  raw.jsonl   — 링크별 API 응답 원문
  report.csv  — 주요 필드 표 (campaign/channel/feature/fallback/딥링크 데이터)

사용:
  python3 audit_links.py links.csv --branch-key key_live_xxx --out out/
"""

import argparse
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api2.branch.io/v1/url"

URL_RE = re.compile(
    r"https?://(?:get\.miso\.kr|get-staging\.miso\.kr|partner-staging\.miso\.kr"
    r"|[a-z0-9-]*\.?app\.link)/(?:e/)?[A-Za-z0-9]+"
)

REPORT_FIELDS = [
    "url",
    "$link_title",
    "~link_type",
    "campaign",
    "channel",
    "feature",
    "destination",
    "serviceCode",
    "isNavigate",
    "$desktop_url",
    "$ios_url",
    "$android_url",
    "$fallback_url",
    "$web_only",
    "$deeplink_path",
    "custom_data",
    "error",
]


def extract_urls(path, column=None, regex=False):
    if regex:
        with open(path, encoding="utf-8-sig") as f:
            text = f.read()
        seen, out = set(), []
        for u in URL_RE.findall(text):
            if u not in seen:
                seen.add(u)
                out.append(u)
        return out
    if not path.endswith(".csv"):
        with open(path, encoding="utf-8-sig") as f:
            return [line.strip() for line in f if line.strip().startswith("http")]
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return []
    if column is None:
        candidates = [
            h for h in rows[0]
            if h and ("link" in h.lower() or "url" in h.lower())
        ]
        for h in candidates:
            if str(rows[0].get(h, "")).startswith("http"):
                column = h
                break
    if column is None:
        sys.exit(f"URL 컬럼을 못 찾음. --column 으로 지정. 헤더: {list(rows[0])}")
    return [r[column].strip() for r in rows if r.get(column, "").startswith("http")]


def fetch(url, branch_key):
    qs = urllib.parse.urlencode({"url": url, "branch_key": branch_key})
    req = urllib.request.Request(f"{API}?{qs}")
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            return json.load(res), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.read().decode(errors='replace')[:200]}"
    except Exception as e:
        return None, str(e)


def to_row(url, body, error):
    row = {k: "" for k in REPORT_FIELDS}
    row["url"] = url
    if error:
        row["error"] = error
        return row
    data = body.get("data", {}) or {}
    for k in ("campaign", "channel", "feature"):
        if k in row:
            row[k] = body.get(k, "")
    custom = {}
    for k, v in data.items():
        if k in row:
            row[k] = v
        elif not k.startswith(("$", "~", "+")):
            custom[k] = v
    row["custom_data"] = json.dumps(custom, ensure_ascii=False) if custom else ""
    return row


def main():
    p = argparse.ArgumentParser()
    p.add_argument("input", help="대시보드 export CSV 또는 URL 목록 txt")
    p.add_argument("--branch-key")
    p.add_argument("--column", help="CSV의 URL 컬럼명 (자동탐지 실패 시)")
    p.add_argument("--regex", action="store_true",
                   help="파일 전체에서 정규식으로 Branch URL 추출 (시트 덤프 등)")
    p.add_argument("--extract-only", action="store_true",
                   help="조회 없이 추출된 URL만 출력")
    p.add_argument("--out", default="branch-audit-out")
    args = p.parse_args()

    urls = extract_urls(args.input, args.column, args.regex)
    if args.extract_only:
        for u in urls:
            print(u)
        print(f"\n총 {len(urls)}개 unique URL", file=sys.stderr)
        return
    if not urls:
        sys.exit("입력에서 URL을 못 찾음")
    if not args.branch_key:
        sys.exit("조회에는 --branch-key 필요")
    print(f"{len(urls)}개 링크 조회 시작", file=sys.stderr)

    import os
    os.makedirs(args.out, exist_ok=True)
    ok = err = 0
    with open(f"{args.out}/raw.jsonl", "w", encoding="utf-8") as raw, \
         open(f"{args.out}/report.csv", "w", newline="", encoding="utf-8") as rep:
        w = csv.DictWriter(rep, fieldnames=REPORT_FIELDS)
        w.writeheader()
        for i, url in enumerate(urls, 1):
            body, error = fetch(url, args.branch_key)
            raw.write(json.dumps({"url": url, "response": body, "error": error},
                                 ensure_ascii=False) + "\n")
            w.writerow(to_row(url, body, error))
            ok += error is None
            err += error is not None
            if i % 20 == 0:
                print(f"  {i}/{len(urls)}", file=sys.stderr)
            time.sleep(0.05)
    print(f"완료: 성공 {ok} / 실패 {err} → {args.out}/report.csv", file=sys.stderr)


if __name__ == "__main__":
    main()
