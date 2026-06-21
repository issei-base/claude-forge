# 削除対象カタログ（safe-targets）

storage-cleanup が削除を判断するときの分類表。**パスは逐語で確認してから消す。** サイズはマシン・時期で変わるので必ず `du -sh` で実測する（このカタログは「何が安全で何が危険か」の根拠用）。

macOS の空き容量はデータボリュームで見る: `df -h /System/Volumes/Data`。

---

## Tier 1 — 安全に即削除（再生成されるキャッシュ / ビルド成果物 / 更新残骸）

| パス | 正体 | 削除後どうなる | 注意 |
|---|---|---|---|
| `~/Library/Developer/Xcode/DerivedData/*` | Xcode ビルドキャッシュ・派生データ | 次回ビルドで再生成（初回ビルドが遅くなるだけ） | Xcode 起動中ならビルド中でないことを確認 |
| `~/Library/Developer/Xcode/iOS DeviceSupport/*` | 接続した実機のシンボル | 実機を再接続すると Xcode が再取得 | 再取得に数分かかる |
| `~/Library/Caches/<bundle-id>/*` | 各アプリのキャッシュ | アプリが再生成 | **所有アプリ本体起動中は skip**（破損リスク）。例: `claude-cli-nodejs`(Claude Code), `com.openai.codex`(Codex), `Google`(Chrome), `ms-playwright`, `CocoaPods`, `node-gyp`, `Homebrew` |
| `~/Library/Application Support/<Electron App>/{Cache,Code Cache,GPUCache,CachedData,CachedExtensionVSIXs}` | Electron アプリのキャッシュ（VSCode 等） | アプリが再生成 | **本体非起動のみ**。同階層の `User` / `Local Storage` / `IndexedDB` は**設定・状態なので消さない**。`Partitions/` は永続ストア（Tier 2） |
| `~/.npm/_cacache`, `~/.npm/_logs`, `~/.npm/_npx` | npm キャッシュ・ログ・npx 実行パッケージ | `_cacache` は `npm cache clean --force` で再構築、`_npx` は次回 npx で再DL | キャッシュは `npm cache clean --force` を優先 |
| `~/.expo/{ios-simulator-app-cache,expo-go}` | Expo の開発キャッシュ | 次回 expo 実行で再生成 | 設定 `state.json` は残す |
| `~/.cache/*` | 汎用ツールキャッシュ | 各ツールが再生成 | 中身を `du -sh ~/.cache/*` で確認。`codex-runtimes` は **Codex 本体起動中なら skip**（再DLされる runtime） |
| `~/Library/Caches/*.ShipIt/*` | アプリ自動更新（Squirrel）の残骸 — DL 済み更新パッケージ・暴走ログ | 不要。更新は再取得される | **所有アプリ起動中の追記ログは `rm` でなく `: > <log>` で truncate**（unlink では空きが戻らない）。例: `com.microsoft.VSCode.ShipIt`, `notion.id.ShipIt` |
| `brew cleanup -s` | Homebrew の古い formula / キャッシュ | 再ダウンロード可 | コマンドで実行（手で rm しない） |

---

## Tier 2 — 永続データストア / 条件付き（必ず影響を説明してから）

**これらはキャッシュではなく「永続データストア」。アプリを閉じても消えない** — 回収には明示削除が要り、再DL / 再ログイン / 再同期 / 再作成の代償がある。「閉じれば回収」とは言わない。

| パス | 正体 | 削除の条件・影響 |
|---|---|---|
| `~/Library/Application Support/<Electron App>/Partitions` | Electron アプリのオフラインキャッシュ（例: Notion で 10GB 級） | 本体を閉じてから `rm -r`。**次回起動で再ログイン + 全再同期**が走る（実データはサーバ側）。オフライン編集の未同期分があれば注意 |
| `~/Library/Containers/com.docker.docker/Data/vms` | Docker の VM ディスク（全イメージ/コンテナ/ボリュームを内包） | 起動中なら `docker system prune`（必要なら `-a --volumes`）で**正規に**縮小が安全。VM ごと工場出荷リセットするなら**全ローカルデータ喪失**を承認の上で `rm -r .../Data/vms/0`（次回起動で空 VM を再作成）。`com.docker.vmnetd` は常駐 root helper で**本体ではない**ので、これだけ残っていても Docker Desktop は終了済み |
| `~/Library/Application Support/Claude/vm_bundles` | Claude Desktop のローカル VM ディスクイメージ（10GB 級） | **VM / サンドボックス機能を使わないユーザーのみ削除可。** Claude Desktop **本体が起動中**だとイメージを掴んでいて `rm` しても `df` の空きが戻らない（held file・`lsof \| grep claudevm` で確認）→ **本体終了後に `rm -r`**（VM イメージなので truncate は不可＝壊れる。held ログの truncate 則は適用しない）。VM / サンドボックス機能を使うなら次回起動で再生成されるので恒久的な回収にはならない |
| `~/Library/Developer/CoreSimulator/Devices` | iOS シミュレータの実体（入れたアプリ状態を含む） | 全削除はしない。`xcrun simctl delete unavailable` で**古い / 利用不可ランタイムのみ**消す。全消しは実機開発に影響 |
| `~/Library/Application Support/com.apple.wallpaper/aerials` | macOS のエアリアル動画壁紙（`.mov` で数 GB 級） | 空撮壁紙 / スクリーンセーバを選び直すと macOS が再DL。回収効果は一時的 |

---

## Tier 3 — 実データ。触らない（消すなら人が個別判断）

これらは**キャッシュではなく実データ / 同期データ / インストール済み環境**。storage-cleanup では削除しない。

| パス | 中身 |
|---|---|
| `~/Library/Application Support/<App>`（Notion / Code / obsidian / minecraft / Slack のデータ部 等） | アプリの本体データ。キャッシュ部分だけは Tier 1 の `Caches` 側で扱う |
| `~/Library/Group Containers/*`（OneDrive / Office 等） | クラウド同期データ。消すと再同期 or データ喪失リスク |
| `~/.nvm`, インストール済み Node | 消すと再インストールが必要 |
| `~/.codex`, `~/.local` | config / session / インストール物が混在 |
| `<project>/node_modules` | 再インストールで戻るが、prune は各プロジェクト側の判断。一括削除しない |

---

## 安全ルール（再掲）

1. 削除前 `df` → 削除後 `df` で**回収量を実測報告**。
2. **起動中アプリ本体の Caches は消さない**。判定は `pgrep -f "<App>.app/Contents/MacOS/"`（本体のみ）。緩い部分一致は常駐 helper/daemon/crashpad を誤検知する。
3. **キャッシュ ≠ 永続データストア**。永続ストア（VM / Partitions / Simulator）は閉じても消えない＝明示削除（Tier 2・影響説明 + 承認）。「閉じれば回収」とは言わない。
4. **削除は `rm -rf` でなく `rm -r`**。`rm -rf` を deny する repo がある（claude-forge 自身も）。deny を `find -delete` / `bash -c` で迂回しない。
5. **追記中ログは truncate（`: > file`）**、`rm` しない。
6. パスは**逐語**で。`DerivedData/*` であって `Developer/*` ではない。
7. Tier 2 は影響説明 + 承認。**Tier 3 は触らない**。
8. 判断がつかないものは**消さない側**に倒す。
