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

3. **`claude-review` ラベルを作成**

   ship skill は PR 作成時に `claude-review` ラベルを必ず付与し、workflow はそのラベルが付いた PR でだけ起動する。ラベルがリポジトリに未作成だと ship が失敗するので、ここで作成:

   ```sh
   gh label list --json name -q '.[].name' | grep -q '^claude-review$' \
     || gh label create claude-review --color 1F6FEB --description "Claude が自動レビューする PR"
   ```

4. **GitHub App のインストール案内**

   OAuth token 経由で動かす場合、`Claude Code` GitHub App を該当リポジトリに install する必要がある (これが無いと `Claude Code is not installed on this repository` で fail する)。ユーザーに案内:

   > https://github.com/apps/claude を開いて Install → このリポジトリを選択

   既に他のリポジトリに install 済みであれば、Settings から対象 repo を追加するだけで OK。

5. **secret 設定の案内**

   Workflow は `CLAUDE_CODE_OAUTH_TOKEN` (推奨) または `ANTHROPIC_API_KEY` を必要とする。次のメッセージを出す:

   ```
   ✅ Workflow とラベルをコピー/作成しました。

   次に、リポジトリの Secrets に以下のいずれかを登録してください:

   【推奨】Pro/Max サブスクリプションを使う:
     1. ローカルで `claude setup-token` を実行 → OAuth token を取得
     2. `gh secret set CLAUDE_CODE_OAUTH_TOKEN` の対話プロンプトに貼り付け
        (★ token はチャットや shell 履歴に絶対残さない)

   【代替】Anthropic API key を使う:
     1. console.anthropic.com で API key を作成
     2. `gh secret set ANTHROPIC_API_KEY` に貼り付け
     3. workflow ファイルの `claude_code_oauth_token` 行をコメントアウト、
        `anthropic_api_key` 行を有効化

   設定後、ship skill で PR を作るとラベルが付き、自動レビューが走ります。
   ```

6. **commit するかは聞く**
   - workflow ファイルは新規 untracked になっているはず。
   - 「これを commit して PR にしますか？」と聞き、yes なら [[ship]] skill に渡す形で進める。no なら untracked のまま残す。
   - 注意: **その repo の初回 workflow 追加 PR は自分自身をレビューできない** (Anthropic action のセキュリティ機能で、main にある workflow と差分があると skip される)。merge 後に動くようになる旨を必ず案内。

## 注意

- 既存の workflow に同名ファイルがあったら **絶対に上書きしない**。
- secret の値は絶対に出力ログに出さない (ユーザーが手動で gh secret set / UI で登録)。
- このコマンドは claude-forge 自体には実行しないでよい (既に入っている)。
