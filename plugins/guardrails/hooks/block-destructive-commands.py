#!/usr/bin/env python3
"""PreToolUse(Bash) guard: block irreversibly destructive commands.

Full-permission operating model: allow Bash broadly, deny only what you can't
undo. Reversible ops are intentionally NOT here — force-pushing a feature branch
(rebase workflow) and local branch deletion (`git branch -d`, reflog-recoverable)
pass through. Only protected-branch history rewrites, remote branch deletion,
root/home wipes, destructive SQL, and infra teardown are denied.

On a block: append the attempt to .claude/guardrails/blocklog-<session>.jsonl
(audit trail for the completion report) then emit permissionDecision=deny so
there is no interactive prompt — the reason is fed straight back to the model.

Deliberate ceilings:
- `git push -f` with no branch named passes (can't know the branch; keeps the
  feature-branch rebase workflow unblocked). Names must appear to trigger.
- SQL/terraform/kubectl matching is raw-regex, so `echo "DROP TABLE x"` also
  trips it. Over-blocking a rare echo is acceptable for a guardrail; git/rm use
  quote-aware tokenising and don't have this issue.
"""
import datetime
import json
import os
import re
import shlex
import sys

PROTECTED = {"main", "master", "production", "prod"}
FORCE_FLAGS = {"-f", "--force", "--force-with-lease"}
DANGEROUS_ROOTS = {"/", "/*", "~", "~/", "$HOME", "${HOME}", "$HOME/", "${HOME}/"}

# (regex, reason) — raw-command patterns, case-insensitive.
REGEX_RULES = [
    (re.compile(r"\bsudo\s+rm\b.*\s-\w*[rf]", re.I),
     "sudo rm 재귀/강제 삭제는 시스템 파괴 위험이라 차단됩니다. 필요하면 터미널에서 직접 실행하세요."),
    (re.compile(r"\bDROP\s+(DATABASE|TABLE|SCHEMA)\b", re.I),
     "DROP DATABASE/TABLE/SCHEMA 는 되돌릴 수 없어 차단됩니다. 필요하면 터미널에서 직접 실행하세요."),
    (re.compile(r"\bTRUNCATE\b", re.I),
     "TRUNCATE 는 데이터를 되돌릴 수 없어 차단됩니다. 필요하면 터미널에서 직접 실행하세요."),
    (re.compile(r"\bterraform\s+destroy\b", re.I),
     "terraform destroy 는 인프라를 파괴하므로 차단됩니다. 필요하면 터미널에서 직접 실행하세요."),
    (re.compile(r"\bterraform\s+apply\b[^\n]*\s-auto-approve\b", re.I),
     "terraform apply -auto-approve 는 확인 없이 인프라를 바꾸므로 차단됩니다. -auto-approve 없이 실행하세요."),
    (re.compile(r"\bkubectl\s+delete\b", re.I),
     "kubectl delete 는 리소스를 삭제하므로 차단됩니다. 필요하면 터미널에서 직접 실행하세요."),
    (re.compile(r"\bkubectl\s+drain\b[^\n]*--force\b", re.I),
     "kubectl drain --force 는 노드를 강제로 비우므로 차단됩니다. 필요하면 터미널에서 직접 실행하세요."),
]


def is_protected_ref(tok):
    """True when the ref token targets a protected branch. Segment-based so
    `feature/main-menu` (last segment 'main-menu') does NOT match, but `main`,
    `HEAD:main`, `+main`, and `release/*` do."""
    seg = tok.lstrip("+").split(":")[-1]
    if seg.startswith("release/"):
        return True
    return seg.split("/")[-1] in PROTECTED


def check_rm(tokens):
    if "rm" not in tokens:
        return None
    args = tokens[tokens.index("rm") + 1:]
    recursive = force = False
    targets = []
    for a in args:
        if a.startswith("--"):
            recursive = recursive or a == "--recursive"
            force = force or a == "--force"
        elif a.startswith("-") and len(a) > 1:
            recursive = recursive or ("r" in a[1:].lower())
            force = force or ("f" in a[1:])
        else:
            targets.append(a)
    if recursive and force and any(t in DANGEROUS_ROOTS for t in targets):
        return "루트(/)·홈(~/$HOME) 디렉터리를 재귀·강제 삭제하려는 명령이 차단됩니다. 필요하면 터미널에서 직접 실행하세요."
    return None


def check_git(tokens):
    if "git" not in tokens or "push" not in tokens:
        return None
    has_force = any(t in FORCE_FLAGS or t.startswith("--force-with-lease=") for t in tokens)
    plus_ref = any(t.startswith("+") and is_protected_ref(t) for t in tokens)
    protected_targets = [t for t in tokens if not t.startswith("-") and is_protected_ref(t)]
    if (has_force or plus_ref) and (protected_targets or plus_ref):
        return ("보호 브랜치(main/master/release-*/prod)로의 force push 는 남의 커밋을 날릴 수 있어 "
                "차단됩니다. feature 브랜치 force push 는 허용됩니다. 꼭 필요하면 --force-with-lease 로 "
                "터미널에서 직접 실행하세요.")
    if any(t in ("--delete", "-d") for t in tokens):
        return "원격 브랜치 삭제(git push --delete)는 차단됩니다. 로컬 삭제(git branch -d)는 허용됩니다."
    if any(t.startswith(":") and len(t) > 1 for t in tokens):
        return "원격 브랜치 삭제(git push <remote> :branch)는 차단됩니다."
    return None


def append_blocklog(data, reason):
    try:
        base = data.get("cwd") or os.getcwd()
        session = data.get("session_id") or "unknown"
        d = os.path.join(base, ".claude", "guardrails")
        os.makedirs(d, exist_ok=True)
        rec = {
            "ts": datetime.datetime.now().isoformat(timespec="seconds"),
            "command": (data.get("tool_input") or {}).get("command", ""),
            "reason": reason,
        }
        with open(os.path.join(d, f"blocklog-{session}.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass  # logging must never swallow or block the deny decision


def deny(reason, data):
    append_blocklog(data, reason)
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }, ensure_ascii=False))
    sys.exit(0)


def evaluate(cmd):
    """Return a deny reason for a destructive command, else None. Pure — the
    testable core of this hook."""
    cmd = (cmd or "").strip()
    if not cmd:
        return None
    for rx, reason in REGEX_RULES:
        if rx.search(cmd):
            return reason
    try:
        tokens = shlex.split(cmd, posix=True)
    except ValueError:
        tokens = cmd.split()  # unbalanced quotes etc: crude split, still useful
    for check in (check_rm, check_git):
        reason = check(tokens)
        if reason:
            return reason
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return  # unparseable input: do not block
    if data.get("tool_name") != "Bash":
        return
    reason = evaluate((data.get("tool_input") or {}).get("command") or "")
    if reason:
        deny(reason, data)


if __name__ == "__main__":
    main()
