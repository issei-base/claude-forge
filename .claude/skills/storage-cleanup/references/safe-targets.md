# 削除対象カタログ（safe-targets）

storage-cleanup が削除を判断するときの分類表。**パスは逐語で確認してから消す。** サイズはマシン・時期で変わるので必ず `du -sh` で実測する（このカタログは「何が安全で何が危険か」の根拠用）。

macOS の空き容量はデータボリュームで見る: `df -h /System/Volumes/Data`。

---

## Tier 1 — 安全に即削除（再生成されるキャッシュ / ビルド成果物 / 更新残骸）

| パス | 正体 | 削除後どうなる | 注意 |
|---|---|---|---|
| `~/Library/Developer/Xcode/DerivedData/*` | Xcode ビルドキャッシュ・派生データ | 次回ビルドで再生成（初回ビルドが遅くなるだけ） | Xcode 起動中ならビルド中でないことを確認 |
| `~/Library/Developer/Xcode/iOS DeviceSupport/*` | 接続した実機のシンボル | 実機を再接続すると Xcode が再取得 | 再取得に数分かかる |
| `~/Library/Caches/<bundle-id>/*` | 各アプリのキャッシュ | アプリが再生成 | **所有アプリ起動中は skip**（破損リスク）。例: `claude-cli-nodejs`(Claude Code), `com.openai.codex`(Codex), `Google`(Chrome), `ms-playwright`, `CocoaPods`, `Homebrew` |
| `~/.npm/_cacache`, `~/.npm/_logs` | npm キャッシュ・ログ | `npm cache clean --force` で正規に再構築 | `npm cache clean --force` を優先 |
| `~/.cache/*` | 汎用ツールキャッシュ（`codex-runtimes` 等） | 各ツールが再生成 | 中身を `du -sh ~/.cache/*` で一度確認 |
| `~/Library/Caches/*.ShipIt/*` | アプリ自動更新（Squirrel）の残骸 — DL 済み更新パッケージ・暴走ログ | 不要。更新は再取得される | **所有アプリ起動中の追記ログは `rm` でなく `: > <log>` で truncate**（unlink では空きが戻らない）。例: `com.microsoft.VSCode.ShipIt`, `notion.id.ShipIt` |
| `brew cleanup -s` | Homebrew の古い formula / キャッシュ | 再ダウンロード可 | コマンドで実行（手で rm しない） |

---

## Tier 2 — 条件付き（再DL / 再作成 / 機能未使用が前提。必ず影響を説明してから）

| パス | 正体 | 削除の条件・影響 |
|---|---|---|
| `~/Library/Application Support/Claude/vm_bundles/claudevm.bundle` | Claude Desktop のローカル VM ディスクイメージ（`rootfs.img` / `sessiondata.img` で 10GB 級） | **VM / サンドボックス（ローカルエージェント）機能を使わないユーザーのみ削除可。** ただし **Claude Desktop は起動時に VM ヘルパー（`com.apple.Virtualization...`）を立ち上げてイメージを開いたまま掴むことがある**。その場合: ① `rm` しても held file なので `df` の空きは増えない（**先に `lsof \| grep claudevm` で掴んでいるプロセスを確認**）、② 解放には **Claude Desktop の終了が必要**、③ 次回起動で**再生成され得る**ため、恒久的に消すには Claude Desktop 側で VM / サンドボックス機能を無効化してから（or アプリ終了中に）削除する。実地確認: 2026-06、issei 環境で削除しても PID が掴んでおり即時解放されず（アプリ終了待ち） |
| `~/Library/Developer/CoreSimulator/Devices` | iOS シミュレータの実体 | 全削除はしない。`xcrun simctl delete unavailable` で**古い / 利用不可ランタイムのみ**消す |
| `~/Library/Containers/com.docker.docker/Data/vms` | Docker の VM ディスク | `docker system prune`（必要なら `-a --volumes`）で正規に縮小。手で rm しない |
| wallpaper aerial 動画（`~/Library/Application Support/com.apple.wallpaper`, `Containers/com.apple.wallpaper.agent`） | macOS のエアリアル動画壁紙 | 消しても macOS が再ダウンロードするだけ。回収効果は一時的 |

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
2. **起動中アプリの Caches は消さない**（`pgrep -lf` で確認）。
3. **追記中ログは truncate（`: > file`）**、`rm` しない。
4. パスは**逐語**で。`DerivedData/*` であって `Developer/*` ではない。
5. Tier 2 は影響説明 + 承認。**Tier 3 は触らない**。
6. 判断がつかないものは**消さない側**に倒す。
