---
description: 現在の git リポジトリに claude-forge の PR 自動レビュー workflow をインストール
argument-hint: "(引数なし)"
---

# install-pr-reviews

claude-forge が持っている 2 つの GitHub Actions workflow を、**現在の cwd** にある git リポジトリの `.github/workflows/` にコピーする。

## 手順

1. **Preflight**
   - `git rev-parse --is-inside-work-tree` が true でなければ「git リポジトリで実行してください」と伝えて STOP。
   - `git remote get-url origin` が github.com を指していなければ STOP (GitHub Actions が動かない)。
   - source 側 (`~/projects/claude-forge/.github/workflows/claude-review.yml` と `claude-security-review.yml`) の存在確認。無ければ「claude-forge を最新にしてください (`cd ~/projects/claude-forge && git pull`)」と伝えて STOP。

2. **コピー**
   ```sh
   mkdir -p .github/workflows
   SRC=~/projects/claude-forge/.github/workflows
   for f in claude-review.yml claude-security-review.yml; do
     if [ -e ".github/workflows/$f" ]; then
       echo "  [skip] .github/workflows/$f は既に存在"
     else
       cp "$SRC/$f" ".github/workflows/$f"
       echo "  [copy] .github/workflows/$f"
     fi
   done
   ```
   既存ファイルは **上書きしない** こと。差分があるか `diff` で見せて、ユーザーが判断する。

3. **secret 設定の案内**

   Workflow は `CLAUDE_CODE_OAUTH_TOKEN` (推奨) または `ANTHROPIC_API_KEY` を必要とする。次のメッセージを出す:

   ```
   ✅ Workflow をコピーしました。

   次に、リポジトリの Secrets に以下のいずれかを登録してください:

   【推奨】Pro/Max サブスクリプションを使う:
     1. ローカルで `claude setup-token` を実行 → OAuth token を取得
     2. `gh secret set CLAUDE_CODE_OAUTH_TOKEN` (or GitHub UI: Settings → Secrets and variables → Actions)
        に貼り付け

   【代替】Anthropic API key を使う:
     1. console.anthropic.com で API key を作成
     2. `gh secret set ANTHROPIC_API_KEY` に貼り付け
     3. workflow ファイルの `claude_code_oauth_token` 行をコメントアウト、
        `anthropic_api_key` 行を有効化

   secret 設定後、次回 PR を opened/synchronize すると自動でレビューが走ります。
   ```

4. **commit するかは聞く**
   - workflow ファイルは新規 untracked になっているはず。
   - 「これを commit して PR にしますか？」と聞き、yes なら [[ship]] skill に渡す形で進める。no なら untracked のまま残す。

## 注意

- 既存の workflow に同名ファイルがあったら **絶対に上書きしない**。
- secret の値は絶対に出力ログに出さない (ユーザーが手動で gh secret set / UI で登録)。
- このコマンドは claude-forge 自体には実行しないでよい (既に入っている)。
