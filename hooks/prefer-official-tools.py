#!/usr/bin/env python3
"""Auto-deny shell commands that duplicate an official tool, redirecting Claude.

PreToolUse(Bash) hook. Judges the HEAD command of every statement in the line
— statements split on && || ; & ( ) and newlines — so a chained binary like
`cd x && /repo/node_modules/.bin/eslint ...` is caught (the second statement's
head is the binary). Within a statement, only the pipeline head is judged, so
piped filters (`git log | grep x`) stay allowed.

Kept deliberately allowed: find (sanctioned file-finder per repo note), rg
(incl. its absolute /opt/homebrew/bin/rg form used to dodge rtk rewrite), and
every real dev tool (git/gh/pnpm/node/...). Emits permissionDecision=deny so
there is NO interactive prompt — the reason is fed straight back to the model.
"""
import sys
import re
import json
import shlex

PROXY_PREFIXES = {"rtk", "command", "env", "nice", "time", "sudo", "xargs"}
STATEMENT_SEP = {"&&", "||", ";", "&", "(", ")"}
PIPE = {"|", "|&"}

REDIRECT = {
    "cat": "파일 읽기는 Read 도구를 쓰세요 (cat 금지). 파이프 필터면 첫 명령을 바꾸세요.",
    "head": "파일 앞부분은 Read(offset/limit)를 쓰세요 (head 금지).",
    "tail": "파일 뒷부분은 Read를, 로그 추적은 run_in_background + BashOutput을 쓰세요 (tail 금지).",
    "sed": "파일 수정은 Edit, 읽기는 Read를 쓰세요 (sed 금지).",
    "awk": "파일 파싱은 Read로 읽고 처리하세요 (awk 금지).",
    "grep": "검색은 rg를 쓰세요 (grep 금지). 파이프 뒤 필터는 첫 명령을 바꾸면 허용됩니다.",
    "ls": "디렉터리 확인은 Read(디렉터리) 또는 `rg --files -g '<glob>'`를 쓰세요 (ls 금지).",
}


def deny(reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def judge(head):
    """Deny if head is a path-run binary (except rg) or a tool-replaceable cmd."""
    base = head.rsplit("/", 1)[-1]
    if (head.startswith("/") or "node_modules/.bin/" in head) and base != "rg":
        deny(f"경로로 바이너리 직접 실행 금지 ({base}). `pnpm exec {base}` 또는 공식 도구를 쓰세요.")
    if base in REDIRECT:
        deny(REDIRECT[base])


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    if data.get("tool_name") != "Bash":
        sys.exit(0)
    cmd = ((data.get("tool_input") or {}).get("command") or "").strip()
    if not cmd:
        sys.exit(0)

    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=";&|<>()")
        lex.whitespace_split = True
        tokens = list(lex)
    except ValueError:
        sys.exit(0)  # unparseable → leave to block-unanalyzable-bash.py

    n = len(tokens)
    i = 0
    at_head = True
    while i < n:
        tok = tokens[i]
        if tok in STATEMENT_SEP:
            at_head = True
            i += 1
            continue
        if tok in PIPE:
            # downstream of a pipe is a filter chain — skip to next statement
            i += 1
            while i < n and tokens[i] not in STATEMENT_SEP:
                i += 1
            continue
        if not at_head:
            i += 1
            continue
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tok):  # env assignment prefix
            i += 1
            continue
        if tok.rsplit("/", 1)[-1] in PROXY_PREFIXES:    # rtk/env/sudo/... wrapper
            i += 1
            continue
        judge(tok)          # deny exits; if it returns, this head was clean
        at_head = False
        i += 1

    sys.exit(0)


main()
