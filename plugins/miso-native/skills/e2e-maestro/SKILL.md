---
name: e2e-maestro
description: Maestro e2e 테스트를 강제 규칙대로 실행한다 — 실행은 model=sonnet 서브에이전트 위임, 화면 확인은 maestro hierarchy(스크린샷 아님). raw `maestro test` 직접 호출 대신 이 스킬을 쓴다.
---

# E2E Maestro 실행 스킬

Maestro e2e 테스트의 **유일한 sanctioned 실행 경로**다. raw `maestro test` 직접 호출은 `e2e-harness-guard` 훅이 deny한다. 컨벤션 `code_convention/11-테스트-패턴.md`의 "E2E 실행 하네스" 참조.

## 강제하는 두 규칙

1. **실행은 Sonnet**: maestro 실행을 `model=sonnet` 서브에이전트(Agent tool)로 위임한다. 테스트 실행·반복은 기계적이라 Sonnet으로 충분하고 비용·속도가 낫다. Opus 메인 루프는 결과 진단·설계만 한다.
2. **화면 확인은 hierarchy**: 결과는 `maestro hierarchy`(DOM 텍스트)로 본다. 스크린샷 PNG를 Read하지 않는다(토큰 헤비). `~/.maestro/tests/**/*.png` debug 스크린샷 Read는 훅이 막는다.

## 절차

전제: 시뮬레이터 부팅 + 필요한 Metro(`ENABLE_MIRAGE=true`로 host·customer·partner 등)는 호출자가 미리 기동한다. 스킬은 이를 확인만 하고 빌드는 하지 않는다.

1. **`model=sonnet` 서브에이전트를 dispatch**한다. 서브에이전트 프롬프트에 다음을 지시한다:
   - `E2E_HARNESS=1 maestro test <flow-path>`로 실행한다. **`E2E_HARNESS=1` sentinel은 필수** — 훅이 이 sentinel 없는 `maestro test`를 deny한다.
   - 실패하거나 화면 상태를 봐야 하면 `maestro hierarchy`로 현재 뷰 계층을 덤프하고 `rg '"accessibilityText" : "[^"]+"'`(콜론 양옆 공백)로 텍스트를 뽑는다. 카드 등 결합 노드는 accessibilityText가 콤마로 합쳐지므로 부분 문자열은 `(?s).*텍스트.*` regex로 매칭한다.
   - 스크린샷 PNG는 Read하지 않는다. 시각 회귀처럼 이미지가 꼭 필요한 경우에만 명시적으로 캡처하고 그 이유를 보고한다.
   - 반환: 플로우 통과/실패 + 진단에 필요한 DOM 텍스트·로그만. 스크린샷 이미지는 반환하지 않는다.
2. 서브에이전트 결과를 받아 메인 루프(Opus)가 진단·다음 단계를 결정한다. 플로우 수정이 필요하면 수정 후 다시 이 스킬로 재실행한다.

## 팁 (실측 학습)

- 마이페이지 등 탭 전환 첫 탭이 네비를 놓칠 수 있다 → 더블탭으로 보강(탭은 멱등). retry 블록은 성공해도 exit 1 artifact를 남기니 피한다.
- 콜드 번들/재번들 직후엔 첫 화면이 늦게 뜬다 → 알림 권한 팝업·첫 화면 대기 timeout을 넉넉히(120s 등).
