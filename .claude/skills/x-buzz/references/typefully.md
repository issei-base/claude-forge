# Typefully MCP — 配信と予約

生成した投稿を X に届ける last-mile。Typefully MCP に下書き/予約を push すれば、
**X API キーも cron も自前で要らず**、Typefully がスケジュール投稿まで肩代わりする。
未導入でも skill は動く (ローカルキューに書き出す fallback)。

> ⚠️ ここに書く tool 名・パラメータは **community 製 MCP (v1 API) と公式ヘルプの記述**から。
> **公式 MCP の正確な tool 名は未公開**。接続後に MCP が返す tool 一覧を実際に見て確認すること。
> 価格は JS レンダリングで取得できず情報源も食い違うため**ライブの /pricing で要確認**。

## 1. セットアップ (リモート HTTP MCP)

公式 MCP は **remote / Streamable HTTP (stateless)**。サーバ URL は `https://mcp.typefully.com`、
エンドポイントは `POST /mcp?TYPEFULLY_API_KEY=YOUR_KEY` (API キーが URL に埋まる)。

```sh
# Claude Code (CLI)。URL は Typefully の Integrations → MCP で自分の値をコピーする。
# 注意: URL は位置引数 (`--url` フラグは存在しない)。scope は user 推奨 (全プロジェクトで有効)。
claude mcp add --scope user --transport http typefully "<Integrations → MCP で取得した URL>"
```

- API キー/URL 取得: Typefully アプリ内 **Integrations → MCP** (生 URL) / **Integrations → Claude** (Claude 向けガイド付きコネクタ)。
- **URL をハードコードしない / repo にコミットしない**。URL 末尾に `?TYPEFULLY_API_KEY=` でキーが埋まる＝シークレット。`--scope project` は `.mcp.json` にキーが commit され漏れるので使わない (`user` か home 以外の `local`)。
- 追加後は **Claude Code を再起動**して tool を認識させる (実行中 session には反映されない)。

## 2. Tool と機能

公式 MCP の機能 (ヘルプ記載・**tool 名は非公開**):
> 下書きの作成・編集、コメントの読み書き、**投稿のスケジュール (next free slot 含む)**、
> キュー管理 (並べ替え・キュールール調整)、メディアアップロード、タグ整理、接続アカウント確認、公開済み投稿の閲覧。

community MCP (v1 API ラッパー) の **実 tool 名** — 公式が返す tool もこの辺りを覆うはず:
- `create_draft` / `typefully_create_draft` — params: `content` (必須), `threadify`, `schedule_date`,
  `auto_retweet_enabled`, `auto_plug_enabled`, `share`
- `get_scheduled_drafts` / `typefully_recently_scheduled_drafts` — `content_filter` (`"tweets"|"threads"`)
- `get_published_drafts` / `typefully_recently_published_drafts`

**v1 API パラメータ (load-bearing)**:
- `content` — 本文。
- `threadify` — `true` で自動スレ分割。
- `schedule_date` — ISO-8601 の datetime **または** リテラル文字列 `"next-free-slot"`。
- `share` — レビュー用の共有プレビューリンクを生成。
- スレ分割は **空行4連続 (`\n\n\n\n`)** が区切り (community 実装)。validate_post.py もこの規則で分割する。

**v2 API (公式 MCP の土台・2025-12-17 リリース)**: social-set 単位 + `platforms` オブジェクト。
```sh
curl -X POST https://api.typefully.com/v2/social-sets/{social_set_id}/drafts \
  -H "Authorization: Bearer YOUR_API_KEY" -H "Content-Type: application/json" \
  -d '{"platforms": {"x": {"enabled": true, "posts": [{"text": "..."}]}}}'
```
v2 の正確な schedule フィールド名はヘルプ未記載。フル仕様は `https://typefully.com/docs/api`。

## 3. スケジュール挙動 (10〜12本/日を散らす)

- Typefully は **予約時刻に自動公開**する (これが製品の本体)。
- **slot 方式**: Scheduling 設定で「suggested times / 保存 slot」を作り、キューに入れた投稿が slot を埋める。
- **`next-free-slot`**: 次の空き slot に自動配置。設定した cadence を尊重。
- **最小間隔**: Calendar Queue View で投稿同士が重ならない最小 gap を設定可。
- **Natural Posting Times**: 選んだ時刻から **±4分** のゆらぎを付けて公開 (※全日ランダムではなく slot 周辺の微ゆらぎ)。

→ **10〜12本/日のやり方**: Scheduling 設定で起床時間帯に ~10-12 個の slot を作り、
skill は `schedule_date="next-free-slot"` で下書きを投入。slot 間隔 + ±4分ゆらぎで時刻が散る。

## 4. Phase 1 (手動承認) → Phase 2 (自動) の切替

**toggle は「schedule_date を付けるか否か」だけ** (公式に独立した "承認待ち" status は無い):
- **Phase 1 (最初の2週間・手動承認)**: `schedule_date` を **付けず**に下書きだけ作る → 下書きは公開されない →
  Typefully で内容を見て自分で Schedule を押す。`share` で共有プレビューリンクも出せる。
- **Phase 2 (自動)**: `schedule_date="next-free-slot"` (または明示 ISO 時刻) を付ける → 予約キューに入り自動公開。

## 5. 価格 / 上限

- **Free** — $0。**MCP は Free に含まれる**（paid 不要）。ただし **月15本まで**の投稿上限。
  この repo の運用は Free 前提（2026-06-01 接続確認済み）。→ **本数を盛らず週3〜4本の良いやつに絞る**のが現実解。
  「10〜12本/日を散らす」系の記述 (§3) は paid・大量運用を想定した名残りで、**今の Free 運用には当てはまらない**。
- **Starter / Creator / Team** — $8〜$39/mo 程度 (情報源で食い違い)。paid は **"unlimited scheduling"** を謳う。
  大量運用に切り替える時だけ検討。**金額はライブで要確認**。
- **X 側レート**: spam ヒューリスティクス上の自然パターン目安は **2〜10 本/日**。Free=月15本なら自然に収まる。

## 6. 対応プラットフォーム / アカウント選択

- 投稿先: **X (Twitter) / LinkedIn / Threads / Bluesky / Mastodon**。
- v2/公式 MCP はアカウントを **social-set** でまとめ、`/v2/social-sets/{social_set_id}/drafts` で対象を指定、
  `platforms` 内で X だけ `enabled: true` にすれば X 限定。MCP は接続アカウント一覧の取得も可。
- v1/community MCP は API キーに紐づくアカウント固定 (per-call のアカウント選択は非公開)。

## fallback (Typefully 未導入時)

Typefully MCP の tool が見当たらなければ、生成した候補を
**`data/x_buzz_queue/<YYYY-MM-DD>.md`** に「コピペで投稿できる形」で書き出し、
ユーザーが手動投稿 or 後で Typefully に貼る。エンジン (生成) は配信方式に依存しない。

## 出典
- [Typefully MCP Server (公式ヘルプ)](https://support.typefully.com/en/articles/13128440-typefully-mcp-server)
- [Typefully API (公式ヘルプ)](https://support.typefully.com/en/articles/8718287-typefully-api)
- [Scheduling and Calendar](https://support.typefully.com/en/articles/9210135-scheduling-and-calendar)
- [agent-skills](https://typefully.com/agent-skills) / [Changelog: API+MCP (2025-12-17)](https://typefully.com/changelog/all-new-api-zapier-integration-mcp-and-126)
- community MCP: [muhammedsamal/typefully-mcp](https://github.com/muhammedsamal/typefully-mcp) / [pascalporedda/typefully-mcp-server](https://github.com/pascalporedda/typefully-mcp-server)
- X レート/自動化: [Sorsa rate limits](https://api.sorsa.io/blog/twitter-api-rate-limits-2026) / [OpenTweet automation rules](https://opentweet.io/blog/twitter-automation-rules-2026)
