# -*- coding: utf-8 -*-
"""FE 챕터 PR 리포트 — 차트 함수 라이브러리.

원칙: 데이터는 호출자가 상수로 넘긴다. 이 파일에는 리포트 수치를 넣지 않는다.
좌표·막대 폭·비율은 전부 여기서 계산한다 — 손으로 타이핑하면 반드시 틀린다.

모든 차트는 (1) 툴팁 (2) 표로 보기 토글을 함께 낸다.
색만으로 읽히는 값이 없어야 한다.
"""
import math

HUES = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)", "var(--s5)"]
# 밝은 hue 위의 라벨은 어두운 잉크로 — 흰 글씨는 대비가 안 나온다
LABEL_INK = ["#fff", "#fff", "#fff", "#3A2600", "#4A1729"]


# ────────────────────────── 표 / 표뷰 ──────────────────────────
def table(headers, rows, aligns=None):
    aligns = aligns or [""] * len(headers)
    h = "".join(f'<th class="{a}">{x}</th>' for x, a in zip(headers, aligns))
    body = "".join(
        "<tr>" + "".join(f'<td class="{a}">{c}</td>' for c, a in zip(r, aligns)) + "</tr>"
        for r in rows)
    return f'<div class="tw"><table><thead><tr>{h}</tr></thead><tbody>{body}</tbody></table></div>'


def tableview(headers, rows, aligns=None, label="표로 보기"):
    """색 인코딩의 WCAG 대체본. 모든 차트에 필수."""
    return f'<details class="tv"><summary>▸ {label}</summary>{table(headers, rows, aligns)}</details>'


def _fig(title, sub, body, tv=""):
    return (f'<figure><figcaption>{title}<span>{sub}</span></figcaption>{body}{tv}</figure>')


# ────────────────────── 1. 단일 계열 수평 막대 ──────────────────────
def hbar(rows, unit="", hue="var(--s1)", maxv=None):
    """rows: [(label, value, tip_suffix)]  — 한 계열은 한 색. 값에 따른 램프 금지."""
    mx = maxv or max(v for _, v, _ in rows)
    out = ['<div class="bars">']
    for label, val, tip in rows:
        out.append(
            f'<div class="row"><span class="rl">{label}</span>'
            f'<span class="track"><span class="fill" style="width:{val/mx*100:.1f}%;background:{hue}" '
            f'data-tip="{label} · {val:,}{unit}{tip}"></span>'
            f'<span class="val"><b>{val:,}{unit}</b></span></span></div>')
    return "".join(out) + '</div>'


def fig_hbar(title, sub, rows, tv_headers, tv_rows, tv_aligns, unit="", hue="var(--s1)", maxv=None):
    return _fig(title, sub, hbar(rows, unit, hue, maxv), tableview(tv_headers, tv_rows, tv_aligns))


# ─────────────── 2. 전월/당월 그룹 막대 (공통 축) ───────────────
def fig_compare(title, sub, rows, prev_label="전월", cur_label="당월", unit="건"):
    """rows: [(label, prev, cur)] — 공통 축으로 그린다. 이중 축 금지."""
    mx = max(max(a, b) for _, a, b in rows)
    out = ['<div class="bars">']
    for n, a, b in rows:
        out.append(
            f'<div class="row"><span class="rl">{n}</span><span class="pair">'
            f'<span class="track"><span class="fill mute" style="width:{a/mx*100:.1f}%" '
            f'data-tip="{n} · {prev_label} {a:,}{unit}"></span><span class="val">{a:,}</span></span>'
            f'<span class="track"><span class="fill" style="width:{b/mx*100:.1f}%" '
            f'data-tip="{n} · {cur_label} {b:,}{unit}"></span><span class="val"><b>{b:,}</b></span></span>'
            f'</span></div>')
    out.append('</div>')
    leg = (f'<div class="legend"><span><i style="background:var(--s-mute)"></i>{prev_label}</span>'
           f'<span><i style="background:var(--s1)"></i>{cur_label}</span>'
           f'<span>공통 축(최대 {mx:,})</span></div>')
    tv = [[n, f"{a:,}", f"{b:,}", f"{(b-a)/a*100:+.0f}%" if a else "—"] for n, a, b in rows]
    return _fig(title, sub, leg + "".join(out),
                tableview(["대상", prev_label, cur_label, "변화"], tv, ["", "n", "n", "n"]))


# ────────────────── 3. 100% 스택 (개발자별 프로필) ──────────────────
def fig_stack100(title, sub, cats, rows, unit="건"):
    """cats: [카테고리명]  rows: [(label, [값...])]  — 세그먼트 사이 2px 간격."""
    out = ['<div class="bars">']
    for name, vals in rows:
        tot = sum(vals)
        segs = []
        for i, (cname, v) in enumerate(zip(cats, vals)):
            if v == 0:
                continue
            pct = v / tot * 100
            lab = f'<em style="color:{LABEL_INK[i % len(LABEL_INK)]}">{v}</em>' if pct >= 11 else ''
            segs.append(f'<span class="seg" style="flex:0 1 {pct:.2f}%;background:{HUES[i % len(HUES)]}" '
                        f'data-tip="{name} · {cname} {v}{unit} ({pct:.0f}%)">{lab}</span>')
        out.append(f'<div class="stack-row"><span class="rl">{name}</span>'
                   f'<span class="stack">{"".join(segs)}</span>'
                   f'<span class="val">{tot:,}{unit}</span></div>')
    out.append('</div>')
    leg = '<div class="legend">' + "".join(
        f'<span><i style="background:{HUES[i % len(HUES)]}"></i>{c}</span>'
        for i, c in enumerate(cats)) + '</div>'
    tv = [[n] + [str(v) for v in vals] + [str(sum(vals))] for n, vals in rows]
    return _fig(title, sub, leg + "".join(out),
                tableview(["대상"] + list(cats) + ["합계"], tv, [""] + ["n"] * (len(cats) + 1)))


# ──────────── 4. 비율 지표 — 1.0 기준 로그 다이버징 ────────────
def fig_diverging_log(title, sub, rows, lo=-2.0, hi=4.5,
                      ticks=(0.25, 0.5, 1, 2, 4, 8, 16),
                      pos_label="순기여", neg_label="순수혜"):
    """rows: [(label, ratio, tip)] — 값의 폭이 크면 선형 막대로는 아래쪽이 안 보인다."""
    def gx(v): return (math.log2(v) - lo) / (hi - lo) * 100
    zero = gx(1.0)
    axis = "".join(f'<span style="left:{gx(t):.2f}%">{t}×</span>' for t in ticks)
    grid = "".join(f'<span class="dv-tick{" zero" if t == 1 else ""}" style="left:{gx(t):.2f}%"></span>'
                   for t in ticks)
    out = ['<div class="bars">']
    for n, v, tip in rows:
        x = gx(v)
        if v >= 1:
            left, width, hue, rad = zero, x - zero, HUES[0], "0 4px 4px 0"
        else:
            left, width, hue, rad = x, zero - x, HUES[1], "4px 0 0 4px"
        out.append(
            f'<div class="row"><span class="rl">{n}</span>'
            f'<span class="track"><span class="dv"><span class="dv-axis">{grid}</span>'
            f'<span class="dv-bar" style="left:{left:.2f}%;width:{max(width,0.4):.2f}%;'
            f'background:{hue};border-radius:{rad}" data-tip="{n} · {v}{tip}"></span>'
            f'</span></span></div>')
    out.append('</div>')
    out.append(f'<div class="axis">{axis}</div>')
    leg = (f'<div class="legend"><span><i style="background:{HUES[0]}"></i>{pos_label}</span>'
           f'<span><i style="background:{HUES[1]}"></i>{neg_label}</span>'
           f'<span>세로선 = 1.0 기준 · 가로축 로그(2배 간격)</span></div>')
    return _fig(title, sub, leg + "".join(out))


# ────── 5. 산점도 — 양축 로그 + 1:1 대각선 (사분면 대신) ──────
def fig_scatter_loglog(title, sub, pts, xt, yt, xlab, ylab, placements,
                       diag=True, pos_label="대각선 위", neg_label="대각선 아래"):
    """pts: [(label, x, y)]  placements: {label:(dx,dy,anchor)} — 라벨 충돌은 손으로 조정.

    중앙값 사분면은 상관관계만 보여주고 정작 볼 것이 사라진다.
    1:1 대각선을 기준선으로 쓰면 위/아래가 곧 의미다.
    """
    W, H, L, R, T, B = 780, 436, 64, 124, 22, 48
    xlo, xhi = math.log2(min(xt) * 0.7), math.log2(max(xt) * 1.7)
    ylo, yhi = math.log2(min(yt) * 0.6), math.log2(max(yt) * 1.35)
    X = lambda v: L + (W - L - R) * (math.log2(v) - xlo) / (xhi - xlo)
    Y = lambda v: T + (H - T - B) * (1 - (math.log2(v) - ylo) / (yhi - ylo))
    g = []
    for t in yt:
        g.append(f'<line class="c-grid" x1="{L}" y1="{Y(t):.1f}" x2="{W-R}" y2="{Y(t):.1f}"></line>')
        g.append(f'<text class="c-tick" x="{L-9}" y="{Y(t)+4:.1f}" text-anchor="end">{t}</text>')
    for t in xt:
        g.append(f'<line class="c-grid" x1="{X(t):.1f}" y1="{T}" x2="{X(t):.1f}" y2="{H-B}"></line>')
        g.append(f'<text class="c-tick" x="{X(t):.1f}" y="{H-B+18}" text-anchor="middle">{t}</text>')
    g.append(f'<line class="c-axis" x1="{L}" y1="{H-B}" x2="{W-R}" y2="{H-B}"></line>')
    g.append(f'<line class="c-axis" x1="{L}" y1="{T}" x2="{L}" y2="{H-B}"></line>')
    if diag:
        a, b = min(yt) * 0.6, max(yt) * 1.3
        g.append(f'<line x1="{X(a):.1f}" y1="{Y(a):.1f}" x2="{X(b):.1f}" y2="{Y(b):.1f}" '
                 f'stroke="var(--ink-faint)" stroke-width="1.5"></line>')
        g.append(f'<text class="c-lbl" x="{X(b)-4:.1f}" y="{Y(b)+16:.1f}" text-anchor="end">1 : 1</text>')
    for n, x, y in pts:
        cx, cy = X(x), Y(y)
        hue = HUES[0] if y >= x else HUES[1]
        g.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="6" fill="{hue}" '
                 f'stroke="var(--surface)" stroke-width="2"></circle>')
        g.append(f'<circle class="hit" cx="{cx:.1f}" cy="{cy:.1f}" r="16" '
                 f'data-tip="{n} · {xlab} {x:,} / {ylab} {y:,} · 비 {y/x:.1f}"></circle>')
        dx, dy, an = placements.get(n, (11, 5, "start"))
        g.append(f'<text class="c-lbl" x="{cx+dx:.1f}" y="{cy+dy:.1f}" text-anchor="{an}" '
                 f'style="fill:var(--ink-soft)">{n}</text>')
    g.append(f'<text class="c-tick" x="{W-R+8}" y="{H-B+18}">{xlab}</text>')
    g.append(f'<text class="c-tick" x="{L-9}" y="{T-6}" text-anchor="end">{ylab}</text>')
    aria = ". ".join(f"{n} {xlab} {x}, {ylab} {y}" for n, x, y in pts)
    svg = (f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="{title}. {aria}.">'
           + "".join(g) + '</svg>')
    leg = (f'<div class="legend"><span><i style="background:{HUES[0]}"></i>{pos_label}</span>'
           f'<span><i style="background:{HUES[1]}"></i>{neg_label}</span>'
           f'<span>양축 로그(2배 간격)</span></div>')
    tv = [[n, f"{x:,}", f"{y:,}", f"{y/x:.1f}"] for n, x, y in pts]
    return _fig(title, sub, leg + svg,
                tableview(["대상", xlab, ylab, "비"], tv, ["", "n", "n", "n"]))


# ────────── 6. 월별 추이 스몰 멀티플 (과거 월을 빼지 않는다) ──────────
def fig_trends(title, sub, panels):
    """panels: [{t, sub, u, x:[월], s:[{n, v:[값 또는 None]}], max}]

    패널마다 축이 다르므로 캡션에 '패널 사이 기울기 비교 금지'를 명시한다.
    직접 라벨은 끝점만 — 모든 점에 숫자를 붙이지 않는다.
    """
    def spark(tr):
        W, H, L, R, T, B = 330, 168, 46, 16, 16, 34
        xs = [L + (W - L - R) * i / (len(tr["x"]) - 1) for i in range(len(tr["x"]))]
        Y = lambda v: T + (H - T - B) * (1 - v / tr["max"])
        g, step = [], tr["max"] / 2
        for k in range(3):
            t = step * k
            g.append(f'<line class="c-grid" x1="{L}" y1="{Y(t):.1f}" x2="{W-R}" y2="{Y(t):.1f}"></line>')
            g.append(f'<text class="c-tick" x="{L-7}" y="{Y(t)+4:.1f}" text-anchor="end" '
                     f'style="font-size:10px">{int(t):,}</text>')
        g.append(f'<line class="c-axis" x1="{L}" y1="{Y(0):.1f}" x2="{W-R}" y2="{Y(0):.1f}"></line>')
        for si, ser in enumerate(tr["s"]):
            pts = [(x, v) for x, v in zip(xs, ser["v"]) if v is not None]
            ms = [m for m, v in zip(tr["x"], ser["v"]) if v is not None]
            g.append(f'<polyline points="{" ".join(f"{x:.1f},{Y(v):.1f}" for x, v in pts)}" '
                     f'fill="none" stroke="{HUES[si]}" stroke-width="2"></polyline>')
            for (x, v), m in zip(pts, ms):
                g.append(f'<circle cx="{x:.1f}" cy="{Y(v):.1f}" r="3.5" fill="{HUES[si]}" '
                         f'stroke="var(--surface)" stroke-width="1.5"></circle>')
                g.append(f'<circle class="hit" cx="{x:.1f}" cy="{Y(v):.1f}" r="14" '
                         f'data-tip="{m} · {ser["n"]} {v:,}{tr["u"]}"></circle>')
            lx, lv = pts[-1]
            dy = -10 if (len(tr["s"]) == 1 or si == 1) else 18   # 끝점 라벨 충돌 회피
            g.append(f'<text x="{lx-5:.1f}" y="{Y(lv)+dy:.1f}" text-anchor="end" '
                     f'style="fill:{HUES[si]};font-family:var(--mono);font-size:11.5px;'
                     f'font-weight:600">{lv:,}</text>')
        for x, m in zip(xs, tr["x"]):
            g.append(f'<text class="c-lbl" x="{x:.1f}" y="{H-12}" text-anchor="middle" '
                     f'style="font-size:10px">{m}</text>')
        aria = " · ".join(f'{s["n"]} ' + ", ".join(
            f"{m} {v}" for m, v in zip(tr["x"], s["v"]) if v is not None) for s in tr["s"])
        leg = ""
        if len(tr["s"]) > 1:
            leg = ('<div class="legend" style="font-size:10px;gap:4px 12px">' + "".join(
                f'<span><i style="background:{HUES[i]}"></i>{s["n"]}</span>'
                for i, s in enumerate(tr["s"])) + '</div>')
        return (f'<div><h4 style="margin:0 0 2px">{tr["t"]}</h4>'
                f'<p style="font-size:11.5px;color:var(--ink-faint);margin:0 0 6px">{tr["sub"]}</p>{leg}'
                f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" '
                f'aria-label="{tr["t"]} 추이. {aria}.">' + "".join(g) + '</svg></div>')

    months = []
    for tr in panels:
        for m in tr["x"]:
            if m not in months:
                months.append(m)
    rows = []
    for tr in panels:
        for s in tr["s"]:
            nm = tr["t"] if len(tr["s"]) == 1 else f'{tr["t"]} — {s["n"]}'
            cells = dict(zip(tr["x"], s["v"]))
            rows.append([nm] + [("—" if cells.get(m) is None else f'{cells[m]:,}') for m in months])
    return _fig(title, sub,
                f'<div class="cols grid-2" style="gap:22px 26px">{"".join(spark(t) for t in panels)}</div>',
                tableview(["지표"] + months, rows, [""] + ["n"] * len(months), "추이 표로 보기"))


# ─────────── 7. 다중 패널 단일 막대 (리뷰 외 기여 등) ───────────
def fig_panels(title, sub, panels):
    """panels: [(패널제목, [(라벨, 값)], unit, hue)] — 축이 패널마다 다름을 반드시 명시."""
    out = []
    for ptitle, rows, unit, hue in panels:
        mx = max(v for _, v in rows)
        bars = "".join(
            f'<div class="row"><span class="rl">{n}</span>'
            f'<span class="track"><span class="fill" style="width:{v/mx*100:.1f}%;background:{hue}" '
            f'data-tip="{n} · {v:,}{unit}"></span><span class="val"><b>{v:,}</b></span></span></div>'
            for n, v in rows)
        out.append(f'<div><h4>{ptitle}</h4><div class="bars">{bars}</div></div>')
    tv = "".join(
        tableview([ptitle, "값", "비중"],
                  [[n, f"{v:,}", f"{v/sum(x for _, x in rows)*100:.0f}%"] for n, v in rows],
                  ["", "n", "n"], f"{ptitle} 표로 보기")
        for ptitle, rows, unit, hue in panels)
    return _fig(title, sub, f'<div class="cols">{"".join(out)}</div>', tv)
