#!/usr/bin/env bash
# SessionStart hook — linked git worktree 에서 세션이 시작될 때 host .env.staging 이 없으면
# 정식 생성 스크립트(pnpm env:staging → packages/host/scripts/getEnv.sh)로 SSM 에서 생성한다.
#
# 왜: 워크트리 fresh checkout 에는 .env*(gitignore + SSM 로 생성되는 파일) 가 없다. 그 상태로
# iOS 를 빌드하면 react-native-config 의 Config 가 undefined 가 되어 런타임에 "Network request
# failed" 로 죽는다. cp(메인 복사)는 stale 위험 + 사용자 요구가 아님 — 정식 생성 스크립트를 호출한다.
#
# 이미 .env.staging 이 있으면 skip(워크트리 로컬 토글 보존). SSM/네트워크 미가용 시 비치명적(exit 0).
set -euo pipefail

top=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
common=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || exit 0
main_root=$(dirname "$common")
[ "$main_root" = "$top" ] && exit 0          # main checkout → no-op
[ -f "$top/packages/host/.env.staging" ] && exit 0   # 이미 있으면 skip
command -v pnpm >/dev/null 2>&1 || exit 0
[ -f "$top/packages/host/scripts/getEnv.sh" ] || exit 0

cd "$top" || exit 0
echo "[sync-worktree-env] worktree host .env.staging 없음 → pnpm env:staging 생성 중…" >&2
if pnpm env:staging >&2 2>&1; then
  echo "[sync-worktree-env] .env.staging 생성 완료" >&2
else
  echo "[sync-worktree-env] pnpm env:staging 실패 — SSM/AWS 자격 또는 네트워크 확인 후 수동 실행: pnpm env:staging" >&2
fi
exit 0
