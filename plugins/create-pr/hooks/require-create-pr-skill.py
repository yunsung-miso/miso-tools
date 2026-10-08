#!/usr/bin/env python3
"""Deny PR creation via gh until the create-pr skill has been loaded in this session.

PreToolUse(Bash) hook. Catches `gh pr create` and `gh api ... pulls -X POST`
at any statement head (rtk/env/... prefixes stripped). Passes when the session
transcript shows the create-pr skill was invoked (Skill tool or /create-pr).
"""
import json
import re
import shlex
import sys

PROXY_PREFIXES = {"rtk", "command", "env", "nice", "time", "xargs"}
STATEMENT_SEP = {"&&", "||", ";", "&", "(", ")", "|", "|&"}
SKILL_USED = re.compile(r'"skill"\s*:\s*"[^"]*create-pr"|<command-name>/?[^<]*create-pr</command-name>')
REASON = (
    "PR 생성은 create-pr 스킬로만 합니다. Skill 도구로 `create-pr`을 먼저 호출하고 "
    "스킬 절차(base 자동 판별·본문 템플릿 검사)를 따라 다시 실행하세요."
)


def statements(cmd):
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=";&|<>()")
    lex.whitespace_split = True
    stmt = []
    for tok in lex:
        if tok in STATEMENT_SEP:
            if stmt:
                yield stmt
            stmt = []
        else:
            stmt.append(tok)
    if stmt:
        yield stmt


def strip_prefixes(stmt):
    i = 0
    while i < len(stmt) and (
        stmt[i].rsplit("/", 1)[-1] in PROXY_PREFIXES
        or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", stmt[i])
    ):
        i += 1
    return stmt[i:]


def creates_pr(stmt):
    stmt = strip_prefixes(stmt)
    if not stmt or stmt[0].rsplit("/", 1)[-1] != "gh":
        return False
    args = stmt[1:]
    if args[:2] == ["pr", "create"]:
        return True
    if args[:1] == ["api"]:
        method = next(
            (nxt for a, nxt in zip(args, args[1:]) if a in ("-X", "--method")),
            next((a.split("=", 1)[1] for a in args if a.startswith("--method=")), None),
        )
        # gh api defaults to POST when any field/input flag is present
        has_body = any(re.match(r"^(-[fF]|--field|--raw-field|--input)(=|$)", a) for a in args)
        posts = (method or ("POST" if has_body else "GET")).upper() == "POST"
        return posts and any(re.search(r"/pulls/?$", a) for a in args)
    return False


def skill_used(transcript_path):
    try:
        with open(transcript_path, encoding="utf-8") as f:
            return any(SKILL_USED.search(line) for line in f)
    except (OSError, TypeError):
        return False


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    if data.get("tool_name") != "Bash":
        sys.exit(0)
    cmd = (data.get("tool_input") or {}).get("command") or ""
    try:
        hit = any(creates_pr(s) for s in statements(cmd))
    except ValueError:
        hit = "gh pr create" in cmd
    if hit and not skill_used(data.get("transcript_path")):
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": REASON,
            }
        }))
    sys.exit(0)


main()
