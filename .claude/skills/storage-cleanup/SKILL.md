---
name: storage-cleanup
description: "Mac のローカルストレージを最適化する。再生成されるキャッシュ・ビルド成果物・アプリ更新の残骸を **調査 → 安全確認 → 削除** の 3 フェーズで段階的に片付け、回収容量を報告する skill。「ストレージを最適化して」「ディスクの空きを増やして」「不要なリソース / キャッシュを調査して削除して」「容量食ってるもの調べて消して」「定期的にストレージ掃除して」「disk cleanup」「free up disk space」などで発動。調査だけ・削除だけでもフェーズで止められる。起動中アプリのキャッシュは skip、追記中ログは truncate、実データ (Tier 3) には触れない安全設計。**AWS / S3 等クラウドストレージのコスト最適化は [[aws-advisor]]**（この skill はローカルディスク専用）。単に 1 ファイルを消すだけの単純作業には使わない。"
allowed-tools: Read, Bash(bash ~/.claude/skills/storage-cleanup/scripts/scan_storage.sh:*), Bash(df:*), Bash(du:*), Bash(ls:*), Bash(pgrep:*), Bash(xcrun simctl list:*), Bash(brew cleanup:*), Bash(npm cache clean:*)
---

# storage-cleanup

Mac のローカルストレージを、**再生成されるキャッシュ・ビルド成果物・アプリ更新の残骸**の削除で最適化する。破壊的操作なので **調査 → 安全確認 → 削除** の 3 フェーズに分け、各フェーズの結果を見せてから次に進む。実データには触れない。

## 原則（最優先・常に守る）

- **消すのは「再生成される / 再ダウンロードされる」ものだけ。** 実データ（ノート・写真・プロジェクト・同期データ）は消さない。
- **削除前に `df` baseline、削除後に再測定して回収容量を必ず報告。** 「やった気」で終わらせない。
- **起動中アプリの `Caches/*` は消さない。** `pgrep -lf` で確認し、起動中ならそのキャッシュは今回 skip して「閉じれば回収できる」と伝える（起動中削除はキャッシュ破損リスク）。
- **追記中の巨大ログ（held file）は `rm` でなく truncate (`: > file`)。** unlink してもプロセスが fd を保持し続け、空きが戻らない。
- **パスは逐語で提示してから消す。** 親ディレクトリごと glob しない（`DerivedData/*` であって `Developer/*` ではない）。
- **Tier 2 / 3 は必ずユーザー確認。Tier 3（実データ）には触れない。**
- **削除 (`rm`) は `allowed-tools` に入れていない = 毎回承認を挟む設計。** 完全無人で `rm` しない。`allowed-tools` も `Bash(bash:*)` のような汎用許可はせず、読み取り専用 scan スクリプトを**名指しで**許可するだけ（`bash -c 'rm …'` で承認ゲートを迂回させない）。

Tier の定義と具体的な対象パス・根拠は `references/safe-targets.md` を読む（実行時のみ参照。model コンテキストを汚さない）。

## Phase 0 — Preflight

- macOS (darwin) 前提。`df -h /System/Volumes/Data` で baseline（使用量・空き・逼迫度）を取る。
- このセッションで触る範囲を合意する。**既定は Tier 1（安全に即削除）のみ。** Tier 2 を含めるかは逼迫度とユーザー意向で決める。

## Phase 1 — 調査 (Scan)　※読み取り専用・何も消さない

- `bash ~/.claude/skills/storage-cleanup/scripts/scan_storage.sh` を実行する（du スイープ + Tier 別の削除候補とサイズ + 起動中アプリ検出を一括で出力。**read-only**。`allowed-tools` ではこの scan コマンドだけを名指しで許可している）。project スコープ運用なら `.claude/skills/storage-cleanup/scripts/scan_storage.sh` を使う。スクリプトが使えない環境なら `references/safe-targets.md` のパスを `du -sh` で個別に測る。
- 結果を **Tier 別の表**にまとめて提示する（列: 対象パス / サイズ / 安全度 / 再生成の有無）。**回収見込み合計**も出す。
- 「調査だけ」の依頼ならここで完了してよい。

## Phase 2 — 安全確認 (Verify)

各候補について順に確認し、最終的な削除リストを確定する:

- それが本当に cache / ビルド成果物 / 更新残骸か（`references/safe-targets.md` の分類に照合）。判断がつかないものは**消さない側に倒す**。
- **所有アプリが起動中でないか**（`pgrep -lf "<app>"`）。起動中なら今回 skip し、「閉じれば回収可」と伝える。
- 追記中の巨大ログは **truncate 対象**としてマーク（`rm` ではなく `: > <log>`）。
- Tier 2 は影響（再ダウンロード / 再作成 / 実機再接続が必要 等）を 1 行で説明してから含める。Tier 3 は除外。
- 確定した **削除リスト（逐語パス）** をユーザーに提示し、GO をもらう。

## Phase 3 — 削除 (Delete)

- baseline を記録: `df -h /System/Volumes/Data`。
- Tier・グループごとに削除し、各グループで「何を消したか」を短く報告する。代表的なコマンド:
  - Xcode: `rm -rf ~/Library/Developer/Xcode/DerivedData/*` / `rm -rf ~/Library/Developer/Xcode/iOS\ DeviceSupport/*`
  - アプリキャッシュ（**非起動のもののみ**）: `rm -rf ~/Library/Caches/<bundle-id>/*`
  - npm: `npm cache clean --force`
  - Homebrew: `brew cleanup -s`
  - 更新残骸: `rm -rf ~/Library/Caches/*.ShipIt/*`（held ログがあれば `: > <log>` で truncate）
  - 古いシミュレータ: `xcrun simctl delete unavailable`
- 大量削除（DerivedData / DeviceSupport など）は時間がかかる → `run_in_background` で実行し、完了を待ってから次へ。
- 完了後に `df` を再測定し、**Before / After + 回収容量**を表で報告する。

## 定期実行（定期的に回したいとき）

- 本 skill は [[schedule]] skill か `/loop` で定期起動できる。ただし**削除は対話承認を残す**設計なので、**完全無人の cron で `rm` を自動実行しない**。
- 推奨運用: スケジュールでは **Phase 1–2（調査 + 安全確認 + レポート）までを自動**で回し、Tier 1 の削除候補と回収見込みを通知する。**削除の GO は人間**が出す。
- 「毎週ストレージを調査してレポートして」なら、schedule で Phase 1–2 を回す設定にする（Phase 3 は手動承認）。

## スコープ外

- **クラウド / AWS のストレージ最適化は [[aws-advisor]]。** この skill はローカルディスク専用。
- 単一ファイルの削除や、プロジェクト内の意図的な成果物削除には使わない（普通に `rm`）。
- **Tier 3（実データ）の削除はしない。** 必要なら個別に人が判断する。
