---
name: simulator-deeplink-test
description: iOS 시뮬레이터에서 앱을 재빌드하고 딥링크를 실행해 화면 증거까지 확인
---

# Simulator Deeplink Test Skill

React Native iOS 앱을 시뮬레이터에 다시 설치한 뒤 deeplink를 실행하고, 결과 화면을 스크린샷으로 남기는 프로젝트용 스킬입니다.

## Usage

```bash
/simulator-deeplink-test
/simulator-deeplink-test "https://miso.app/customer?isCoupon=true&type=newcomer&promocode=TEST123&code=TEST123&destination=CouponView"
```

사용자가 URL을 명시하지 않으면 현재 작업 중인 대표 deeplink 시나리오를 기준으로 테스트합니다.

## Workflow

### Step 1: 시뮬레이터 확인

```bash
xcrun simctl list devices booted
```

기본 대상 기기 예시:

- `PRD-5940-iPhone-16`
- UDID: `2A59C000-8AEB-40EB-99F6-E6C3D28912D3`

없으면 부팅:

```bash
xcrun simctl boot "<UDID or device name>"
open -a Simulator --args -CurrentDeviceUDID <UDID>
```

### Step 2: 필요 시 비인증 상태 초기화

비인증 케이스를 확인할 때만 사용:

```bash
xcrun simctl shutdown <UDID>
xcrun simctl erase <UDID>
xcrun simctl boot <UDID>
open -a Simulator --args -CurrentDeviceUDID <UDID>
```

### Step 3: 로컬 remote 서버 확인

customer/auth remote가 필요한 경우 포트 확인:

```bash
lsof -i tcp:9001 -i tcp:9003
```

필요 시 실행:

```bash
nohup yarn customer start > /tmp/customer-deeplink.log 2>&1 &
nohup yarn auth start > /tmp/auth-deeplink.log 2>&1 &
```

### Step 4: 앱 재빌드/재설치 (필요할 때만)

매번 리빌드하지 않습니다.

**리빌드가 필요한 경우**

- host/native 코드가 바뀐 경우
- iOS 설정/Pods/브리징 변경이 있는 경우
- 시뮬레이터를 `erase` 해서 앱이 지워진 경우

**리빌드가 불필요한 경우**

- customer/auth remote 같은 JS 변경만 있는 경우
- 이미 같은 host shell이 떠 있고 remote 서버만 최신으로 다시 컴파일하면 되는 경우

```bash
cd packages/host
npx react-native run-ios --scheme "Miso(debug)" --udid <UDID> --no-packager
```

### Step 5: deeplink 실행

예시:

```bash
xcrun simctl openurl <UDID> "miso://open?destination=Home"
xcrun simctl openurl <UDID> "https://miso.app/customer/home"
xcrun simctl openurl <UDID> "https://miso.app/customer?isCoupon=true&type=newcomer&promocode=TEST123&code=TEST123&destination=CouponView"
```

실행 후 3~5초 대기:

```bash
python3 - <<'PY'
import time
time.sleep(5)
PY
```

### Step 6: 화면 증거 수집

```bash
xcrun simctl io <UDID> screenshot "/tmp/deeplink-result.png"
```

판독 기준:

- Auth 진입인지
- Home 진입인지
- CouponView 진입인지
- alert / bottom sheet가 있는지

### Step 7: 첫 실행 권한 팝업 확인

fresh simulator에서는 알림 권한 팝업이 deeplink 결과를 가릴 수 있습니다.

예시 텍스트:

- `‘미소(staging)’에서 알림을 보내고자 합니다.`
- 버튼: `허용 안 함`, `허용`

이 경우 deeplink 실패로 판단하지 말고, **권한 팝업을 먼저 처리한 뒤 같은 deeplink를 다시 실행**합니다.

## Recommended Assertions

### 공개 화면 deeplink

- Home deeplink는 Auth 없이 Home 화면으로 진입해야 함

### 보호 화면 deeplink

- 미인증 상태면 Auth 화면으로 먼저 진입해야 함

### CouponView deeplink

- 미인증: `이동 → 인증 확인 → Auth`
- 인증 후: `이동 → CouponView → 화면 포커스 안정화 이후 발급`
- 같은 pending coupon payload로 반복 발급 루프가 없어야 함

## Troubleshooting

- **딥링크 실행 후 홈에 남음**
  - 현재 인증 상태/remote 서버 상태/URL 형태를 다시 확인
  - custom scheme와 canonical customer URL을 각각 비교

- **권한 팝업이 결과를 가림**
  - first-launch 알림 권한 팝업인지 먼저 확인
  - 팝업 처리 후 동일 deeplink를 재실행

- **시뮬레이터 빌드 실패**
  - `DerivedData` / `ModuleCache.noindex` 정리 후 재시도
  - `packages/host/ios`의 CocoaPods 상태 확인

- **remote 최신 코드 반영 안 됨**
  - customer/auth 서버 재시작 후 iOS compile 완료 로그 확인

## Output Expectation

최종 보고 시 아래를 포함합니다:

- 사용한 deeplink URL
- 시뮬레이터 상태(booted/erased 여부)
- 결과 화면 요약
- 스크린샷 경로
- 필요 시 다음 디버깅 포인트
