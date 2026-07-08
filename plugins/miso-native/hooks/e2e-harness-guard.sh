#!/usr/bin/env bash
# e2e-harness-guard — PreToolUse(Bash|Read) guard enforcing the Maestro e2e harness.
#
# Opt-in wiring (lsp-first 패턴): 개인 ~/.claude/settings.json 의 hooks.PreToolUse 에
#   matcher "Bash|Read" 로 추가. 자세한 내용은 code_convention/11-테스트-패턴.md "E2E 실행 하네스".
#
# 강제 내용:
#   - raw `maestro test` (E2E_HARNESS=1 sentinel 없음) → deny. /e2e-maestro 스킬로 실행하라.
#   - ~/.maestro/tests/ 하위 모든 debug 산출물(스크린샷 등, 서브디렉터리 포함) Read → deny. maestro hierarchy 를 쓰라.
#
# fail-open: jq 부재·입력 이상 시 아무 결정도 내리지 않고 통과(테스트를 막지 않는다).

input="$(cat)"

tool="$(printf '%s' "$input" | jq -r '.tool_name // ""' 2>/dev/null)"

deny() {
  jq -nc --arg r "$1" \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}' \
    2>/dev/null
  exit 0
}

if [ "$tool" = "Bash" ]; then
  cmd="$(printf '%s' "$input" | jq -r '.tool_input.command // ""' 2>/dev/null)"
  if printf '%s' "$cmd" | grep -qE '(^|[^[:alnum:]_])maestro[[:space:]]+test([[:space:]]|$)'; then
    if ! printf '%s' "$cmd" | grep -q 'E2E_HARNESS=1'; then
      deny "raw 'maestro test' 금지 — /e2e-maestro 스킬로 실행하세요 (model=sonnet 위임 + maestro hierarchy). 스킬은 E2E_HARNESS=1 sentinel 을 붙여 실행하므로 훅을 통과합니다."
    fi
  fi
fi

if [ "$tool" = "Read" ]; then
  fp="$(printf '%s' "$input" | jq -r '.tool_input.file_path // ""' 2>/dev/null)"
  # case 의 * 는 / 도 매칭하므로 timestamp 서브디렉터리(tests/<run>/…)까지 포함된다.
  # 깊이·확장자 무관하게 maestro 디버그 산출물 디렉터리 전체를 막아 모호성을 없앤다.
  case "$fp" in
    */.maestro/tests/*)
      deny "maestro debug 산출물(스크린샷 등) Read 금지 (토큰 헤비) — 'maestro hierarchy' 로 DOM 텍스트를 확인하세요. code_convention/11-테스트-패턴.md 'E2E 실행 하네스' 참조."
      ;;
  esac
fi

exit 0
