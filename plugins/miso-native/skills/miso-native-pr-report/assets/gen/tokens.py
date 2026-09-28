# -*- coding: utf-8 -*-
"""FE 챕터 PR 리포트 — 디자인 토큰 + CSS.

라이트/다크 3-상태(시스템·명시 라이트·명시 다크)를 모두 커버한다.
series 슬롯은 dataviz 스킬의 검증 통과 팔레트다 —
바꾸려면 scripts/validate_palette.js 를 라이트·다크 양쪽으로 다시 돌릴 것.
"""

HEAD = r'''<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Gothic+A1:wght@500;700;800&family=IBM+Plex+Sans+KR:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
  :root {
    --ground:#EFF2F6; --surface:#FFFFFF; --surface-sunk:#E4E9F0;
    --ink:#121821; --ink-soft:#4E5C6E; --ink-faint:#7C8898;
    --rule:#D3DAE4; --rule-soft:#E4E9F0; --grid:#DFE5EC;
    --accent:#16324F; --accent-live:#2C6FA6;
    --good:#1A7F4B; --warn:#A85B08; --bad:#AE2A1B;
    --good-wash:#E2F1E8; --warn-wash:#F7EBDC; --bad-wash:#F7E4E1;
    /* dataviz 검증 통과 — light (surface #FFFFFF) */
    --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --s4:#eda100; --s5:#e87ba4;
    --s-mute:#C3CCD8;
    --shadow:0 1px 2px rgba(18,24,33,.06), 0 8px 24px -12px rgba(18,24,33,.18);
    --display:"Gothic A1","IBM Plex Sans KR",system-ui,sans-serif;
    --body:"IBM Plex Sans KR","Gothic A1",system-ui,sans-serif;
    --mono:"IBM Plex Mono","SFMono-Regular",ui-monospace,monospace;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --ground:#0E1319; --surface:#161D26; --surface-sunk:#1E2731;
      --ink:#E7ECF2; --ink-soft:#A3AFBE; --ink-faint:#7B8798;
      --rule:#2A3440; --rule-soft:#212A34; --grid:#28313D;
      --accent:#9EC4E4; --accent-live:#6FA8D6;
      --good:#56C68C; --warn:#DE9A3D; --bad:#EE8377;
      --good-wash:#14261D; --warn-wash:#2A2013; --bad-wash:#2C1A18;
      --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500; --s5:#d55181;
      --s-mute:#3A4655;
      --shadow:0 1px 2px rgba(0,0,0,.4), 0 10px 30px -14px rgba(0,0,0,.6);
    }
  }
  :root[data-theme="dark"] {
    --ground:#0E1319; --surface:#161D26; --surface-sunk:#1E2731;
    --ink:#E7ECF2; --ink-soft:#A3AFBE; --ink-faint:#7B8798;
    --rule:#2A3440; --rule-soft:#212A34; --grid:#28313D;
    --accent:#9EC4E4; --accent-live:#6FA8D6;
    --good:#56C68C; --warn:#DE9A3D; --bad:#EE8377;
    --good-wash:#14261D; --warn-wash:#2A2013; --bad-wash:#2C1A18;
    --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500; --s5:#d55181;
    --s-mute:#3A4655;
    --shadow:0 1px 2px rgba(0,0,0,.4), 0 10px 30px -14px rgba(0,0,0,.6);
  }

  *{box-sizing:border-box}
  body{margin:0;background:var(--ground);color:var(--ink);font-family:var(--body);
       font-size:15px;line-height:1.6;-webkit-font-smoothing:antialiased;
       word-break:keep-all;overflow-wrap:break-word}

  /* ── 문서 레이아웃 ── */
  .doc{max-width:1060px;margin:0 auto;padding:0 20px 96px}
  .rpt-head{padding:52px 0 26px;border-bottom:2px solid var(--ink)}
  .rpt-head h1{font-family:var(--display);font-weight:800;font-size:clamp(28px,4.6vw,46px);
       line-height:1.12;letter-spacing:-.035em;margin:0 0 10px;text-wrap:balance}
  .rpt-head .period{font-family:var(--mono);font-size:12.5px;color:var(--ink-faint);
       letter-spacing:.04em;display:flex;flex-wrap:wrap;gap:6px 24px}
  .rpt-head .period b{color:var(--ink-soft);font-weight:500}
  .toc{position:sticky;top:0;z-index:30;background:var(--surface);border-bottom:1px solid var(--rule);
       padding:10px 0;margin-bottom:34px;display:flex;flex-wrap:wrap;gap:4px 6px}
  .toc a{font-family:var(--mono);font-size:11.5px;color:var(--ink-soft);text-decoration:none;
       padding:4px 9px;border:1px solid var(--rule);border-radius:2px;white-space:nowrap}
  .toc a:hover{background:var(--surface-sunk);color:var(--ink);border-color:var(--ink-faint)}
  .toc a:focus-visible{outline:2px solid var(--accent-live);outline-offset:1px}
  section.part{padding:38px 0;border-top:1px solid var(--rule-soft);display:flex;
       flex-direction:column;gap:22px;scroll-margin-top:60px}
  section.part:first-of-type{border-top:0}
  .part-eyebrow{font-family:var(--mono);font-size:11px;font-weight:600;letter-spacing:.16em;
       text-transform:uppercase;color:var(--accent-live)}
  .part h2{font-family:var(--display);font-weight:800;font-size:clamp(21px,2.7vw,29px);
       line-height:1.25;letter-spacing:-.022em;margin:0;text-wrap:balance}
  .part h3{font-family:var(--display);font-weight:700;font-size:16px;color:var(--ink);margin:14px 0 0}
  .part h4{font-family:var(--mono);font-size:11px;font-weight:600;letter-spacing:.12em;
       text-transform:uppercase;color:var(--ink-faint);margin:8px 0 0}

  /* ── 슬라이드 레이아웃 (어젠다 덱) ── */
  .deck{display:flex;flex-direction:column;gap:20px;padding:20px 20px 96px;max-width:1180px;margin:0 auto}
  .slide{background:var(--surface);border:1px solid var(--rule);border-radius:3px;
       box-shadow:var(--shadow);padding:34px 38px 26px;display:flex;flex-direction:column;
       gap:18px;scroll-margin-top:16px}
  .slide-head{display:flex;align-items:baseline;justify-content:space-between;gap:16px;
       border-bottom:1px solid var(--rule-soft);padding-bottom:10px}
  .eyebrow{font-family:var(--mono);font-size:11px;font-weight:600;letter-spacing:.16em;
       text-transform:uppercase;color:var(--accent-live)}
  .timebox{font-family:var(--mono);font-size:11px;letter-spacing:.08em;color:var(--ink-faint);white-space:nowrap}
  .slide h2{font-family:var(--display);font-weight:800;font-size:clamp(22px,3vw,31px);
       line-height:1.25;letter-spacing:-.02em;margin:0;text-wrap:balance}
  .slide-foot{margin-top:auto;padding-top:12px;border-top:1px solid var(--rule-soft);
       font-family:var(--mono);font-size:11px;color:var(--ink-faint);letter-spacing:.06em;
       display:flex;justify-content:space-between;gap:12px}

  /* ── 공통 ── */
  .lede{margin:0;max-width:68ch;font-size:15.5px;color:var(--ink-soft)}
  .lede strong{color:var(--ink);font-weight:600}
  p{margin:0}
  .cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:22px;align-items:start}
  @media (min-width:700px){.grid-2{grid-template-columns:repeat(2,minmax(0,1fr)) !important}}
  ul.plain{margin:0;padding-left:18px;display:flex;flex-direction:column;gap:6px;
       font-size:13.5px;color:var(--ink-soft)}
  ul.plain strong{color:var(--ink);font-weight:600}
  .note{font-size:13px;color:var(--ink-soft);border-left:2px solid var(--rule);padding-left:14px;max-width:76ch}
  /* 번호 목록: 그리드 금지. 중첩 <ul>이 번호 열로 밀려 레이아웃이 깨진다.
     절대배치 마커 + padding 으로 해결한다. */
  ol.props{margin:0;padding-left:0;list-style:none;counter-reset:p;display:flex;flex-direction:column;gap:18px}
  ol.props>li{counter-increment:p;position:relative;padding-left:34px;font-size:14px;line-height:1.65;color:var(--ink-soft)}
  ol.props>li::before{content:counter(p) ".";position:absolute;left:0;top:0;width:26px;text-align:right;
       font-family:var(--mono);font-weight:600;color:var(--accent-live)}
  ol.props>li strong{color:var(--ink);font-weight:600}
  ol.props ul{margin:8px 0 0;padding-left:17px;display:flex;flex-direction:column;gap:5px}
  ol.props ul li{list-style:disc}
  .note strong{color:var(--ink);font-weight:600}
  .callout{background:var(--surface-sunk);border-left:3px solid var(--accent);padding:16px 20px;
       font-size:14px;color:var(--ink-soft)}
  .callout strong{color:var(--ink);font-weight:600}
  code{font-family:var(--mono);font-size:.92em;background:var(--surface-sunk);padding:1px 5px;border-radius:2px}

  /* ── 표 ── */
  .tw{overflow-x:auto;border:1px solid var(--rule)}
  table{border-collapse:collapse;width:100%;min-width:460px;font-size:13.5px}
  th,td{text-align:left;padding:8px 12px;border-bottom:1px solid var(--rule-soft);vertical-align:top}
  thead th{font-family:var(--mono);font-size:10.5px;text-transform:uppercase;letter-spacing:.1em;
       color:var(--ink-faint);font-weight:600;background:var(--surface-sunk);
       border-bottom:1px solid var(--rule);white-space:nowrap}
  tbody tr:last-child td{border-bottom:0}
  td.n,th.n{text-align:right;font-family:var(--mono);font-variant-numeric:tabular-nums;white-space:nowrap}
  td.mono{font-family:var(--mono);font-size:12.5px}
  tr.hi td{background:var(--surface-sunk);font-weight:600}

  /* ── 판정 배지 ── */
  .v{font-family:var(--mono);font-size:10.5px;font-weight:600;letter-spacing:.08em;
     padding:2px 7px;border-radius:2px;white-space:nowrap;display:inline-block}
  .v-good{color:var(--good);background:var(--good-wash)}
  .v-warn{color:var(--warn);background:var(--warn-wash)}
  .v-bad{color:var(--bad);background:var(--bad-wash)}

  /* ── stat 타일: 히어로 숫자엔 tabular-nums 금지 ── */
  .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;
       background:var(--rule);border:1px solid var(--rule)}
  .stat{background:var(--surface);padding:14px 16px;display:flex;flex-direction:column;gap:2px}
  .stat .k{font-family:var(--mono);font-size:10.5px;text-transform:uppercase;letter-spacing:.1em;color:var(--ink-faint)}
  .stat .v-num{font-family:var(--body);font-size:27px;font-weight:600;letter-spacing:-.02em;line-height:1.15}
  .stat .d{font-size:12px;color:var(--ink-soft)}
  .stat.crit .v-num{color:var(--bad)}
  .stat.ok .v-num{color:var(--good)}

  /* ── 차트 ── */
  figure{margin:0;display:flex;flex-direction:column;gap:12px}
  figcaption{font-family:var(--display);font-weight:700;font-size:14.5px;color:var(--ink)}
  figcaption span{display:block;font-family:var(--body);font-weight:400;font-size:12.5px;
       color:var(--ink-faint);margin-top:2px}
  .legend{display:flex;flex-wrap:wrap;gap:6px 18px;font-family:var(--mono);font-size:11px;color:var(--ink-soft)}
  .legend i{display:inline-block;width:10px;height:10px;margin-right:6px;vertical-align:-1px;border-radius:1px}
  .bars{display:flex;flex-direction:column;gap:9px}
  .row{display:grid;grid-template-columns:minmax(72px,86px) 1fr;gap:12px;align-items:center}
  .rl{font-family:var(--mono);font-size:11.5px;color:var(--ink-soft);text-align:right;
      overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .track{position:relative;display:flex;align-items:center;gap:8px;min-height:20px}
  .fill{height:14px;border-radius:0 4px 4px 0;background:var(--s1);min-width:2px;cursor:default}
  .fill.mute{background:var(--s-mute)}
  .val{font-family:var(--mono);font-size:11.5px;font-variant-numeric:tabular-nums;
       color:var(--ink-soft);white-space:nowrap}
  .val b{color:var(--ink);font-weight:600}
  .pair{display:flex;flex-direction:column;gap:3px}
  .stack{display:flex;gap:2px;height:16px;width:100%;min-width:0}
  .seg{height:16px;min-width:1px;display:flex;align-items:center;justify-content:center;
       overflow:hidden;cursor:default}
  .seg:first-child{border-radius:3px 0 0 3px}
  .seg:last-child{border-radius:0 3px 3px 0}
  .seg em{font-family:var(--mono);font-style:normal;font-size:9.5px;font-weight:600;padding:0 3px}
  .stack-row{display:grid;grid-template-columns:minmax(72px,86px) 1fr minmax(38px,auto);gap:12px;align-items:center}
  .dv{position:relative;height:22px;width:100%}
  .dv-bar{position:absolute;top:4px;height:14px;cursor:default}
  .dv-axis{position:absolute;inset:0;pointer-events:none}
  .dv-tick{position:absolute;top:0;bottom:0;width:1px;background:var(--grid)}
  .dv-tick.zero{background:var(--ink-faint);width:1.5px}
  .axis{position:relative;height:16px;margin-left:98px;font-family:var(--mono);
        font-size:10.5px;color:var(--ink-faint)}
  .axis span{position:absolute;transform:translateX(-50%);white-space:nowrap}
  .chart{width:100%;height:auto;display:block}
  .c-grid{stroke:var(--grid);stroke-width:1}      /* 실선 헤어라인 — 점선 금지 */
  .c-axis{stroke:var(--rule);stroke-width:1}
  .c-tick,.c-lbl{fill:var(--ink-faint);font-family:var(--mono);font-size:11px}
  .c-v{fill:var(--ink);font-family:var(--mono);font-size:12px;font-weight:600}
  .hit{fill:transparent;cursor:default}
  details.tv{border-top:1px dashed var(--rule);padding-top:8px}
  details.tv summary{font-family:var(--mono);font-size:11px;color:var(--accent-live);
       cursor:pointer;letter-spacing:.06em}
  details.tv summary:focus-visible{outline:2px solid var(--accent-live);outline-offset:2px}
  details.tv .tw{margin-top:10px}

  /* ── 툴팁 ── */
  #tip{position:fixed;z-index:60;pointer-events:none;opacity:0;transition:opacity .1s;
       background:var(--ink);color:var(--surface);font-family:var(--mono);font-size:11.5px;
       line-height:1.5;padding:6px 9px;border-radius:3px;max-width:260px;
       box-shadow:0 4px 14px rgba(0,0,0,.25)}
  #tip.on{opacity:1}

  @media (prefers-reduced-motion: reduce){*{scroll-behavior:auto !important;transition:none !important}}
  @media (max-width:640px){
    .doc{padding:0 12px 80px}.slide{padding:24px 20px 20px}.deck{padding:12px 12px 88px}
    .row,.stack-row{grid-template-columns:64px 1fr}.axis{margin-left:76px}
  }
</style>'''

TIP_SCRIPT = '''<div id="tip" role="status" aria-live="polite"></div>
<script>
(function(){
  var tip=document.getElementById('tip');
  function show(t,x,y){tip.textContent=t;tip.classList.add('on');
    var r=tip.getBoundingClientRect();
    tip.style.left=Math.min(Math.max(8,x+14),window.innerWidth-r.width-8)+'px';
    tip.style.top=Math.min(Math.max(8,y-r.height-12),window.innerHeight-r.height-8)+'px';}
  function hide(){tip.classList.remove('on');}
  document.addEventListener('mousemove',function(e){
    var el=e.target.closest?e.target.closest('[data-tip]'):null;
    if(el){show(el.getAttribute('data-tip'),e.clientX,e.clientY);}else{hide();}
  },{passive:true});
  document.addEventListener('mouseleave',hide);
  window.addEventListener('scroll',hide,{passive:true});
})();
</script>'''
