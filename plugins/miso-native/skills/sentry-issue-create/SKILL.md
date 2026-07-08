---
name: sentry-issue-create
description: Sentry 에서 보고된 production/staging 에러를 Linear Product 팀 이슈로 등록하면서 자동으로 Sentry 라벨을 붙이고, QA(김민지) / FE(윤성) / 매니저(김경민) 3명에게 코멘트로 알림. "sentry 이슈 만들어줘", "sentry → linear", "센트리 이슈 등록", "MISO-NATIVE-XX 를 이슈로" 같은 요청에 사용.
---

# Sentry → Linear 이슈 생성 스킬

Sentry 의 production/staging 에러를 Linear `Product` 팀 이슈로 등록하는 표준 흐름. 라벨 일관성과 3명 알림을 자동화.

## 전제 조건

- `~/.zshenv` 에 `SENTRY_AUTH_TOKEN`, `SENTRY_ORG=miso-ea`, `SENTRY_PROJECT=miso-native` 설정 (sentry-prod-analyze 스킬과 공유)
- Linear MCP 도구 사용 가능: `list_issue_labels`, `save_issue`, `save_comment`, `get_issue`, `list_issues`
- 본 스킬은 Product 팀 전용 — `team: "Product"` 고정, `PRD-` prefix 확인 필수

## 입력 정보 수집

### 필수
- **Sentry 식별자**: shortId (`MISO-NATIVE-1C`) / numeric id / Sentry URL 중 하나
- **이슈 제목**: 한글, 대괄호 prefix 권장 — `[크래시/MF]`, `[관측/안정성]`, `[채팅]`, `[푸시]`, `[결제]` 등
- **간단한 1~3줄 진단 가설** (수정 전 진단 우선 원칙)

### 선택 (기본값 있음)
- 우선순위: 자동 추천 (아래 표 참조), 사용자 명시 시 그쪽이 우선
- 라벨: `["Dev", "bug", "Sentry"]` 기본 + 도메인 추가 (`communication`, `customer-app`, `partner-app`)
- assignee: `me` 기본 (= FE 윤성)
- relatedTo: `PRD-6422` (logger 결함 메타 이슈) — untyped grouping 영향권이면 항상 link

## 흐름

### 1. 중복 검사 (필수)

같은 Sentry 이슈가 이미 Linear 에 등록됐는지 확인.

```typescript
list_issues({ query: "MISO-NATIVE-1C", team: "Product", limit: 5 })
list_issues({ query: "<핵심 에러 메시지 키워드>", team: "Product", limit: 5 })
```

중복 발견 시: 새로 만들지 않고 기존 이슈를 업데이트하거나 사용자에게 보고.

### 2. Sentry 데이터 가져오기

shortId 만 있으면 numeric id 로 변환:

```bash
curl -s -G "https://us.sentry.io/api/0/projects/$SENTRY_ORG/$SENTRY_PROJECT/issues/" \
  -H "Authorization: Bearer $SENTRY_AUTH_TOKEN" \
  --data-urlencode "query=$SHORT_ID" --data-urlencode "limit=1"
```

latest event 상세:

```bash
curl -s "https://us.sentry.io/api/0/issues/$NUMERIC_ID/events/latest/" \
  -H "Authorization: Bearer $SENTRY_AUTH_TOKEN" -o /tmp/sentry_event.json
```

추출 항목:
- 14d events / users (issues list `count` / `userCount`)
- exception.type / value / mechanism (handled, type=onunhandledrejection 여부)
- 플랫폼 (javascript/cocoa/java/native), 릴리즈, dist
- stacktrace 최상위 in-app frame + 최하단 frame (호출처)
- 마지막 4 breadcrumbs

### 3. 우선순위 자동 추천

| 조건 | priority |
|---|---|
| `level=fatal` | **1 (Urgent)** |
| `users >= 1000` 또는 `events >= 5000` | **2 (High)** |
| `users >= 100` 또는 `events >= 500` | 3 (Medium, 기본) |
| 그 외 | 3 (Medium) |

사용자가 명시하면 그쪽 우선.

### 4. Linear 이슈 생성

```typescript
save_issue({
  title: "[<카테고리>] <한글 제목> (production X events / Y users)",
  team: "Product",
  assignee: "me",
  state: "Todo",
  priority: <자동 추천>,
  labels: ["Dev", "bug", "Sentry"],   // + 도메인 라벨
  relatedTo: ["PRD-6422"],            // untyped 영향권일 때
  description: "<아래 템플릿>"
})
```

#### description 템플릿

```markdown
## 개요

{1~2 문장 요약. production 영향 수치(events/users) 포함}

## Sentry 정보

- **이슈**: [MISO-NATIVE-XX](https://miso-ea.sentry.io/issues/{NUMERIC_ID}/)
- **에러**: `{exception.type}: {value}`
- **culprit**: `{culprit}`
- **플랫폼**: {platform} ({iOS/Android 세부}, dist={dist})
- **릴리즈**: {release}
- **14d events**: X | **users**: Y | **level**: {level} | **mechanism**: {mechanism}, handled={handled}

## 추정 원인

{1~3 문장 가설. 가능하면 코드 위치 / 관련 PRD 메모리 패턴과 연결}

## 진단 우선 작업 (수정 전 승인 필요)

1. {코드 경로 grep — 어떤 파일/함수가 호출됐는지}
2. {breadcrumbs / Sentry tag breakdown 으로 트리거 조건 확인}
3. {관련 PRD/메모리 (project_*.md) 와 비교}

수정 전 진단 결과 + 근거 + 수정 후 확인 방법 정리 → 승인 → 수정.
(CLAUDE.md "디버깅 접근 방식" 규칙)

## 작업 범위

(진단 후 정하기로 — 또는 명확하면 미리 적기)

## 관련 패키지

- `packages/...`

## 참고

- Related: PRD-6422 (logger 결함 메타) — 해당 시
- Production 분석: YYYY-MM-DD
```

### 5. 코멘트로 3명 멘션

이슈 생성 후 같은 이슈에 코멘트를 추가해 검토자에게 알림.

**3명의 Linear displayName** (mention 용):

| 역할 | 이름 | displayName | email |
|------|------|-------------|-------|
| QA | 김민지 | `qa_minji` | kimminji@getmiso.com |
| FE (assignee) | 윤성 (Yunsung Yang) | `yunsung` | yunsung@getmiso.com |
| Manager | 김경민 (Kyoungmin Kim) | `kyoungmin` | kyoungmin@getmiso.com |

```typescript
save_comment({
  issue: "<PRD-XXXX>",
  body: `Sentry 에서 보고된 production 에러로 이슈를 등록했습니다.

- @qa_minji — QA 관점 재현 / 재현 조건 확인 부탁드립니다
- @yunsung — FE 진단 / 수정 진행 (assignee)
- @kyoungmin — 우선순위 / 일정 관리 부탁드립니다

요약:
- Sentry: MISO-NATIVE-XX ({events} events / {users} users / level={level})
- 가설: {1~2 문장 가설}

상세는 이슈 description 참조.`
})
```

### 6. 결과 보고

```
✅ Sentry → Linear 이슈 생성 완료

- **ID**: PRD-XXXX
- **제목**: {title}
- **Linear URL**: {linear url}
- **Sentry**: https://miso-ea.sentry.io/issues/{NUMERIC_ID}/
- **라벨**: Sentry, Dev, bug, ...
- **우선순위**: {priority}
- **Related**: PRD-6422 (해당 시)
- **코멘트 알림**: @qa_minji, @yunsung, @kyoungmin
```

## 라벨 정책

- `Sentry` 라벨은 항상 부착 (이 라벨로 Sentry 출처 이슈 일관 분류)
- `Dev`, `bug` 기본
- 도메인:
  - 채팅/메시징: `communication`
  - customer 패키지: `customer-app`
  - partner 패키지: `partner-app`
  - 인프라/관측/빌드: `techdebt` 도 함께 고려

> 주의: `customer-app` 과 `partner-app` 은 같은 그룹이라 동시 부착 불가. 양쪽 영향이면 둘 다 빼고 description 에 명시.

## 자동 카테고리 prefix 추천

| Sentry 패턴 | prefix |
|---|---|
| Module Federation resolver / shared scope | `[크래시/MF]` |
| MF manifest / runtime fetch 실패 | `[안정성/MF]` |
| Promise unhandled rejection | `[관측/안정성]` |
| Native crash (EXC_BAD_ACCESS, NSt3) | `[네이티브 크래시]` |
| ANR / App Hang / Watchdog | `[퍼포먼스/Hang]` |
| 일반 비즈니스 로직 에러 | 도메인 prefix (`[채팅]`, `[결제]`, `[푸시]` 등) |

## 주의사항

- **trivial 1회성 에러는 만들지 말 것** — 외부 SDK 일회성 / 이미 알려진 release 회귀 / 통신 오류 등은 skip
- **중복 검증 필수** — 위 1단계 안 거치면 같은 이슈 여러 개 생성될 수 있음
- **PRD-6422 link**: untyped grouping 영향권이면 항상 `relatedTo: ["PRD-6422"]`
- **MP Product 팀 금지** — `team: "Product"` 만 사용, `MPP-` prefix 생성되면 실패로 간주 후 재생성
- **수정 코드 작성 금지** — 본 스킬은 이슈 등록까지만. 실제 수정은 별도 작업으로 진단 우선 원칙 따라 진행
- **branch 생성/체크아웃은 본 스킬 범위 밖** — 사용자가 특정 이슈에서 작업 시작할 때 별도로 진행
