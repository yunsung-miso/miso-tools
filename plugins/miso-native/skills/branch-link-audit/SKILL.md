---
name: branch-link-audit
description: Branch.io 운영 딥링크 전수 조사. 구글 시트 덤프나 대시보드 export CSV에서 링크 목록을 뽑아 링크별 설정(campaign/channel/딥링크 data/웹 fallback URL)을 Branch Public API로 수집하고 분석 리포트를 만든다. "딥링크 전수조사", "브랜치 링크 감사", "운영 딥링크 어디로 연결되는지 정리" 같은 요청에 사용.
---

# Branch 딥링크 전수 조사

Branch Public API에는 링크 목록(list) 엔드포인트가 없다. 목록은 시트/대시보드 export로 받고,
링크별 설정은 `GET /v1/url` 로 조회한다 (읽기는 branch_key만 필요, secret 불필요).

## 절차

1. **링크 목록 확보** — 세 가지 소스 중 하나:
   - **구글 시트** (마케팅팀이 관리하는 링크 시트가 정본): Google Drive MCP `search_files`
     → `read_file_content`로 시트 덤프. 큰 시트는 tool-results 파일로 저장됨. 그 파일을
     `--regex` 모드로 넘기면 Branch 링크만 정규식 추출(시트의 다른 텍스트·외부 문서 링크는 자동 제외).
   - Branch 대시보드 → Links(Link Manager) → Export CSV.
   - txt (한 줄당 URL 하나).

2. **branch_key 확보 + 판별**
   - miso-native `packages/host/.env` 의 `CUSTOMER_BRANCH_KEY` / `PARTNER_BRANCH_KEY`.
   - **`get.miso.kr` / `miso.app.link` (production customer 링크) = `CUSTOMER_BRANCH_KEY`(key_live_cdiL…)로 조회됨.**
     `.env` 프리픽스가 `get-staging`이라 staging 키처럼 보이지만, 이 키가 production 링크의 소유 키다.
     대시보드 웹SDK에 노출되는 `key_live_jpc4…`는 오히려 403.
   - 판별법: 실제 링크 1개를 후보 키로 조회 → 403이면 틀린 키, 데이터 나오면 맞는 키.
   - 키를 채팅에 그대로 출력하지 말 것.

3. **수집 실행** — 스크립트는 이 스킬의 base directory 기준 `scripts/audit_links.py`.

   ```bash
   # 구글 시트 덤프에서:
   python3 <skill-base>/scripts/audit_links.py \
     <sheet_dump.txt> --regex --branch-key <key> --out <scratchpad>/branch-audit

   # CSV/txt 목록에서:
   python3 <skill-base>/scripts/audit_links.py \
     <export.csv> --branch-key <key> --out <scratchpad>/branch-audit
   ```

   - `--extract-only`: 조회 없이 추출된 unique URL만 출력 (개수·목록 확인용).
   - CSV의 URL 컬럼은 자동 탐지("link"/"url" 포함 헤더). 실패 시 `--column` 지정.
   - 출력: `report.csv`(주요 필드 표) + `raw.jsonl`(응답 원문).
   - **RTK 주의**: 이 스크립트는 urllib라 RTK를 우회한다. `curl`로 직접 GET하면 RTK가
     JSON을 타입 스키마로 압축해 실제 값이 안 보이니, 조회는 반드시 이 스크립트로.

4. **분석 리포트 작성** — `report.csv`의 주요 필드를 집계해 정리:
   - `destination` (앱 내 라우팅 화면: AIBooking/IntegratedChat/CampaignIntro/BookingPackage 등) 분포
   - `serviceCode` (서비스 종류) 분포
   - `$desktop_url`/`$ios_url`/`$android_url` (웹/앱 목적지) 도메인 분포. 앱 딥링크는 ios/android가
     비어있고 `destination`+`serviceCode`로 인앱 라우팅하는 게 정상 — $*_url은 미설치 시 웹 fallback.
   - campaign/channel/feature 분포, custom_data 키 종류별 개수
   - 이상 징후: 목록엔 있으나 Branch 404(미생성/삭제), `front-staging`·`get-staging` 등 비-prod 목적지,
     fallback 비어있는 링크
   - 링크 수가 많으면 전체 표는 파일로 두고 요약만 답변에 담는다.

## 수정이 필요할 때

조회 결과를 근거로 수정 대상이 정해지면 `PUT /v1/url` 사용 — 이때는 `branch_secret` 필요
(paramstore/대시보드에서 확보). 수정은 되돌리기 어려우므로 반드시 사용자 확인 후 실행.

## 제약

- 공식 Branch MCP는 closed beta + 분석 조회 전용이라 링크 CRUD에 못 쓴다.
- rate limit 100 req/s — 스크립트는 요청당 50ms 대기라 여유.
