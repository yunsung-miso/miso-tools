#!/usr/bin/env python3
"""Stop hook: render a self-contained HTML session report on every turn end.

Full-permission operating model, part 3: when the agent finishes, hand back an
audit + summary report. Non-blocking — never emits decision:block. Rewrites the
same file each Stop so the report is always current; there is no reliable
"task done" signal, so freshness-on-every-stop stands in for it.

Data sources: the session transcript (transcript_path, JSONL) for commands run,
files touched, and the closing summary; plus blocklog-<session>.jsonl (written by
block-destructive-commands.py) for the authoritative list of blocked attempts.

Ceilings:
- Re-renders on every Stop = a few-KB local file write; negligible. Add a debounce
  if it ever churns.
- Transcript JSONL shape is harness-version-dependent; parsing is best-effort and
  degrades to blocklog-only rather than failing.
"""
import datetime
import html
import json
import os
import sys


def read_stdin_json():
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def parse_transcript(path):
    """Return (commands, files, summary). Best-effort; empty on any failure."""
    commands, files, summary = [], [], ""
    seen_files = set()
    if not path or not os.path.exists(path):
        return commands, files, summary
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return commands, files, summary
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        if entry.get("type") != "assistant":
            continue
        content = (entry.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for c in content:
            if not isinstance(c, dict):
                continue
            ctype = c.get("type")
            if ctype == "text":
                text = (c.get("text") or "").strip()
                if text:
                    summary = text  # last non-empty assistant text wins
            elif ctype == "tool_use":
                name = c.get("name")
                inp = c.get("input") or {}
                if name in ("Bash", "BashOutput") and inp.get("command"):
                    commands.append(inp["command"])
                elif name in ("Edit", "Write", "NotebookEdit"):
                    fp = inp.get("file_path") or inp.get("notebook_path")
                    if fp and fp not in seen_files:
                        seen_files.add(fp)
                        files.append(fp)
    return commands, files, summary


def read_blocklog(base, session):
    blocks = []
    path = os.path.join(base, ".claude", "guardrails", f"blocklog-{session}.jsonl")
    if not os.path.exists(path):
        return blocks
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        blocks.append(json.loads(line))
                    except Exception:
                        pass
    except Exception:
        pass
    return blocks


def li_list(items, render):
    if not items:
        return '<p class="empty">없음</p>'
    return "<ul>" + "".join(f"<li>{render(x)}</li>" for x in items) + "</ul>"


def build_html(session, commands, files, blocks, summary, now):
    esc = html.escape
    summary_html = esc(summary) if summary else "요약 없음 (트랜스크립트 미확보)"
    blocks_html = (
        '<p class="empty">차단된 시도 없음</p>' if not blocks else
        "<ul>" + "".join(
            f'<li><code>{esc(b.get("command", ""))}</code>'
            f'<span class="reason">{esc(b.get("reason", ""))}</span>'
            f'<span class="ts">{esc(b.get("ts", ""))}</span></li>'
            for b in blocks
        ) + "</ul>"
    )
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>guardrails 세션 보고서</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font: 15px/1.6 -apple-system, system-ui, sans-serif; max-width: 900px;
         margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; background: #fff; }}
  @media (prefers-color-scheme: dark) {{ body {{ color: #e6e6e6; background: #16181d; }} }}
  h1 {{ font-size: 1.5rem; margin-bottom: .2rem; }}
  h2 {{ font-size: 1.1rem; margin-top: 2rem; border-bottom: 1px solid #8883; padding-bottom: .3rem; }}
  .meta {{ color: #8a8a8a; font-size: .85rem; }}
  .stats {{ display: flex; gap: 1rem; flex-wrap: wrap; margin: 1rem 0; }}
  .stat {{ background: #8881; border-radius: 8px; padding: .6rem 1rem; }}
  .stat b {{ display: block; font-size: 1.6rem; }}
  .stat.blocked b {{ color: #d33; }}
  .summary {{ white-space: pre-wrap; background: #8881; border-radius: 8px; padding: 1rem; }}
  ul {{ padding-left: 0; list-style: none; }}
  li {{ margin: .3rem 0; }}
  code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .85rem;
         background: #8882; padding: .1rem .35rem; border-radius: 4px;
         display: inline-block; max-width: 100%; overflow-x: auto; white-space: pre; }}
  #blocked li {{ border-left: 3px solid #d33; padding-left: .6rem; margin: .6rem 0; }}
  #blocked .reason {{ display: block; color: #c22; font-size: .85rem; margin-top: .2rem; }}
  #blocked .ts {{ color: #8a8a8a; font-size: .75rem; }}
  .empty {{ color: #8a8a8a; font-style: italic; }}
</style></head><body>
<h1>🛡️ guardrails 세션 보고서</h1>
<p class="meta">세션 <code>{esc(session)}</code> · 생성 {esc(now)}</p>
<div class="stats">
  <div class="stat"><b>{len(commands)}</b>실행 명령</div>
  <div class="stat"><b>{len(files)}</b>편집·생성 파일</div>
  <div class="stat blocked"><b>{len(blocks)}</b>차단된 시도</div>
</div>
<h2>작업 요약</h2>
<div class="summary">{summary_html}</div>
<h2>편집·생성 파일</h2>
{li_list(files, lambda f: f'<code>{esc(f)}</code>')}
<h2>실행 명령</h2>
{li_list(commands, lambda c: f'<code>{esc(c)}</code>')}
<h2 id="blocked">차단된 시도</h2>
{blocks_html}
</body></html>
"""


def main():
    data = read_stdin_json()
    base = data.get("cwd") or os.getcwd()
    session = data.get("session_id") or "unknown"
    now = datetime.datetime.now().isoformat(timespec="seconds")

    commands, files, summary = parse_transcript(data.get("transcript_path"))
    blocks = read_blocklog(base, session)

    out_dir = os.path.join(base, ".claude", "guardrails")
    try:
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"report-{session}.html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(build_html(session, commands, files, blocks, summary, now))
        print(f"📄 guardrails 보고서: {out_path}")
    except Exception:
        pass  # a Stop hook must never fail the turn


if __name__ == "__main__":
    main()
