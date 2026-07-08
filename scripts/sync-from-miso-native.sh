#!/usr/bin/env bash
# miso-native 레포의 .claude 스킬/훅을 이 팩의 miso-native 플러그인으로 단방향 미러한다.
# 원천 = miso-native 레포(팀 공유). 팩 = 복사본. 역류 금지.
# 사용: scripts/sync-from-miso-native.sh [MISO_NATIVE_PATH]
set -euo pipefail

MISO_NATIVE="${1:-$HOME/Documents/miso_workspace/miso-native}"
PACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$PACK_DIR/plugins/miso-native"

src_skills="$MISO_NATIVE/.claude/skills"
src_e2e="$MISO_NATIVE/.claude/hooks/e2e-harness-guard.sh"

[ -d "$src_skills" ] || { echo "[sync] miso-native skills 디렉터리 없음: $src_skills" >&2; exit 1; }

# 스킬 미러 — 대상 비우고 재복사(원천에서 삭제된 스킬 반영)
rm -rf "$DEST/skills"
mkdir -p "$DEST/skills"
cp -R "$src_skills"/. "$DEST/skills/"

# 훅은 e2e-harness-guard.sh 만 미러. lsp-first-bootstrap.sh 는 guardrails 플러그인이 제공하므로 제외.
mkdir -p "$DEST/hooks"
[ -f "$src_e2e" ] && cp "$src_e2e" "$DEST/hooks/e2e-harness-guard.sh"

# 검증 — SKILL.md 개수 원천==대상
src_n=$(find "$src_skills" -name SKILL.md | wc -l | tr -d ' ')
dst_n=$(find "$DEST/skills" -name SKILL.md | wc -l | tr -d ' ')
if [ "$src_n" != "$dst_n" ]; then
  echo "[sync] SKILL.md 개수 불일치: 원천=$src_n 대상=$dst_n" >&2
  exit 1
fi
echo "[sync] 완료 — miso-native 스킬 ${dst_n}개 + e2e 훅 미러 → $DEST"
