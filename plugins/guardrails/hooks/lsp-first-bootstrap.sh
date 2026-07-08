#!/usr/bin/env bash
# SessionStart hook — this machine runs a NATIVE Claude Code build, which folds the
# standalone Grep/Glob/TodoWrite tools into Bash (embedded bfs/ugrep). Inject routing
# guidance so the agent reaches for LSP (symbols) and Bash rg (text/files) instead of
# trying the absent tools, and never uses cd-compounds that trigger permission prompts.
# Non-blocking: emits additionalContext only, never blocks the session.
cat > /dev/null  # consume hook stdin (unused)

python3 - <<'PY'
import json
ctx = (
  "[tooling/native-build] The Grep, Glob, and TodoWrite tools do NOT exist in this session "
  "(native Claude Code build folds search into Bash). Do not attempt to call them. Search routing:\n"
  "- SYMBOL navigation (definition, references, implementations, type/hover, document & "
  "workspace symbols, call hierarchy): use the LSP tool. It is deferred — load it once per "
  "session with ToolSearch query \"select:LSP\". TypeScript and Swift language servers are "
  "installed; Kotlin/Groovy/JSON/YAML/.env have no server, so use rg for those.\n"
  "- TEXT / content search: Bash `rg '<pattern>' <path>` (allowlisted — no prompt).\n"
  "- FILE finding: `/opt/homebrew/bin/rg --files -g '<glob>'` or `find` (bare `rg --files` is rewritten to grep by rtk on this machine and fails — use the absolute path or find). FILE CONTENTS: use the Read tool, never cat/sed/head pipelines.\n"
  "- NEVER use `cd <path> && ...` or `cd <path>; ...` compound commands — each one triggers a "
  "permission prompt. Use absolute paths, `git -C <path>`, or a tool's own project-dir flag "
  "(e.g. `gradlew -p <path>`).\n"
  "- NEVER put command substitution `$(...)`, variable assignment (`f=...`), or multi-step pipelines in a single Bash call — the permission engine can't statically analyze them ('cannot be statically analyzed') and always prompts, regardless of rtk. Split into simple single commands and read files with the Read tool."
)
print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ctx}}))
PY
