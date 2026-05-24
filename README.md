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

`.github/workflows/` に 2 つの workflow を置いている:

| Workflow | 役割 |
|---|---|
| `claude-review.yml` | PR opened/synchronize で Claude が一般レビュー (正しさ / 可読性 / テスト / パフォーマンス) を inline コメント |
| `claude-security-review.yml` | 同 trigger で Claude がセキュリティ専用レビュー (OWASP / secret / 認可 / 暗号誤用 / 依存脆弱性) を inline コメント |

### 自分の repo (claude-forge) で動かすには

GitHub repo の Secrets に `CLAUDE_CODE_OAUTH_TOKEN` を登録する:
```sh
claude setup-token        # OAuth token を発行
gh secret set CLAUDE_CODE_OAUTH_TOKEN -R issei-base/claude-forge   # 貼り付け
```
これで次の PR から自動でレビューが走る。

### 他の repo にも入れるには

別の repo の中で:
```
/install-pr-reviews
```
を実行すると `.github/workflows/` に 2 つの yml がコピーされる。その後同様に `gh secret set CLAUDE_CODE_OAUTH_TOKEN` を実行。
