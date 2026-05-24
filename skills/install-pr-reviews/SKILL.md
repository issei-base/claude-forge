---
name: install-pr-reviews
description: 現在の cwd の git リポジトリに claude-forge の PR 自動レビュー (Claude PR Review + Claude Security Review) workflow をコピーして有効化する。ユーザーが「この repo にも PR レビュー入れて」「自動レビュー workflow を install して」「他リポジトリにも claude-forge の review を展開」「セキュリティチェックも入れて」など、現在のリポジトリで PR 自動レビューを有効化したい意図を示したときに発動する。claude-forge 自身では既に有効なので、起動するのは別 repo にいる時を前提とする。
---

# install-pr-reviews

claude-forge にある 2 つの GitHub Actions workflow を、**現在の cwd** にある別の git リポジトリの `.github/workflows/` にコピーし、合わせて `claude-review` ラベルの作成 / GitHub App / secret 設定の案内まで行う。

## 手順

### 1. Preflight

並列で確認:
- `git rev-parse --is-inside-work-tree` が true でなければ「git リポジトリで実行してください」と伝えて STOP
- `git remote get-url origin` が github.com を指していなければ STOP（GitHub Actions が動かない）
- claude-forge 本体が `~/projects/claude-forge/.github/workflows/` に存在し、両 yml ファイルが取得可能か確認。無ければ「claude-forge を最新化してください (`cd ~/projects/claude-forge && git pull`)」と伝えて STOP
- 現在 cwd が claude-forge 本体ではないことを確認（claude-forge 自身では既に有効化済み）

### 2. Workflow ファイルのコピー

```sh
mkdir -p .github/workflows
SRC=~/projects/claude-forge/.github/workflows
for f in claude-review.yml claude-security-review.yml; do
  if [ -e ".github/workflows/$f" ]; then
    echo "  [skip] .github/workflows/$f は既に存在"
    # 差分確認のため diff を表示するか、ユーザーに「上書きする?」と確認
    diff "$SRC/$f" ".github/workflows/$f" || true
  else
    cp "$SRC/$f" ".github/workflows/$f"
    echo "  [copy] .github/workflows/$f"
  fi
done
```

既存ファイルがある場合は **絶対に上書きしない**。diff を見せてユーザー判断。

### 3. `claude-review` ラベル作成

ship skill は PR 作成時に `claude-review` ラベルを必須付与し、workflow はそのラベル付き PR でだけ起動する設計。ラベルが repo に未作成だと ship が失敗するので、ここで作成:

```sh
gh label list --json name -q '.[].name' | grep -q '^claude-review$' \
  || gh label create claude-review --color 1F6FEB --description "Claude が自動レビューする PR"
```

### 4. GitHub App インストールの案内

OAuth token 経由で workflow を動かす場合、`Claude Code` GitHub App をその repo に install する必要がある（無いと `Claude Code is not installed on this repository` で fail する）。ユーザーに次を案内:

> https://github.com/apps/claude を開いて Install → このリポジトリを選択（既に他 repo に install 済みなら Settings から対象を追加するだけで OK）

### 5. Secret 設定の案内

Workflow は `CLAUDE_CODE_OAUTH_TOKEN` (推奨) または `ANTHROPIC_API_KEY` を必要とする。次のメッセージを出す:

```
✅ Workflow とラベルをコピー / 作成しました。

次にリポジトリの Secrets に以下のいずれかを登録してください:

【推奨】Pro/Max サブスクリプションを使う:
  1. ローカルで `claude setup-token` を実行 → OAuth token を取得
  2. `gh secret set CLAUDE_CODE_OAUTH_TOKEN` の対話プロンプトに貼り付け
     (★ token はチャットや shell 履歴に絶対残さない)

【代替】Anthropic API key を使う:
  1. console.anthropic.com で API key を作成
  2. `gh secret set ANTHROPIC_API_KEY` に貼り付け
  3. workflow ファイルの `claude_code_oauth_token` 行をコメントアウト、
     `anthropic_api_key` 行を有効化

加えて Branch Protection (or Rulesets) を設定すると、approve 必須 + status
check 必須にできる。詳細は claude-forge README の Branch Protection 節を参照。
```

### 6. Commit 判断はユーザーに任せる

- workflow ファイルは新規 untracked になっているはず
- 「これを commit して PR にしますか？」と聞き、yes なら `ship` skill に渡す形で進める
- no なら untracked のまま残す

⚠️ **その repo の初回 workflow 追加 PR は自分自身をレビューできない**。Anthropic action のセキュリティ機能 (PR の workflow と main の workflow が一致するか検証) で skip される。merge 後の PR から動くようになる旨も必ず案内する。

## 注意

- 既存の workflow に同名ファイルがあったら **絶対に上書きしない**。diff を見せて判断を仰ぐ。
- secret の値は絶対に出力ログに出さない (ユーザーが手動で `gh secret set` / UI で登録)。
- このコマンドは claude-forge 自身では実行しなくてよい (既に入っている)。
