#!/usr/bin/env bash
# PreToolUse(Skill) hook.
# create-pr / review-reply / gh-review-reply / create-issue 스킬이 발동하면,
# 해당 스킬이 만드는 한국어 본문을 최종 제출 직전에 humanize-korean 규칙으로
# 다듬으라는 가이드를 모델 컨텍스트에 주입한다.

input=$(cat)
skill=$(printf '%s' "$input" | jq -r '.tool_input.skill // empty' 2>/dev/null)

case "$skill" in
  create-pr | review-reply | gh-review-reply | create-issue) ;;
  *) exit 0 ;;
esac

context='[humanize 파이프라인 자동 가이드] 이 스킬로 작성하는 한국어 본문(PR 본문 / 리뷰 답글 / 이슈 설명)은 gh·Linear 등으로 최종 제출하기 직전에 humanize-korean 의 번역투·AI 티 제거 규칙을 적용해 다듬어라. 규칙 파일: ~/.claude/skills/humanize-korean/references/quick-rules.md 를 읽어서 인라인으로 적용한다(연결어미 뒤 쉼표 제거, 불필요한 피동·이중피동, "~에 대해/~를 통해/~에 있어" 같은 번역투, 결말 공식, 과한 볼드·이모지, 동일 종결어미 반복 정리). 무거운 오케스트레이터(_workspace 디렉토리 생성, 서브에이전트 호출)는 돌리지 말고 룰만 적용할 것. 의미·수치·고유명사·코드·링크·티켓ID 는 한 글자도 바꾸지 말고, 친근한 해요체(제목만 명령형)와 이모지 금지 컨벤션을 유지한다. 이어서 humanize-me(윤성 개인 문체) 패스를 마지막에 적용한다: Claude 문체 습관 3종(추상명사 의인화 예 "의심이 번진다", 은유 중첩=기름진 문장, 자기판정형 수사)을 걷어내고 짧고 직설적인 사실 중심 어조로 바꾼다. humanize-me 스킬 정의(SKILL.md)를 따르며, 적용 순서는 humanize-korean(범용 AI 티) → humanize-me(개인 문체)로 고정한다. 살릴 것: 짧고 구체적인 펀치어·화자 본인 경험·의도된 반복·핵심 주장 문장.'

jq -cn --arg ctx "$context" '{hookSpecificOutput:{hookEventName:"PreToolUse",additionalContext:$ctx}}'
