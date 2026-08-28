---
name: slack-my-commitments
description: Slack 채널(기본 #development)에서 내가 "제가 가져갈게요 / 하겠습니다 / 넵!" 같이 처리하겠다고 말한 건들을 최근 N주치 모아, 스레드 부모의 Linear 티켓을 붙이고 현재 상태·SLA 까지 확인해 미착수 목록을 만든다. "내가 처리한다고 한 이슈 모아줘", "슬랙에서 내가 맡은 거 밀린 거 정리", "development 채널 내 약속 확인", "commitment 백로그" 같은 요청에 사용.
---

# Slack My Commitments Skill

바빠서 못 챙긴 사이, Slack 스레드에서 "제가 가져갈게요" 하고 흘려보낸 건들을 회수한다.
산출물은 **티켓 + 내 발언 + 현재 Linear 상태** 표 하나.

## 입력

| 인자 | 기본값 | 비고 |
|---|---|---|
| 채널 | `#development` | 다른 채널명/ID 지정 가능 |
| 기간 | 최근 3주 | "근 한 달", "8월 이후" 등 자유 표현 → 날짜로 환산 |
| 대상자 | 나 | `slack_search_public` 도구 설명에 박혀 있는 current logged in user id 사용 |

채널 ID 는 `slack_search_channels` 로 이름 → ID 변환 (예: `#development` = `C095XL48J`).
사용자 ID 는 도구 설명의 "Current logged in user's user_id" 를 그대로 쓴다 — 추측 금지.

## 절차

### 1. 내 메시지 스캔 (토큰 절약이 핵심)

```
slack_search_public(
  query: "from:<@{USER_ID}> in:<#{CHANNEL_ID}> after:{YYYY-MM-DD}",
  sort: "timestamp", sort_dir: "desc",
  include_context: false,          # 필수
  response_format: "concise",      # 필수
  limit: 20
)
```

- `include_context: true` 로 부르면 스레드 전체 맥락이 결과마다 붙어 **한 번에 수만 토큰**이 날아간다. 스캔 패스는 무조건 `false` + `concise`.
- 한 페이지 최대 20건. `pagination_info` 의 cursor 로 끝까지 넘긴다.
- **누락 검증**: 결과에 날짜 공백 구간이 보이면 그 구간만 `after:`/`before:` 로 좁혀 재조회해서, 진짜 무발언인지 검색 캡에 잘린 건지 확인한다. (휴가 주간이면 진짜 0건일 수 있다.)

### 2. 커밋먼트 발언 골라내기

내가 "내가 한다"고 말한 것만 남긴다. 실제로 관측된 표현들:

| 유형 | 예시 | 판정 |
|---|---|---|
| 직접 선언 | "제가 가져갈게용", "제가 할게요", "~하겠습니다", "제가 해봐도 되죠?" | ✅ 커밋먼트 |
| 지목에 대한 수락 | 상대가 "윤성님이 출격하실까요" / "확인 부탁드립니다" → 내 답이 "넵!" | ✅ 커밋먼트 (부모 확인 필수) |
| 진단·설명만 | "스테이징에서 나는 문제인거죠?", 원인 분석 코멘트 | ❌ 제외 |
| 타인에게 위임 | "~해보세용", "IB 팀에서 해결해보셔도" | ❌ 제외 |
| 의견·잡담 | "ㅋㅋㅋㅋ", "아하 문서가 오래되었나보군요" | ❌ 제외 |

`넵!` / `네` 같은 한 마디 수락은 **본문만 보면 판정 불가**하다. 반드시 `slack_read_thread` 로 부모 + 직전 발언을 읽어 "누가 나에게 무엇을 요청했는가"를 확인한 뒤 판정한다.

### 3. 스레드 부모 → 티켓 ID

```
slack_read_thread(channel_id, message_ts: {thread_ts}, limit: 6, response_format: "concise")
```

- `thread_ts` 는 1번 결과의 permalink 쿼리스트링(`?thread_ts=...`)에 들어 있다.
- 부모가 `Linear Asks` 봇 메시지면 본문 URL 에서 티켓 ID(`MIS-4029` 등)를 뽑는다.
- 부모에 티켓이 없으면(순수 대화 스레드) 티켓 없이 "슬랙 전용 약속"으로 따로 분류한다.

### 4. Linear 현재 상태 확인

`mcp__linear-server__get_issue` 를 티켓 수만큼 **한 응답에서 병렬 호출**한다.

읽을 필드:

| 필드 | 의미 |
|---|---|
| `status` / `statusType` | `Triage`·`Backlog` = 미착수, `started` = 진행중, `completed` = 완료 |
| `assignee` (없으면 미배정) | 응답에 키 자체가 없으면 담당자 없음 |
| `startedAt` / `completedAt` | null 이면 손도 안 댄 것 |
| `slaBreachesAt` | 현재 시각보다 과거면 **SLA breach** — 우선순위 최상단 |
| `updatedAt` | 마지막 움직임 |

### 5. 보고

기본은 터미널 표 하나. 컬럼: 날짜 / 티켓 / 내용 요약 / 내 발언 원문 / 현재 상태.

- **정렬**: 오래 묵은 순 (발언일 오름차순). SLA breach 는 별도 표시.
- 표 아래 2~3줄로: 가장 오래 묵은 건, 작업 범위가 큰 건, SLA 넘긴 건.
- **제외한 건도 한 줄로 보고** — "MIS-4031·MIS-4035 는 다른 사람이 가져감, MIS-4037 은 진단만 하고 코드 수정 없음". 왜 목록에 없는지 사용자가 되묻지 않게.
- 티켓 URL 은 `https://linear.app/miso/issue/{ID}` 로 링크한다.

## 가드레일

- **읽기 전용**. 티켓 상태 변경·assign·슬랙 답글은 이 스킬 범위 밖이다. 사용자가 따로 시키면 그때 한다.
- 커밋먼트 판정은 **원문 근거**로만 한다. "아마 이것도 맡았을 것" 추측 금지 — 애매하면 별도 "판정 애매" 섹션에 원문 그대로 올리고 사용자에게 묻는다.
- Slack 검색 결과는 캡이 걸릴 수 있다. 페이지가 갑자기 끊기면 날짜 구간을 쪼개 재검증한 뒤 "N건 전수"라고 말한다.
- 스캔 패스에서 `include_context: true` 를 쓰지 않는다 (위 1번 사유).

## 참고

- 첫 사용 (2026-08-28): #development 3주치(8/7~8/28) 25개 메시지 → 커밋먼트 6건(MIS-4033·4029·4030·4027·4023·3999) 적발, 전부 Triage·미배정·미착수. MIS-3999 는 18일 방치 + SLA breach.
- 자주 걸리는 함정: 온보딩/UI 버그처럼 한 스레드에 `<!subteam^...>` 멘션만 오고 내가 "제가가져갈게용" 한 줄 남기는 패턴 — 티켓에는 아무 흔적이 안 남아서 슬랙에서만 잡힌다.
- 관련 스킬: 회수한 티켓을 실제로 정리할 때는 `release-tickets-done`(miso-native) 이 아니라 개별 처리. 주간 보고에 넣을 땐 `notion-weekly-report`.
