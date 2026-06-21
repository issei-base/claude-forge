---
name: storage-cleanup
description: "Mac のローカルストレージを最適化する。再生成されるキャッシュ・ビルド成果物・アプリ更新の残骸を **調査 → 安全確認 → 削除** の 3 フェーズで段階的に片付け、回収容量を報告する skill。「ストレージを最適化して」「ディスクの空きを増やして」「不要なリソース / キャッシュを調査して削除して」「容量食ってるもの調べて消して」「定期的にストレージ掃除して」「disk cleanup」「free up disk space」などで発動。調査だけ・削除だけでもフェーズで止められる。起動中アプリのキャッシュは skip、追記中ログは truncate、実データ (Tier 3) には触れない安全設計。**AWS / S3 等クラウドストレージのコスト最適化は [[aws-advisor]]**（この skill はローカルディスク専用）。単に 1 ファイルを消すだけの単純作業には使わない。"
allowed-tools: Read, Bash(bash ~/.claude/skills/storage-cleanup/scripts/scan_storage.sh:*), Bash(df:*), Bash(du:*), Bash(ls:*), Bash(pgrep:*), Bash(xcrun simctl list:*)
---

# storage-cleanup

Mac のローカルストレージを、**再生成されるキャッシュ・ビルド成果物・アプリ更新の残骸**の削除で最適化する。破壊的操作なので **調査 → 安全確認 → 削除** の 3 フェーズに分け、各フェーズの結果を見せてから次に進む。実データには触れない。

## 原則（最優先・常に守る）

- **消すのは「再生成される / 再ダウンロードされる」ものだけ。** 実データ（ノート・写真・プロジェクト・同期データ）は消さない。
- **「キャッシュ」と「永続データストア」を区別する（最重要）。** _キャッシュ_（`Caches/*`、Electron の `Cache` / `Code Cache` / `GPUCache` 等）はアプリが再生成するので、起動中なら今回 skip して「閉じれば回収できる」と伝えてよい。だが _永続データストア_（Docker VM `Data/vms`、Electron アプリの `Partitions/`、iOS Simulator の `Devices`、Notion 等のオフラインキャッシュ）は**アプリを閉じても消えない** — 回収には明示削除が要り、再ログイン / 再同期 / 再作成の代償がある。これらに「閉じれば回収」とは言わない。削除するなら Tier 2 として影響を説明し承認を取る。
- **起動判定は「本体プロセス」で行う。** `pgrep -f "<App>.app/Contents/MacOS/"` で**アプリ本体**を確認する。`pgrep -lf "<名前>"` の緩い部分一致は**常駐 helper / daemon / crashpad を本体と誤検知**する（例: `com.docker.vmnetd` は Docker Desktop 終了後も常駐する root helper であって本体ではない）。本体が無く helper / crashpad だけ残るのは「終了済み」と判断する。
- **削除前に `df` baseline、削除後に再測定して回収容量を必ず報告。** 「やった気」で終わらせない。
- **削除は `rm -rf` でなく `rm -r` を使う。** 一部 repo（claude-forge 自身を含む）は settings の deny で `Bash(rm -rf:*)` / `Bash(rm -fr:*)` を**ハードブロック**しており、承認しても通らない。`-f` を外した `rm -r` はキャッシュ（自分の書込権限内）なら止まらず deny にも該当しない。**deny を `find … -delete` や `bash -c 'rm …'` で迂回しない**（ガードの趣旨に反する）。
- **追記中の巨大ログ（held file）は `rm` でなく truncate (`: > file`)。** unlink してもプロセスが fd を保持し続け、空きが戻らない。
- **パスは逐語で提示してから消す。** 親ディレクトリごと glob しない（`DerivedData/*` であって `Developer/*` ではない）。
- **Tier 2 / 3 は必ずユーザー確認。Tier 3（実データ）には触れない。**
- **破壊的・外向きコマンドは一切 `allowed-tools` に入れない = 毎回承認を挟む設計。** 対象は `rm` だけでなく `brew cleanup` / `npm cache clean` / `xcrun simctl delete` などのキャッシュ削除、および**アプリを閉じる `osascript … quit` も含む**。`allowed-tools` は**読み取り専用のものだけ**（scan スクリプトの名指し許可 + `df`/`du`/`ls`/`pgrep`/`xcrun simctl list`）。`Bash(bash:*)` のような汎用許可もしない（`bash -c 'rm …'` で承認ゲートを迂回させないため）。完全無人で削除しない。

Tier の定義と具体的な対象パス・根拠は `references/safe-targets.md` を読む（実行時のみ参照。model コンテキストを汚さない）。

## Phase 0 — Preflight

- macOS (darwin) 前提。`df -h /System/Volumes/Data` で baseline（使用量・空き・逼迫度）を取る。
- このセッションで触る範囲を合意する。**既定は Tier 1（安全に即削除）のみ。** Tier 2 を含めるかは逼迫度とユーザー意向で決める。

## Phase 1 — 調査 (Scan)　※読み取り専用・何も消さない

- `bash ~/.claude/skills/storage-cleanup/scripts/scan_storage.sh` を実行する（du スイープ + Tier 別の削除候補とサイズ + 起動中アプリ検出を一括で出力。**read-only**。`allowed-tools` ではこの scan コマンドだけを名指しで許可している）。project スコープ運用なら `.claude/skills/storage-cleanup/scripts/scan_storage.sh` を使う。スクリプトが使えない環境なら `references/safe-targets.md` のパスを `du -sh` で個別に測る。
- **scan が出す固定リストだけで満足しない。** 最大の獲物は固定の `Caches` リスト外に隠れていることがある（実例: Notion 12G・aerial 壁紙 4.1G はどちらも `Application Support` 配下だった）。scan が出す `Application Support` / `Group Containers` / dotディレクトリの一覧で **1G 超の塊**は、`du -sh "<dir>"/*` で一段掘り、cache か永続ストアか実データかを判定してから候補に入れる。
- 結果を **Tier 別の表**にまとめて提示する（列: 対象パス / サイズ / 安全度 / 再生成の有無）。**回収見込み合計**も出す。
- 「調査だけ」の依頼ならここで完了してよい。

## Phase 2 — 安全確認 (Verify)

各候補について順に確認し、最終的な削除リストを確定する:

- それが cache / ビルド成果物 / 更新残骸か、それとも**永続データストア**（閉じても消えない）か実データかを、`references/safe-targets.md` の分類に照合して判定する。判断がつかないものは**消さない側に倒す**。
- **所有アプリ本体が起動中でないか**を `pgrep -f "<App>.app/Contents/MacOS/"` で確認する（緩い部分一致は使わない＝helper/daemon を誤検知）。起動中アプリの**キャッシュ**は今回 skip し「閉じれば回収可」と伝える。
- **起動中アプリのキャッシュを今回回収したい**とユーザーが望む場合のみ: ① `osascript -e 'tell application "<App>" to quit'` で graceful に閉じる（承認を取る）→ ② `pgrep -f "<App>.app/Contents/MacOS/"` で**本体終了を確認**（原則どおり crashpad / helper の orphan は本体ではない＝残っていても終了済みと判断する）→ ③ そのキャッシュを削除。本体が落ちないアプリは無理に kill せず skip。
- 追記中の巨大ログは **truncate 対象**としてマーク（`rm` ではなく `: > <log>`）。
- Tier 2（永続ストア含む）は影響（再ダウンロード / 再ログイン / 再同期 / 再作成 / 実機再接続が必要 等）を 1 行で説明してから含める。Tier 3 は除外。
- 確定した **削除リスト（逐語パス）** をユーザーに提示し、GO をもらう。

## Phase 3 — 削除 (Delete)

- baseline を記録: `df -h /System/Volumes/Data`。
- 削除は **`rm -rf` でなく `rm -r`**（原則参照: deny 回避と取り違え防止）。Tier・グループごとに削除し、各グループで「何を消したか」を短く報告する。代表的なコマンド:
  - Xcode: `rm -r ~/Library/Developer/Xcode/DerivedData/*` / `rm -r ~/Library/Developer/Xcode/iOS\ DeviceSupport/*`
  - アプリキャッシュ（**本体非起動のもののみ**）: `rm -r ~/Library/Caches/<bundle-id>/*`
  - Electron アプリのキャッシュ（本体非起動・**`User` / `Local Storage` / `IndexedDB` 等の設定/状態は消さない**）: scan の Electron cache 一覧（`Cache` / `Code Cache` / `GPUCache` / `CachedData` / `CachedExtensionVSIXs` の5種）から逐語で。例: `rm -r ~/Library/Application\ Support/Code/Cache ~/Library/Application\ Support/Code/"Code Cache" ~/Library/Application\ Support/Code/GPUCache ~/Library/Application\ Support/Code/CachedData ~/Library/Application\ Support/Code/CachedExtensionVSIXs`（`Code Cache` は空白入りなので要クォート）
  - npm / npx: `npm cache clean --force` / `rm -r ~/.npm/_npx`
  - Homebrew: `brew cleanup -s`
  - 更新残骸（**Phase 2 で確定した非起動アプリの `*.ShipIt` を 1 個ずつ逐語で**。`*.ShipIt` の glob 一括はしない＝未スキャン/起動中アプリの分まで消さないため）: `rm -r ~/Library/Caches/com.microsoft.VSCode.ShipIt/*`（held ログがあれば `rm` ではなく `: > <log>` で truncate）
  - 古いシミュレータ: `xcrun simctl delete unavailable`
- **永続データストア（Tier 2）** は影響説明 + 承認の後に削除する。閉じても消えないので、回収するには明示削除が要る:
  - Docker VM: 正規には起動中に `docker system prune`（必要なら `-a --volumes`）で縮小。VM ごと工場出荷リセットするなら**全イメージ/コンテナ/ボリュームを失う**ことを承認の上で `rm -r ~/Library/Containers/com.docker.docker/Data/vms/0`（次回起動で空の VM を再作成）。
  - Electron の `Partitions/`（**サーバ同期が確認できるアプリのみ**・例: Notion）: 本体を閉じてから `rm -r`。**次回起動で再ログイン + 全再同期**になる旨を伝える。`Partitions` は Cookie / IndexedDB / LocalStorage（ローカル実データ）も含むので、**同期が確認できない / ローカルファーストのアプリは Tier 3 として消さない**。
- **起動中アプリのキャッシュを回収する場合**は Phase 2 の手順（`osascript … quit` → 本体終了を確認 → 削除）に従う。
- 大量削除（DerivedData / Partitions / DeviceSupport など）は時間がかかる → `run_in_background` で実行し、完了を待ってから次へ。
- 完了後に `df` を再測定し、**Before / After + 回収容量**を表で報告する。

## 定期実行（定期的に回したいとき）

- 本 skill は `schedule` skill / Routines か `/loop` で定期起動できる。ただし**削除は対話承認を残す**設計なので、**完全無人の cron で `rm` を自動実行しない**。
- 推奨運用: スケジュールでは **Phase 1–2（調査 + 安全確認 + レポート）までを自動**で回し、Tier 1 の削除候補と回収見込みを通知する。**削除の GO は人間**が出す。
- 「毎週ストレージを調査してレポートして」なら、schedule で Phase 1–2 を回す設定にする（Phase 3 は手動承認）。

## スコープ外

- **クラウド / AWS のストレージ最適化は [[aws-advisor]]。** この skill はローカルディスク専用。
- 単一ファイルの削除や、プロジェクト内の意図的な成果物削除には使わない（普通に `rm`）。
- **Tier 3（実データ）の削除はしない。** 必要なら個別に人が判断する。
