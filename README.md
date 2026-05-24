# claude-forge

個人用 Claude Code カスタマイズ資産を git で管理するリポジトリ。

```
claude-forge/
├── commands/   # スラッシュコマンド → ~/.claude/commands/
├── skills/     # カスタム skill  → ~/.claude/skills/
├── agents/     # カスタム agent  → ~/.claude/agents/
├── hooks/      # hook スクリプト → ~/.claude/hooks/
├── settings/
│   └── settings.example.json  # ~/.claude/settings.json 用のテンプレ (手動マージ)
├── .github/workflows/         # PR 自動レビュー / セキュリティチェック (claude-forge 自身用)
└── install.sh                 # 冪等な symlink インストーラ
```

## 新しいマシンでのセットアップ

```sh
git clone git@github.com:issei-base/claude-forge.git ~/projects/claude-forge
cd ~/projects/claude-forge
./install.sh
```

`install.sh` は上記 4 ディレクトリを `~/.claude/` 配下にシンボリックリンクする。既に実体ディレクトリがある場合は `*.bak-<timestamp>` にバックアップしてから、その中身を本 repo にマージする。

`settings.json` は **シンボリックリンクしない** (Claude Code がランタイムで rewrites するため)。代わりに `settings/settings.example.json` から手動マージする、もしくは `/permissions` UI を使う。

## ここに置くもの

| ディレクトリ | 用途 |
|---|---|
| `commands/` | `/<filename>` で呼べるスラッシュコマンドの markdown |
| `skills/` | `<skill-name>/SKILL.md` 形式の model-invoked skill |
| `agents/` | `<agent-name>.md` のカスタム subagent |
| `hooks/` | `settings.json` の `hooks` ブロックから参照される shell script |
| `.github/workflows/` | claude-forge 自身の PR レビュー / セキュリティチェック |

## ここに置かないもの

- `~/.claude/settings.json` / `settings.local.json` — ランタイムで書き換わる、マシン固有
- `~/.claude/projects/` — プロジェクトごとの memory / session state
- `~/.claude/plugins/` — plugin marketplace 経由でインストールされる
- secrets を含むもの全て (API key、token など)

## 現在のスラッシュコマンド

| コマンド | やること |
|---|---|
| `/codex-review` | 現在の git 差分を OpenAI Codex CLI に渡してセカンドオピニオンレビュー |
| `/install-pr-reviews` | 現在の git repo の `.github/workflows/` にこの repo の PR 自動レビュー workflow をコピー |

## 現在の skill (model-invoked)

| Skill | 発動するフレーズ | 中身 |
|---|---|---|
| `ship` | 「ship して」「PR出して」「PR作って」 | branch → commit → push → `gh pr create`。**main / default branch への直接 push は絶対禁止** の hard guard 付き |
| `codex-review` | 「codex にレビュー」「セカンドオピニオン」「他のモデルにも見せて」 | 現在の差分を Codex CLI に渡し、出力を逐語的にユーザーに見せる |
| `aws-docs` | 「AWS の docs」「公式ドキュメントだと」「Lambda の上限って」 | `aws` MCP server で公式 docs を引いて一次ソースから回答 |
| `aws-advisor` | 「AWS で X したい」「best practice for <service>」「Well-Architected 的に」 | Well-Architected docs に基づくアーキテクチャ助言 (推奨 + tradeoffs) |
| `lesson-homework` | 「次回の宿題考えて」「ハンズオン課題提案して」「`<sheet URL>` の宿題」 | Google スプレッドシートのレッスン記録 (行 5) に次回ハンズオン課題を生成・書き込み。読取は CSV export で認証不要、書込は `gws` の OAuth 必須。ユーザー承認後にのみ書き込み |

## MCP servers (`settings/settings.example.json`)

| サーバー | 用途 / 前提 |
|---|---|
| `obsidian` | `/Users/issei/obsidian/issei` の vault |
| `aws` | AWS 公式マネージド MCP (`mcp-proxy-for-aws`)。前提: `uv` (`brew install uv`) と AWS credentials (`aws configure` か SSO)。リージョン default は `ap-northeast-1` (テンプレ内、適宜編集)。IAM SigV4 でローカル credentials を使うので、MCP の実行可能範囲は IAM ポリシーに従う |

`install.sh` 実行後の有効化:
1. `settings/settings.example.json` の `mcpServers` ブロックを `~/.claude/settings.json` に手動マージ
2. Claude Code を再起動して新サーバーを認識
3. (AWS のみ) `aws sts get-caller-identity` が成功することを先に確認

## PR 自動レビュー workflow

`.github/workflows/` に 2 つの workflow を置いている。**`claude-review` ラベルが付いた PR でのみ起動** する (ship skill が PR 作成時に自動付与)。ラベル無しの PR は無視されるので、軽微な変更で quota を無駄遣いしない。

| Workflow | 役割 |
|---|---|
| `claude-review.yml` | 一般レビュー (正しさ / 可読性 / テスト / パフォーマンス) を inline コメント |
| `claude-security-review.yml` | セキュリティ専用レビュー (OWASP / secret / 認可 / 暗号誤用 / 依存脆弱性) を inline コメント |

**merge は手動。** Workflow / ship skill は merge を絶対に行わない。Claude のレビューを読んだ上で人間が判断。

**ベストプラクティスとしての Branch Protection** (claude-forge では有効化済み):
- `main` への直接 push 不可
- PR merge に **承認 (approving review) 1 件以上** 必須
- 必須 status check: `Claude PR Review` (PASS = approve / FAIL = request-changes) と `Claude Security Review` (critical/high あれば exit 1 で fail)
- 新しい commit が push されたら過去の approve は dismiss (`dismiss_stale_reviews`)
- inline コメントは resolve 必須 (`required_conversation_resolution`)
- force push / branch 削除 禁止
- 緊急時のため admin (issei-base) は bypass 可 (`enforce_admins: false`)

設定コマンド (このリポジトリで既に実行済み):
```sh
gh api -X PUT /repos/issei-base/claude-forge/branches/main/protection --input - <<'EOF'
{
  "required_status_checks": { "strict": false, "contexts": ["Claude PR Review", "Claude Security Review"] },
  "enforce_admins": false,
  "required_pull_request_reviews": { "required_approving_review_count": 1, "dismiss_stale_reviews": true, "require_code_owner_reviews": false },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true,
  "required_linear_history": false
}
EOF
```

**運用フロー** (Solo dev 向け):
1. `ship` skill で PR 作成 (ラベル `claude-review` 自動付与)
2. `Claude PR Review` workflow が起動 → Claude が inline コメント + `--approve` または `--request-changes` を post
3. `Claude Security Review` workflow が起動 → critical/high あれば step を fail (= check fail)
4. 両方 OK ならユーザーが内容を確認して **手動で merge**
5. critical/high 修正が必要なら commit を push (stale approve は自動 dismiss、再度 Claude review が走る)
6. 緊急時のみ admin が Branch Protection を bypass して force merge 可 (使用は最小限に)

### claude-forge 自身で動かす前提

3 つすべてが揃って初めて動く:
1. **`id-token: write` permission**: workflow ファイルに記載済み
2. **`CLAUDE_CODE_OAUTH_TOKEN` secret** (Pro/Max サブスク使用時):
   ```sh
   claude setup-token        # OAuth token を発行
   gh secret set CLAUDE_CODE_OAUTH_TOKEN -R issei-base/claude-forge  # ★ 対話プロンプトに貼り付け (チャット/履歴に出さない)
   ```
   API key を使う場合は `ANTHROPIC_API_KEY` を同手順で。
3. **Claude Code GitHub App をインストール**: https://github.com/apps/claude → `claude-forge` を選択

**初回 workflow 追加 PR は自分自身をレビューできない**。Anthropic action のセキュリティ機能 (PR の workflow と main の workflow が一致するか検証) で skip される。merge 後の PR から動くようになる。

### 他リポジトリに横展開する

そのリポジトリの中で:
```
/install-pr-reviews
```
を実行。workflow 2 ファイルのコピー + `claude-review` ラベル作成 + GitHub App / secret 設定の案内が出る。
