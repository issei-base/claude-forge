#!/usr/bin/env bash
# storage-cleanup: read-only storage scanner.
#
# Prints a disk baseline, the biggest consumers under $HOME, and sized cleanup
# candidates grouped by safety tier, plus which owning apps are currently
# running (their caches must be skipped). It NEVER deletes anything — deletion
# is driven by SKILL.md Phase 3 with explicit confirmation.
#
# Usage: bash scan_storage.sh
set -uo pipefail

H="$HOME"
hr() { printf '%s\n' "------------------------------------------------------------"; }
# size of a path; prints "-" if it does not exist
sz() { [ -e "$1" ] && du -sh "$1" 2>/dev/null | cut -f1 || echo "-"; }
row() { [ -e "$1" ] && printf '%8s  %s\n' "$(du -sh "$1" 2>/dev/null | cut -f1)" "$1"; }

echo "# storage-cleanup scan (read-only)"
echo

echo "## ディスク使用量 (baseline)"
df -h / /System/Volumes/Data 2>/dev/null
hr

echo "## ホーム直下の大きいもの (top 15)"
du -sh "$H"/* 2>/dev/null | sort -rh | head -15
echo
echo "## ドットディレクトリの大きいもの (top 15)"
# .[!.]* matches dotfiles but skips "." and ".." (which would report the whole home)
du -sh "$H"/.[!.]* 2>/dev/null | sort -rh | head -15
hr

echo "## Tier 1 候補 — 再生成されるキャッシュ / ビルド成果物 / 更新残骸 (安全に即削除)"
echo "   ※ 所有アプリが起動中の Caches は下の RUNNING を見て skip すること"
for p in \
  "$H/Library/Developer/Xcode/DerivedData" \
  "$H/Library/Developer/Xcode/iOS DeviceSupport" \
  "$H/Library/Caches/claude-cli-nodejs" \
  "$H/Library/Caches/com.openai.codex" \
  "$H/Library/Caches/Google" \
  "$H/Library/Caches/ms-playwright" \
  "$H/Library/Caches/Homebrew" \
  "$H/Library/Caches/com.microsoft.VSCode.ShipIt" \
  "$H/Library/Caches/notion.id.ShipIt" \
  "$H/.npm/_cacache" \
  "$H/.cache" \
; do row "$p"; done
hr

echo "## Tier 2 候補 — 条件付き (再DL / 再作成 / 機能未使用が前提。影響を説明してから)"
for p in \
  "$H/Library/Application Support/Claude/vm_bundles" \
  "$H/Library/Developer/CoreSimulator/Devices" \
  "$H/Library/Containers/com.docker.docker/Data/vms" \
; do row "$p"; done
hr

echo "## 起動中アプリ (この一覧に出たアプリの Caches/* は今回 skip する)"
found=0
for app in "Google Chrome" "Code Helper" "Notion" "Codex" "com.docker" "Slack" "Xcode" "obsidian"; do
  if pgrep -lf "$app" >/dev/null 2>&1; then echo "  RUNNING: $app"; found=1; fi
done
[ "$found" = 0 ] && echo "  (該当なし — Caches は概ね安全に削除できる)"
hr

echo "## 削除可能な古いシミュレータ (simctl unavailable)"
out="$(xcrun simctl list devices 2>/dev/null | grep -i unavailable | head)"
[ -n "$out" ] && echo "$out" || echo "  (なし — 'xcrun simctl delete unavailable' で消せるものは無い)"
hr

echo "scan 完了。削除は SKILL.md の Phase 2 (安全確認) → Phase 3 (削除) に従い、"
echo "対象パスを逐語で確認してから実行する。このスクリプトは何も削除していない。"
