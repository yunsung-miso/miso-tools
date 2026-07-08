#!/usr/bin/env python3
"""PreToolUse(Bash) guard: deny commands whose shape defeats the permission
engine's static analysis, so the allowlist (e.g. Bash(pnpm:*)) can actually match.

On this native Claude Code build, commands containing command substitution,
sequencing, exit-status expansion, file redirects, or multi-stage pipes are
flagged "cannot be statically analyzed" and prompt every time regardless of
allow rules. We block those and tell the agent to reformulate into single
commands (use run_in_background for output capture, the Read tool for files).

Allowed (not flagged): &&, a single |, and VAR=value env-prefix commands.
Quote-aware: characters inside single/double quotes never trigger.
"""
import json
import sys


def strip_quotes(s):
    out = []
    quote = None
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if quote == "'":
            if c == "'":
                quote = None
            i += 1
            continue
        if quote == '"':
            if c == "\\" and i + 1 < n:
                i += 2
                continue
            if c == '"':
                quote = None
            i += 1
            continue
        if c == "'":
            quote = "'"
        elif c == '"':
            quote = '"'
        else:
            out.append(c)
        i += 1
    return "".join(out)


def count_pipes(s):
    # Count single-pipe operators, ignoring logical ||.
    return s.replace("||", "").count("|")


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return  # unparseable input: do not block
    if data.get("tool_name") != "Bash":
        return
    command = (data.get("tool_input") or {}).get("command", "")
    if not command:
        return

    bare = strip_quotes(command)

    findings = []
    if "$(" in bare or "`" in bare:
        findings.append("명령 치환 $()/백틱")
    if "$?" in bare:
        findings.append("$? 확장")
    if ";" in bare:
        findings.append("; 명령 나열")
    if ">" in bare:
        findings.append("파일 리다이렉트 >")
    if count_pipes(bare) >= 2:
        findings.append("다단계 파이프(2개 이상)")

    if not findings:
        return

    reason = (
        "이 Bash 명령은 정적 분석이 안 되는 패턴이라 allowlist(Bash(pnpm:*) 등)가 매칭되지 못하고 "
        "매번 권한 프롬프트를 유발합니다. 발견: " + ", ".join(findings) + ". "
        "해결: (1) 단일 명령으로 쪼개세요(한 호출에 하나). "
        "(2) 출력 저장은 리다이렉트 대신 run_in_background를 쓰세요(자동 로그 파일이 생깁니다). "
        "(3) 파일 내용은 Read 도구로 보세요. "
        "(4) 값 캡처가 필요하면 $(...) 대신 단계를 나누세요. "
        "(&&, 단일 |, VAR=value 형식의 env-prefix는 허용됩니다.)"
    )
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
