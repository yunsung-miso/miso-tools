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

context='[humanize 파이프라인 자동 가이드] 이 스킬로 작성하는 한국어 본문(PR 본문 / 리뷰 답글 / 이슈 설명)은 gh·Linear 등으로 최종 제출하기 직전에 humanize-korean 의 번역투·AI 티 제거 규칙을 적용해 다듬어라. 규칙 파일: ~/.claude/skills/humanize-korean/references/quick-rules.md 를 읽어서 인라인으로 적용한다(연결어미 뒤 쉼표 제거, 불필요한 피동·이중피동, "~에 대해/~를 통해/~에 있어" 같은 번역투, 결말 공식, 과한 볼드·이모지, 동일 종결어미 반복 정리). 무거운 오케스트레이터(_workspace 디렉토리 생성, 서브에이전트 호출)는 돌리지 말고 룰만 적용할 것. 의미·수치·고유명사·코드·링크·티켓ID 는 한 글자도 바꾸지 말고, 친근한 해요체(제목만 명령형)와 이모지 금지 컨벤션을 유지한다. 이어서 humanize-me(윤성 개인 문체) 패스를 마지막에 적용한다: Claude 문체 습관 3종(무생물 주어 의인화, 은유 중첩=기름진 문장, 자기판정형 수사)을 걷어내고 짧고 직설적인 사실 중심 어조로 바꾼다. 의인화는 추상명사("의심이 번진다")만이 아니라 구체 무생물 + 평범한 동사("로그가 불어난다", "에러가 목록을 채운다", "노이즈가 볼륨을 차지한다", "이벤트가 사라진다", "실패를 부풀린다")까지 전부 대상이다. 주어가 사람·기관이 아닌 문장을 동사 세기와 무관하게 전수 검사하고, 행위자를 코드·시스템·도구·이 변경·원인 중 하나로 세워라(예: host가 error로 네 번 기록해요 / Datadog은 warn을 Logs에 저장하고 RUM 에러 목록에는 넣지 않아요 / 이 변경으로 28,444건을 줄여요 / 반복되는 원인은 리마운트예요). 상태 서술(있다·없다·남는다)까지는 무생물 주어를 허용한다. PR 본문과 이슈 설명은 이 작업을 전혀 모르는 동료가 독자라고 전제하고 추상화·일반화까지 검사한다: 내부 식별자(로그 문자열·scope 이름·함수명)를 역할 이름으로 바꿔 부르고, 파일 경로에는 무슨 파일인지 한 마디를 붙이고, 내부 용어·약어는 첫 등장에 풀어 쓰고, 세션 안에서만 통하는 지시("아까 그 케이스", "위에서 본 구조")와 조사 서사(가설→반증→재측정)는 지워 결론만 남기고, 왜 이게 문제인가·무엇이 바뀌는가·안전한가(호환·롤백) 세 질문에 본문이 답하는지 확인한다. 서술형 나열이 세 줄을 넘으면 표로 바꾼다. humanize-me 스킬 정의(SKILL.md)를 따르며, 적용 순서는 humanize-korean(범용 AI 티) → humanize-me(개인 문체)로 고정한다. 살릴 것: 짧고 구체적인 펀치어·화자 본인 경험·의도된 반복·핵심 주장 문장.'

jq -cn --arg ctx "$context" '{hookSpecificOutput:{hookEventName:"PreToolUse",additionalContext:$ctx}}'
