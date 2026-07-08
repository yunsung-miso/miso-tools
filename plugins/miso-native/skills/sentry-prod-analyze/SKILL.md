---
name: sentry-prod-analyze
description: Production Sentry 에러를 4축(빈도/사용자영향/신규/심각도)으로 리스트업하고 자동 분류 + 종합 보고서 markdown 작성. "sentry 분석", "production 에러 분석", "센트리 에러 리스트업" 같은 요청에 사용.
---

# Sentry Production 에러 분석 스킬

`miso-ea/miso-native` Sentry 에서 production 환경의 에러를 4축으로 수집·집계해 보고서를 작성한다. Sentry MCP `search_issues` 가 막혀있을 때도 동작 (REST API 직접 호출).

## 전제 조건

`~/.zshenv` 에 다음이 export 되어 있어야 함. Bash tool 의 non-interactive zsh 가 `.zshenv` 를 자동 로드하므로 명령어에 토큰을 인라인으로 박지 않는다.

- `SENTRY_AUTH_TOKEN` (`sntryu_` user token, 또는 `sntrys_` org token)
- `SENTRY_ORG=miso-ea`
- `SENTRY_PROJECT=miso-native`
- `SENTRY_URL=https://us.sentry.io/`

검증:

```bash
[ -n "$SENTRY_AUTH_TOKEN" ] && echo "✅ token loaded (len=${#SENTRY_AUTH_TOKEN})" || echo "❌ token missing"
```

## 분석 절차

### 1. 4축 데이터 병렬 수집

`statsPeriod` 는 이 프로젝트 retention 상 `''`, `24h`, `14d` 만 허용. 기본 `14d`.

```bash
api="https://us.sentry.io/api/0/projects/$SENTRY_ORG/$SENTRY_PROJECT/issues/"
auth="Authorization: Bearer $SENTRY_AUTH_TOKEN"
period="${PERIOD:-14d}"

# freq
curl -s -G "$api" -H "$auth" \
  --data-urlencode "query=is:unresolved environment:production" \
  --data-urlencode "sort=freq" --data-urlencode "statsPeriod=$period" \
  --data-urlencode "limit=100" -o /tmp/sentry_freq.json -w "freq HTTP %{http_code}\n"

# user impact
curl -s -G "$api" -H "$auth" \
  --data-urlencode "query=is:unresolved environment:production" \
  --data-urlencode "sort=user" --data-urlencode "statsPeriod=$period" \
  --data-urlencode "limit=50" -o /tmp/sentry_user.json -w "user HTTP %{http_code}\n"

# new (firstSeen 최근)
curl -s -G "$api" -H "$auth" \
  --data-urlencode "query=is:unresolved environment:production" \
  --data-urlencode "sort=new" --data-urlencode "statsPeriod=$period" \
  --data-urlencode "limit=30" -o /tmp/sentry_new.json -w "new HTTP %{http_code}\n"

# fatal
curl -s -G "$api" -H "$auth" \
  --data-urlencode "query=is:unresolved environment:production level:fatal" \
  --data-urlencode "sort=freq" --data-urlencode "statsPeriod=$period" \
  --data-urlencode "limit=30" -o /tmp/sentry_fatal.json -w "fatal HTTP %{http_code}\n"
```

### 2. python3 자동 집계

```python
import json
from collections import Counter

def load(p):
    with open(p) as f:
        return json.load(f)

def pull(i):
    md = i.get('metadata') or {}
    return dict(
        id=i.get('shortId'),
        title=(i.get('title') or '').replace('\n', ' ')[:140],
        culprit=(i.get('culprit') or '')[:90],
        count=int(i.get('count') or 0),
        users=int(i.get('userCount') or 0),
        level=i.get('level'),
        type=md.get('type') or '',
        platform=i.get('platform'),
        firstSeen=(i.get('firstSeen') or '')[:10],
        lastSeen=(i.get('lastSeen') or '')[:10],
        isUnhandled=i.get('isUnhandled'),
        release=(i.get('lastRelease') or {}).get('version', ''),
    )

freq = [pull(x) for x in load('/tmp/sentry_freq.json')]
users = [pull(x) for x in load('/tmp/sentry_user.json')]
new_ = [pull(x) for x in load('/tmp/sentry_new.json')]
fatal = [pull(x) for x in load('/tmp/sentry_fatal.json')]

# 분포 — type / level / platform / lastRelease
# Top 20 by freq, Top 15 by users, 신규 등장 15, Fatal 전체
```

### 3. 개별 이슈 deep-dive (옵션)

`untyped` 그룹의 진짜 원인은 latest event 의 stacktrace + breadcrumbs 를 봐야 한다. shortId 의 numeric id 는 freq/user/new/fatal json 의 `id` 필드.

```bash
curl -s "https://us.sentry.io/api/0/issues/$NUMERIC_ID/events/latest/" \
  -H "Authorization: Bearer $SENTRY_AUTH_TOKEN" -o /tmp/sentry_event.json
```

확인할 필드:
- `entries[type=exception].data.values[].type/value/mechanism` — typing 결함 여부
- `entries[type=exception].data.values[].stacktrace.frames[]` — 최하단 frame 이 실제 호출처. `packages/shared/src/utils/logger.ts:118 in error` 가 보이면 PRD-6422 패턴
- `entries[type=breadcrumbs].data.values[-4:]` — 사건 직전 흐름
- `tags[].key=='dist'`, `release` — 플랫폼/릴리즈 어트리뷰션

### 3.5. 그룹 events 분포 검증 (분류/archive/이슈화 직전 필수)

Sentry 의 group fingerprint 는 throwing 위치 기준이라 같은 그룹에 **여러 sub-pattern 메시지** 가 묶일 수 있다. issues 리스트의 `metadata.value` 는 sample 1건만 보여줘서 이것만 보고 분류하면 다수 sub-pattern 이 묻힌다 (PRD-6466 → PRD-6467 사례: archive 한 그룹이 96% 코드 버그였음).

**분류/archive/Linear 이슈화 직전에는 그룹 events 100건 분포 확인:**

```bash
curl -s -G "https://us.sentry.io/api/0/issues/$NUMERIC_ID/events/" \
  -H "Authorization: Bearer $SENTRY_AUTH_TOKEN" \
  --data-urlencode "full=false" --data-urlencode "limit=100" \
  -o /tmp/sentry_group_events.json
```

```python
from collections import Counter
import json
events = json.load(open('/tmp/sentry_group_events.json'))
print(Counter(e.get('metadata',{}).get('value','')[:60] for e in events).most_common(10))
print(Counter(t['value'] for e in events for t in e.get('tags',[]) if t['key']=='os.name').most_common())
```

- sample value 와 분포 다수가 다르면 분류 재고
- 특히 환경 의존 vs 코드 버그 분류에서 critical — sub-pattern 비율로 결정
- 관련 메모리: feedback_sentry_group_distribution_check, feedback_env_error_vs_bug_classification

## 보고서 구조

```markdown
# Production 에러 분석 보고서 (miso-native, last {period}, {YYYY-MM-DD})

## 한 줄 요약
상위 N 그룹에서 X events / Y users. 주요 분포: ...

## 분포 집계
- Exception Type (type/null 비율 — null 비율 높으면 PRD-6422 패턴 의심)
- Level (error/fatal)
- Platform (javascript/cocoa/java/native)
- lastRelease (null 100% 면 deploy event 미등록)

## Top 20 by frequency · Top 15 by user impact · 신규 등장 15 · Fatal 전체
(표)

## 카테고리별 종합
- A. Module Federation 인프라 (resolver / manifest / DNS)
- B. 처리 안 된 Promise rejection (mechanism=onunhandledrejection)
- C. 네트워크 실패 (Network request failed / Timeout)
- D. Native crash / ANR / Hang
- E. 신규 등장 회귀 (firstSeen=오늘)

## 메타 발견 (관측 인프라 결함)

## 우선순위 제안 (P0~P3)
```

## 패턴 인식 가이드

| 시그널 | 의심 원인 | 관련 |
|---|---|---|
| `exception.type=null`, `title="error"`/`"<object>.error"`/`"anonymous"` 다수 | logger.error 캡쳐 결함 — args 손실로 grouping 실패 | PRD-6422 |
| `mechanism=onunhandledrejection`, `handled=true` | 호출처 `.catch()` 누락 | PRD-6451 |
| `Error: No resolver was able to resolve script ...` | MF shared scope 정합성 결함 (host-remote) | PRD-6424, PRD-6450 |
| `Failed to get manifest #RUNTIME-003` / S3 DNS / Fetch timeout | MF runtime cold-start 차단 | PRD-6452 |
| `lastRelease=null` 100% | Sentry deploy event 미등록 — release health 미작동 | PRD-6387 후속 |
| dist 가 platform-buildNumber 형태가 아님 | release attribution 컨벤션 미준수 | PRD-6387 |
| Android Background ANR / iOS WatchdogTermination | main thread 블로킹 | profiling 필요 |

## 사용 흐름

1. 위 4축 curl 실행 → `/tmp/sentry_*.json` 생성
2. python3 집계 + 표 출력
3. (필요 시) 상위 N개 이슈 deep-dive
4. 보고서 markdown 작성 (사용자에게 출력)
5. 후속 작업: 발견된 이슈를 [sentry-issue-create](../sentry-issue-create/SKILL.md) 스킬로 Linear 등록

## 주의사항

- 결과는 retention 14d 한정 — 그 이상 기간은 데이터 없음
- `MCP search_issues` 가 작동하면 그쪽이 더 편하나, 본 스킬은 MCP 막혀도 동작
- 토큰이 채팅에 평문 노출되지 않도록 명령어에 inline 박지 않고 `$SENTRY_AUTH_TOKEN` 환경변수로만 참조
