# claude-forge

個人用 Claude Code カスタマイズ資産を git で管理するリポジトリ。

```
claude-forge/
├── skills/     # カスタム skill  → ~/.claude/skills/
├── agents/     # カスタム agent  → ~/.claude/agents/
├── hooks/      # hook スクリプト → ~/.claude/hooks/
├── settings/
│   └── settings.example.json  # ~/.claude/settings.json 用のテンプレ (手動マージ)
├── .github/workflows/         # PR 自動レビュー / セキュリティチェック (claude-forge 自身用)
└── install.sh                 # 冪等な symlink インストーラ
```

> **方針: スラッシュコマンドは使わず、すべて Skills に統合** (Anthropic の最近のガイドラインに沿う)。Skill は description で自動発火するが、明示呼びしたい時は `/skill-name` でも呼べる。`commands/` ディレクトリは置かない。

## 新しいマシンでのセットアップ

```sh
git clone git@github.com:issei-base/claude-forge.git ~/projects/claude-forge
cd ~/projects/claude-forge
./install.sh
```

`install.sh` は上記 3 ディレクトリ (`skills` / `agents` / `hooks`) を `~/.claude/` 配下にシンボリックリンクする。既に実体ディレクトリがある場合は `*.bak-<timestamp>` にバックアップしてから、その中身を本 repo にマージする。旧バージョンで `~/.claude/commands` を symlink していた場合は、`install.sh` が broken link を自動で掃除する。

`settings.json` は **シンボリックリンクしない** (Claude Code がランタイムで rewrites するため)。代わりに `settings/settings.example.json` から手動マージする、もしくは `/permissions` UI を使う。

## ここに置くもの

| ディレクトリ | 用途 |
|---|---|
| `skills/` | `<skill-name>/SKILL.md` 形式の skill。description で自動発火 or `/skill-name` で明示呼び |
| `agents/` | `<agent-name>.md` のカスタム subagent |
| `hooks/` | `settings.json` の `hooks` ブロックから参照される shell script |
| `.github/workflows/` | claude-forge 自身の PR レビュー / セキュリティチェック |

## ここに置かないもの

- `~/.claude/settings.json` / `settings.local.json` — ランタイムで書き換わる、マシン固有
- `~/.claude/projects/` — プロジェクトごとの memory / session state
- `~/.claude/plugins/` — plugin marketplace 経由でインストールされる
- secrets を含むもの全て (API key、token など)

## 現在の skill

description で自動発火 (model-invoked)。明示的に呼びたい時は `/skill-name` でも可。

| Skill | 発動するフレーズ | 中身 |
|---|---|---|
| `ship` | 「ship して」「PR出して」「PR作って」 | branch → commit → push → `gh pr create`。**main / default branch への直接 push は絶対禁止** の hard guard 付き |
| `codex-review` | 「codex にレビュー」「セカンドオピニオン」「他のモデルにも見せて」 | 現在の差分を Codex CLI に渡し、出力を逐語的にユーザーに見せる |
| `install-pr-reviews` | 「この repo にも PR レビュー入れて」「自動レビュー workflow を install して」 | 現在 cwd の git repo の `.github/workflows/` にこの repo の PR 自動レビュー workflow をコピー、ラベル作成、GitHub App / secret 設定の案内も |
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

### Branch Protection: claude-forge では **off**

このリポジトリは Solo dev の dotfiles なので **Branch Protection は有効化していません**。理由:
- approve を Claude bot に頼る運用は、`anthropics/claude-code-action` v1 の sandbox 仕様で `gh pr review` 系を実行できず安定しなかった (permission denials 多発)
- approve 必須の Protection を残すと、Solo dev では毎回 admin bypass の儀式が発生して実益がない
- main への直 push は `ship` skill 側の hard guard でガードしている (ツール強制ではなく規律で担保)

### 運用フロー (現状)

1. `ship` skill で PR 作成 (ラベル `claude-review` 自動付与)
2. `Claude PR Review` / `Claude Security Review` workflow が起動 → 動作した時は inline コメントを post (現状は前述の仕様で空のまま終わるケースが多い)
3. **内容を見てユーザーが手動で merge**

### (参考) チーム repo で Branch Protection を効かせる場合

将来 claude-forge 構成を team repo に流用する時の reference として、効かせる場合の設定例を残しておく:

```sh
gh api -X PUT /repos/<OWNER>/<REPO>/branches/main/protection --input - <<'EOF'
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

- 人間のチームメイトが review/approve する文化があるリポジトリではこの設定が有効
- Claude bot に approve を担わせる前提なら、加えて workflow の `with:` に `settings: '{"permissions":{"allow":["Bash(gh:*)"]}}'` 追加 + `Bash(gh pr review:*)` 許可が必要 (未検証、別途 debug が必要)
- Free プランの **private repo では Branch Protection / Rulesets が使えない**。public または GitHub Pro が前提

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

そのリポジトリの cwd で Claude Code を起動して **「この repo にも PR レビュー入れて」** と言うと `install-pr-reviews` skill が発火し、workflow 2 ファイルのコピー + `claude-review` ラベル作成 + GitHub App / secret 設定の案内まで一気にやってくれる。明示的に呼びたい時は `/install-pr-reviews` でも OK。
