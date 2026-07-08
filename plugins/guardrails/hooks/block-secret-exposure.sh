#!/usr/bin/env bash
# PreToolUse hook: block Bash commands that may expand secret env vars to chat.
# Reads tool input JSON from stdin, prints decision JSON to stdout (exit 0).

set -u

input=$(cat)
cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // empty')

if [ -z "$cmd" ]; then
  exit 0
fi

# Secret name fragments (matched case-insensitively against env var names).
secret_re='(API_?KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|PRIVATE_?KEY|ACCESS_?KEY|AUTH)'

# Block patterns:
#   1. $VAR or ${VAR} expansion where VAR name contains a secret fragment
#   2. printenv VAR (direct dump of a secret-named env var)
#   3. env | grep/awk/sed/rg ...secret... (filter env for secrets)
block_re="(\\\$\\{?[A-Z_]*${secret_re}[A-Z_]*\\}?|printenv[[:space:]]+[A-Z_]*${secret_re}|env[[:space:]]*\\|[[:space:]]*(grep|awk|sed|rg)[^|]*${secret_re})"

if printf '%s' "$cmd" | grep -qiE "$block_re"; then
  cat <<'JSON'
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"이 Bash 명령이 시크릿 환경변수($DD_API_KEY/$TOKEN/$SECRET 등)를 채팅에 노출할 수 있어 차단됩니다. 의도한 명령이면 터미널에서 직접 실행하거나, 시크릿 값을 참조하지 않도록 명령을 다시 작성하세요."}}
JSON
  exit 0
fi

# Block copying/moving/writing secret .env files (use `pnpm env:staging` / getEnv.sh instead).
# `pnpm env:staging` / `./scripts/getEnv.sh` themselves are NOT matched: getEnv.sh does its
# `mv $tmp .env.staging` inside the script (subprocess), not as a top-level agent command.
env_file='\.env([.][A-Za-z]+)?([[:space:]/]|$)'
env_template='\.env\.(example|sample|template)'
if printf '%s' "$cmd" | grep -qE '(^|[[:space:];|&])(cp|mv|rsync|scp|ditto|install)[[:space:]]' \
  && printf '%s' "$cmd" | grep -qE "$env_file" \
  && ! printf '%s' "$cmd" | grep -qE "$env_template"; then
  cat <<'JSON'
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"시크릿 .env 파일을 복사/이동하는 명령이 차단됐습니다 (SSM 인증 우회·유출 위험). 워크트리 env 는 `pnpm env:staging`(getEnv.sh → SSM)로 생성하세요. SessionStart 훅 sync-worktree-env.sh 가 워크트리에서 자동 생성을 시도합니다."}}
JSON
  exit 0
fi

if printf '%s' "$cmd" | grep -qE '(>[[:space:]]*[^[:space:]|&;<>]*|tee[[:space:]]+([^|&;]*[[:space:]])?)\.env([.][A-Za-z]+)?([[:space:]]|$)' \
  && ! printf '%s' "$cmd" | grep -qE "$env_template"; then
  cat <<'JSON'
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"시크릿 .env 파일에 직접 쓰는 명령이 차단됐습니다 (SSM 인증 우회·유출 위험). `pnpm env:staging`(getEnv.sh → SSM)로 생성하세요."}}
JSON
  exit 0
fi

exit 0
