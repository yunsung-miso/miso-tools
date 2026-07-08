#!/usr/bin/env bash
# SessionStart hook — linked git worktree에서 세션이 시작되면 main checkout의
# .claude/settings.local.json allow 규칙을 워크트리 쪽으로 머지(union)한다.
# 워크트리에서 자체 승인한 규칙은 보존하고, main에 새로 추가된 규칙만 가져온다.
set -euo pipefail

top=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
common=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || exit 0
main_root=$(dirname "$common")
[ "$main_root" = "$top" ] && exit 0

src="$main_root/.claude/settings.local.json"
[ -f "$src" ] || exit 0

python3 - "$src" "$top/.claude/settings.local.json" <<'PYEOF'
import json, os, sys

src, dst = sys.argv[1], sys.argv[2]
try:
    with open(src) as f:
        src_allow = (json.load(f).get("permissions") or {}).get("allow") or []
except (OSError, json.JSONDecodeError):
    sys.exit(0)

data = {}
if os.path.exists(dst):
    try:
        with open(dst) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        sys.exit(0)  # 손상된 파일은 건드리지 않음

perms = data.setdefault("permissions", {})
allow = perms.setdefault("allow", [])
existing = set(allow)
new_rules = [r for r in src_allow if r not in existing]
if new_rules:
    allow.extend(new_rules)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"[sync-worktree-settings] merged {len(new_rules)} allow rules from main checkout", file=sys.stderr)
PYEOF
exit 0
