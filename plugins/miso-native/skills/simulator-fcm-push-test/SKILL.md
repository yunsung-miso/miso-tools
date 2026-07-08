---
name: simulator-fcm-push-test
description: iOS 시뮬레이터에 FCM 데이터 스키마 알림을 simctl push로 보내고, 클릭 시 host→remote 라우팅(파트너/고객 화면 이동)을 로그·스크린샷으로 검증. Local(sim 번들)과 CDN/Federation(staging 배포 리모트 다운로드) 양쪽 지원
---

# Simulator FCM Push Test Skill

실제 FCM/APNS 푸시는 iOS 시뮬레이터로 올 수 없습니다 (시뮬레이터는 앱 토큰 등록 불가). 대신 `xcrun simctl push`로 **FCM data 스키마에 맞춘 로컬 알림을 흉내내어 전달**하고, 알림을 탭했을 때 푸시 클릭 라우팅(`handleNotificationPress` → `resolvePushAction` → `navigateByDeepLink*` → remote 화면 이동)이 동작하는지 검증하는 프로젝트용 스킬입니다.

순수 화면 이동만 보려면 `simulator-deeplink-test`(openurl 기반)가 더 안정적입니다. 이 스킬은 **실제 푸시 payload 모양(data 스키마)** 으로 검증하고 싶을 때 사용합니다.

## 검증 모드 — Local vs CDN(Federation)

두 모드에서 활용:

| 모드 | host가 로드하는 remote | 용도 |
|---|---|---|
| **Local** (기본 `yarn dev:ios`) | Metro가 host+remote를 한 번들로 서빙 (`@local/*` alias) | **로컬 코드 변경 즉시 검증** (워크트리/브랜치 JS가 그대로 반영) |
| **CDN/Federation** | host가 staging S3에서 **배포된 remote 번들 다운로드** | **배포본 검증 / OTA 갱신 확인** (실기기와 동일 경로) |

- 로컬 코드 fix를 빨리 보려면 → **Local 모드 Workflow**
- "배포된 staging 번들이 실제 동작하는지 / OTA 미갱신이 원인인지" 가리려면 → **CDN/Federation 모드 Workflow** (특정 buildId를 다운로드해 검증)

## Usage

```bash
/simulator-fcm-push-test
/simulator-fcm-push-test "partner MyJobsScreen"
/simulator-fcm-push-test "customer CouponView"
```

URL/대상을 명시하지 않으면 현재 작업 중인 대표 시나리오로 테스트합니다.

## FCM data 스키마 (검증된 모양)

사업부 백엔드가 보내는 일자리 추천 푸시 등과 동일한 `data` 스키마:

```json
{
  "aps": { "alert": { "title": "<제목>", "body": "<본문>" }, "sound": "default" },
  "pf_id": "@미소홈클리닝",
  "template": "20220628062829-0239",
  "isNavigate": "true",
  "destination": "MyJobsScreen",
  "app_type": "partner"
}
```

- `aps`는 iOS가 배너를 띄우기 위한 부분. **나머지 top-level 키(`app_type`/`destination`/…)가 RN Firebase의 `message.data`로 전달**됩니다 (실제 FCM에서 top-level `data`가 매핑되는 자리).
- **`app_type`은 snake_case 여야 함.** host `navigateByDeepLink.ts`가 `rawParams.app_type`만 읽습니다. `appType`(camelCase)는 인식 안 돼 `customer` 기본값으로 빠집니다.
- **`destination`은 실제 화면명** 또는 `PARTNER_ROUTE_MAP` alias.
  - BottomTab 화면: `MyJobsScreen`, `MyQuoteScreen`, `ApplyScreen`, `ChatScreen`, `ProfileScreen`
  - alias(예): `applyJobs→ApplyScreen`, `bookingDetail→RfQBookingDetail`, `userChat→MisoSendbird` (`packages/shared/src/services/navigation/deepLinkEntry.ts` `PARTNER_ROUTE_MAP`)
- `destination`이 없으면 `resolvePushAction`이 `unknown`으로 처리되어 **이동하지 않습니다** (chat 푸시는 `data.sendbird`로 별도 분기).

## Local 모드 Workflow (sim 번들)

### Step 1: 시뮬레이터 / Metro 확인

```bash
xcrun simctl list devices booted
lsof -ti:8081   # Metro
```

대상 기기 예시: `Miso iPhone 16 Pro` (UDID `D84D1279-3895-45A7-9C39-23A914B3B9B0`). 없으면 부팅 + `yarn dev:ios`로 앱 설치/Metro 기동.

### Step 2: payload(.apns) 작성

위 스키마로 `/tmp/push_<case>.apns` 작성. `app_type`/`destination`만 시나리오에 맞게 변경.

### Step 3: 앱 종료 후 push (cold-start로 최신 JS 로드)

JS 변경(라우팅 fix 등)을 반영하려면 cold-start가 안전합니다. Metro가 working tree를 서빙하므로 재빌드는 불필요(네이티브 변경 없을 때).

```bash
SIM=D84D1279-3895-45A7-9C39-23A914B3B9B0
xcrun simctl terminate "$SIM" com.miso
xcrun simctl push "$SIM" com.miso /tmp/push_<case>.apns
```

### Step 4: 알림 탭 (수동)

idb가 없으면 자동 탭이 안 됩니다. **시뮬레이터에서 배너를 직접 탭**해야 `onNotificationOpenedApp`/`getInitialNotification` → `handleNotificationPress`가 발화합니다. (탭 없이 foreground 수신은 표시만 하고 라우팅하지 않음.)

### Step 5: 라우팅 검증 (Metro 로그)

Metro 로그(`/tmp/metro.log` 또는 기동 로그)에서:

- `[PushNotificationNavigation] Notification pressed:` → 핸들러 도달
- `Navigation params found:` → `resolvePushAction` = `destination`
- `[DL-TRACE] … app_type=partner … screen=Partners` → host가 파트너로 라우팅
- `No navigation info in notification data` → `unknown` (destination/URL 없음 → 이동 안 함)

### Step 6: 화면 증거

```bash
xcrun simctl io <UDID> screenshot /tmp/fcm-push-result.png
```

파트너 탭바(내 일정/참여 중 견적/일자리 신청/대화하기/내 정보) 및 지정한 `destination` 화면으로 이동했는지 확인.

## CDN/Federation 모드 Workflow (배포 리모트 다운로드)

배포된 staging 리모트가 실제로 동작하는지 / OTA 갱신을 검증할 때. host가 staging S3에서 remote 번들을 다운로드한다 (실기기와 동일 경로).

### 1. staging env 준비

워크트리엔 `.env`가 없을 수 있음(SSM 생성, gitignore). 메인 체크아웃에서 복사:

```bash
cp <main>/packages/host/.env.staging packages/host/.env.staging
cp <main>/packages/host/.env packages/host/.env
```

`.env.staging`에 `BUILD_MODE=staging`, `BUNDLE_API_URL=https://staging-api.oneset.getmiso.com`(런타임 remote 해석용) 포함.

### 2. CDN+staging Metro 기동

```bash
cd packages/host
FEDERATION_MODE=cdn APP_ENV=staging ENVFILE=.env.staging yarn start:cdn
```

rspack 로그에서 `Partner URL: https://oneset.s3.../staging/partner/ios/mf-manifest.json` 확인.

### 3. 네이티브 재빌드 (staging env 필요)

```bash
ENVFILE=.env.staging yarn react-native run-ios --scheme 'Miso(debug)' --simulator 'Miso iPhone 16 Pro' --no-packager
```

- `react-native`는 PATH에 없음 → **`yarn` 경유 필수** (직접 호출 시 exit 127).
- `--no-packager`로 위에서 띄운 CDN Metro 사용.
- `ENVFILE=.env.staging` → `Config.BUNDLE_API_URL`이 staging으로 baked → 런타임 remote 해석이 staging 번들 API로.

### 4. remote 다운로드 확인 (런타임 로그)

```
[RemoteResolver] Backend API resolved partner -> oneset.s3.../staging/partner/ios/{hostVer}/{buildId}/mf-manifest.json (backend=true)
[InitializeFederation] Remotes registered successfully
__FEDERATION_MODE__=cdn
```

`{buildId}`가 **검증 대상 배포 번들**. 특정 배포본 확인 시 이 id를 deploy 결과와 대조 (OTA 미갱신 판별).

### 5. push 테스트

Local 모드 Step 2~6과 동일. 다운로드된 remote가 라우팅을 수행한다.

## warm 모드 재현 (직전 모드=고객 등)

실기기 버그는 "직전 모드=고객(warm)" 상태에서 파트너 push를 받는 케이스가 많다. cold-start(terminate)는 이 상태를 재현하지 못한다. warm 재현:

```bash
SIM=D84D1279-3895-45A7-9C39-23A914B3B9B0
xcrun simctl openurl "$SIM" "miso://open"   # 고객 모드 진입(warm)
# 앱 백그라운드 (Cmd+Shift+H)
osascript -e 'tell application "Simulator" to activate' \
  -e 'tell application "System Events" to key code 4 using {command down, shift down}'
xcrun simctl push "$SIM" com.miso /tmp/push_<case>.apns
# → 배너 수동 탭 → onNotificationOpenedApp (warm)
```

## deeplink vs push (fix 검증 시 주의)

- **deeplink**(`miso-partner://…`, openurl)는 `originalUrl`이 있어 `hasDeepLinkPayload` 분기를 탄다 → **`params.destination` fix 없이도 통과**.
- **raw FCM push**(`destination`만, originalUrl 없음)만 `params.destination` 게이트를 탄다.
- 따라서 **`params.destination` 관련 fix 검증은 반드시 push 경로로** 해야 한다 (deeplink로는 검증 불가).

## 라우팅 경로 (참고)

```
simctl push(.apns) → 탭 → handleNotificationPress(host)
  → resolvePushAction(data)  // destination 있으면 'destination'
  → navigateByDeepLinkParams({ destination, ...data })  // app_type(snake)로 Partners/Customers 결정
  → queueOrDispatchRoleEntryNavigation({ screen:'Partners', params:{ entryRequest } })
  → 파트너 App.tsx Effect A: params.destination → resolveDeepLinkEntryTarget → BottomTab/<destination>
```

파트너 remote는 `entryRequest.params.destination`(originalUrl 없이)도 처리해야 raw FCM 푸시가 이동합니다 (`packages/partner/src/App.tsx` Effect A 게이트가 `hasDeepLinkPayload || params.destination`).

## 한계 / Troubleshooting

- **실제 FCM 푸시는 iOS 시뮬레이터로 안 옴** (앱 토큰 등록 불가). `simctl push`는 로컬 시뮬레이션이며, RN Firebase가 simctl 푸시를 `onNotificationOpenedApp`로 항상 충실히 올린다는 보장은 없음. 핸들러 로그가 안 보이면 시뮬레이터 한계로 보고, **실기기(staging) 또는 `simulator-deeplink-test`(openurl)** 로 대체 검증.
- **탭해도 customer로 감** → `app_type`이 `appType`(camel)이거나 누락. snake_case로.
- **파트너로는 갔는데 기본 화면(ApplyScreen)에 머묾** → `destination` 미반영. destination 값이 화면명/alias와 일치하는지, 파트너 App.tsx 게이트가 `params.destination`을 처리하는지 확인.
- **JS 변경이 반영 안 됨** → (Local) 앱 terminate 후 재실행(cold-start)으로 Metro 최신 번들 로드.
- **배포본인데 실기기에서만 실패** → (CDN) 다운로드 로그의 `{buildId}`를 deploy 결과와 대조. 이전 id면 **OTA 미갱신**(앱 강제 종료→재실행으로 갱신). CDN 모드 sim 테스트가 정상이면 배포본은 정상 → 실기기 OTA 갱신 문제로 좁혀짐.

## Output Expectation

최종 보고 시:

- 사용한 FCM data 스키마(payload)
- 시뮬레이터/Metro 상태
- 라우팅 로그 발췌(`Notification pressed` / `Navigation params found` / `DL-TRACE`)
- 결과 화면 스크린샷 경로
- 실기기/딥링크 대체 검증 필요 여부
