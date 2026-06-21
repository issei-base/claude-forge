#!/usr/bin/env bash
# storage-cleanup: read-only storage scanner.
#
# Prints a disk baseline, the biggest consumers under $HOME (home dirs, dot
# dirs, Application Support), sized cleanup candidates grouped by safety tier,
# Electron app cache vs persistent-store subdirs, and which owning apps are
# currently running (main process, not helpers). It NEVER deletes anything —
# deletion is driven by SKILL.md Phase 3 with explicit confirmation.
#
# Usage: bash scan_storage.sh
set -uo pipefail

H="$HOME"
hr() { printf '%s\n' "------------------------------------------------------------"; }
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
echo
echo "## Application Support の大きいもの (top 12)"
echo "   ※ 親は実データ。1G 超は 'du -sh <dir>/*' で一段掘り、cache サブディレクトリだけ候補にする"
du -sh "$H/Library/Application Support"/* 2>/dev/null | sort -rh | head -12
hr

echo "## Tier 1 候補 — 再生成されるキャッシュ / ビルド成果物 / 更新残骸 (安全に即削除)"
echo "   ※ 所有アプリ本体が起動中の Caches は下の RUNNING を見て skip すること"
for p in \
  "$H/Library/Developer/Xcode/DerivedData" \
  "$H/Library/Developer/Xcode/iOS DeviceSupport" \
  "$H/Library/Caches/claude-cli-nodejs" \
  "$H/Library/Caches/com.openai.codex" \
  "$H/Library/Caches/Google" \
  "$H/Library/Caches/ms-playwright" \
  "$H/Library/Caches/Homebrew" \
  "$H/Library/Caches/CocoaPods" \
  "$H/Library/Caches/node-gyp" \
  "$H/Library/Caches/com.microsoft.VSCode.ShipIt" \
  "$H/Library/Caches/notion.id.ShipIt" \
  "$H/.npm/_cacache" \
  "$H/.npm/_logs" \
  "$H/.npm/_npx" \
  "$H/.expo/ios-simulator-app-cache" \
  "$H/.expo/expo-go" \
  "$H/.cache" \
; do row "$p"; done
hr

echo "## Electron アプリの cache サブディレクトリ (本体非起動なら Tier 1・アプリが再生成)"
echo "   ※ 同じ階層の User / Local Storage / IndexedDB は設定・状態なので消さない"
echo "   ※ maxdepth 4 まで掘る。ただし Partitions 配下の Cache は Tier2(Partitions 本体)で計上するので除外し、回収見込み合計の二重計上を防ぐ"
find "$H/Library/Application Support" -maxdepth 4 -type d \
  -path "*/Partitions/*" -prune -o -type d \
  \( -name "Cache" -o -name "Code Cache" -o -name "GPUCache" -o -name "CachedData" -o -name "CachedExtensionVSIXs" \) \
  -prune -print 2>/dev/null | while IFS= read -r d; do row "$d"; done | sort -rh | head -15
hr

echo "## Tier 2 候補 — 永続データストア / 条件付き (閉じても消えない or 再生成に代償。明示削除＋影響説明＋承認が要る)"
echo "   ※ 再DL / 再ログイン / 再同期 / 再作成の代償がある。「閉じれば回収」ではない"
for p in \
  "$H/Library/Application Support/Claude/vm_bundles" \
  "$H/Library/Developer/CoreSimulator/Devices" \
  "$H/Library/Containers/com.docker.docker/Data/vms" \
  "$H/Library/Application Support/com.apple.wallpaper/aerials" \
; do row "$p"; done
# Electron の Partitions (Notion 等のオフラインキャッシュ。閉じても残る＝永続ストア)
find "$H/Library/Application Support" -maxdepth 2 -type d -name "Partitions" \
  -prune 2>/dev/null | while IFS= read -r d; do row "$d"; done | sort -rh | head -8
hr

echo "## 起動中アプリ本体 (この一覧に出たアプリの Caches/* は今回 skip する)"
echo "   ※ 判定は本体 .app/Contents/MacOS/ のみ。常駐 helper/daemon/crashpad は本体ではない"
echo "   ※ 下は代表例。ここに無いアプリの Caches を消す前は Phase 2 で個別に pgrep -f 'App.app/Contents/MacOS/' を確認"
found=0
# "<bundle .app>|<表示名>" — 本体実行ファイルは <bundle>.app/Contents/MacOS/ 配下にある
for entry in \
  "Google Chrome.app|Google Chrome" \
  "Visual Studio Code.app|VSCode" \
  "Notion.app|Notion" \
  "Codex.app|Codex" \
  "Docker Desktop.app|Docker Desktop" \
  "Docker.app|Docker" \
  "Slack.app|Slack" \
  "Xcode.app|Xcode" \
  "Obsidian.app|Obsidian" \
; do
  bundle="${entry%%|*}"; name="${entry##*|}"
  if pgrep -f "${bundle}/Contents/MacOS/" >/dev/null 2>&1; then
    echo "  RUNNING (本体): $name"; found=1
  fi
done
[ "$found" = 0 ] && echo "  (本体起動なし — Caches は概ね安全に削除できる)"
hr

echo "## 削除可能な古いシミュレータ (simctl unavailable)"
out="$(xcrun simctl list devices 2>/dev/null | grep -i unavailable | head)"
[ -n "$out" ] && echo "$out" || echo "  (なし — 'xcrun simctl delete unavailable' で消せるものは無い)"
hr

echo "scan 完了。削除は SKILL.md の Phase 2 (安全確認) → Phase 3 (削除) に従い、"
echo "対象パスを逐語で確認してから rm -r で実行する。このスクリプトは何も削除していない。"
