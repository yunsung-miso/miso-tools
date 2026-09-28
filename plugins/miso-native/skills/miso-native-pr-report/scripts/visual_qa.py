#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FE 챕터 PR 리포트 — 시각 QA. 발행 전에 반드시 돌린다 (SKILL §8-2).

코드 리뷰만으로 HTML을 통과시키지 않는다. 레이아웃 붕괴는 코드에서 안 보이고 화면에서만 보인다.

  python3 scripts/visual_qa.py <파일.html> [<파일2.html> …]

검사 항목
  - 가로 스크롤 발생 여부 (본문은 절대 옆으로 밀리면 안 된다)
  - overflow 컨테이너 밖으로 넘치는 요소
  - 비정상적으로 높은 컨테이너 (4,000px 초과 = 그리드/플렉스 붕괴 신호)
  - 데스크톱(1180px)·좁은 화면(700px) 양쪽
  - 라이트·다크 양 모드 캡처 저장

위반은 폰트 축소로 때우지 않는다. 라벨 위치를 옮기거나 항목을 줄인다.
"""
import sys, pathlib

SKELETON = ("<!doctype html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<style>:root{color-scheme:light}body{margin:0;font:14px system-ui}"
            "img{max-width:100%}[hidden]{display:none!important}</style></head><body>")

AUDIT_JS = """() => {
  const bad=[];
  document.querySelectorAll('body *').forEach(e=>{
    if (e instanceof SVGElement) return;
    const cs=getComputedStyle(e);
    if (['auto','scroll','hidden'].includes(cs.overflowX) || cs.overflow==='hidden') return;
    if (e.scrollWidth > e.clientWidth+2 && e.clientWidth>0)
      bad.push(e.tagName+'.'+(typeof e.className==='string'?e.className:'')
               +' '+e.scrollWidth+'>'+e.clientWidth);
  });
  const tall=[];
  document.querySelectorAll('section, figure, ol, ul, table, .slide').forEach(e=>{
    const h=e.getBoundingClientRect().height;
    if (h > 4000) tall.push(e.tagName+'.'+(typeof e.className==='string'?e.className:'')
                            +' h='+Math.round(h));
  });
  return {bad:bad.slice(0,20), tall:tall.slice(0,10),
          w:document.documentElement.scrollWidth, cw:document.documentElement.clientWidth};
}"""


def main(files, outdir="/tmp/qa"):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright 없음 — pip install playwright --break-system-packages")
        print("시각 QA를 건너뛰었다고 사용자에게 알릴 것")
        return 2
    exe = "/opt/pw-browsers/chromium"
    pathlib.Path(outdir).mkdir(parents=True, exist_ok=True)
    fails = 0
    with sync_playwright() as p:
        b = p.chromium.launch(**({"executable_path": exe} if pathlib.Path(exe).exists() else {}))
        for f in files:
            src = pathlib.Path(f)
            tmp = pathlib.Path("/tmp/_qa.html")
            tmp.write_text(SKELETON + src.read_text() + "</body>")
            for w in (1180, 700):
                pg = b.new_page(viewport={"width": w, "height": 1000})
                pg.goto(tmp.as_uri()); pg.wait_for_timeout(1800)
                r = pg.evaluate(AUDIT_JS)
                hscroll = r["w"] > r["cw"] + 2
                bad_n = len(r["bad"]) + len(r["tall"]) + (1 if hscroll else 0)
                fails += bad_n
                print(f"{src.name} @{w}px  {'FAIL' if bad_n else 'PASS'}")
                if hscroll:
                    print(f"   가로 스크롤: {r['w']} > {r['cw']}")
                if r["bad"]:
                    print("   오버플로:", *r["bad"], sep="\n     ")
                if r["tall"]:
                    print("   과대 높이(레이아웃 붕괴 의심):", *r["tall"], sep="\n     ")
                pg.close()
            for mode in ("light", "dark"):
                pg = b.new_page(viewport={"width": 1180, "height": 1400}, color_scheme=mode)
                pg.goto(tmp.as_uri()); pg.wait_for_timeout(1800)
                pg.screenshot(path=f"{outdir}/{src.stem}-{mode}.png", full_page=True)
                pg.close()
            print(f"   캡처: {outdir}/{src.stem}-light.png · -dark.png  ← 한 장씩 눈으로 볼 것")
        b.close()
    print()
    print(f"{'통과' if not fails else f'위반 {fails}건 — 고친 뒤 다시 돌린다'}")
    return 1 if fails else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    sys.exit(main(sys.argv[1:]))
