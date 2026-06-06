---
name: ship
description: 現在の作業を GitHub Pull Request にまで持っていく。必要ならフィーチャーブランチを切り、差分からコミットメッセージと PR タイトル/本文を生成し、push して `gh pr create` で PR を開く。ユーザーが「ship して」「PR出して」「PR作って」「送って」「プルリク」「ship it」「open a PR」「make a PR」「let's ship this」など、現在の変更を PR にしたい意図を示したときに発動する。
allowed-tools: Read, Glob, Grep, Bash(grep:*), Bash(git status:*), Bash(git remote:*), Bash(git log:*), Bash(git branch:*), Bash(git diff:*), Bash(git rev-parse:*), Bash(git checkout:*), Bash(git add:*), Bash(git commit:*), Bash(git push:*), Bash(gh auth status:*), Bash(gh repo view:*), Bash(gh repo create:*), Bash(gh pr view:*), Bash(gh pr create:*), Bash(gh pr comment:*)
---

# ship

「変更を PR まで持っていく」end-to-end ワークフロー。各ステップに STOP 条件あり。違反したら自動回復せず必ずユーザーに見せる。

## 🚫 絶対に守るルール

- **main / master / default branch に直接 push してはいけない。** 例外なし。
- フィーチャーブランチを必ず作成・使用する。これは soft な推奨ではなく hard guard。
- `git push origin main` / `git push origin master` を実行しそうになったら **必ず STOP** してユーザーに確認。

## 0. Preflight (全項目 pass 必須 — 1 つでも失敗したら STOP)

並列で実行:
- `gh auth status` — ログイン必須。未ログインなら `gh auth login` を案内して STOP。
- `git rev-parse --is-inside-work-tree` — true でなければ STOP。
- `git remote -v` — `origin` が github.com を指している必要あり。無ければユーザーに「`gh repo create` する？それとも中止？」と確認。
- `git ls-remote --heads origin` — **出力が空 = リモートにブランチが1本も無い新規 repo**。この場合 PR のベースが存在しないので **ブートストラップが必要**（§1 参照）。`gh repo view --json defaultBranchRef` も空を返すため、後続の default 判定が誤作動する点に注意。
- `git status --porcelain` または `git log @{u}..HEAD 2>/dev/null` — 未コミット変更 OR 未 push コミットのどちらかが存在しなければ「ship するものが無い」と伝えて STOP。
- **巨大 import の検知**: 最後のコミット以降の変更が大きい（多数ファイル）場合、PR が「今回の主目的」だけでなく**過去の未コミット作業を全部含む**ことをユーザーに事前に伝え、スコープを確認する。

## 1. Branch (hard guard)

```sh
current=$(git branch --show-current)
default=$(gh repo view --json defaultBranchRef -q .defaultBranchRef.name)
```

- **`current` が `default` と一致する場合** (= main や master にいる):
  - **絶対にこのブランチで commit/push してはいけない。**
  - `git diff` を見て kebab-case のブランチ名を 3〜6 語で生成。明らかな type prefix があれば付ける: `feat/`, `fix/`, `docs/`, `chore/`, `refactor/`。
  - `git checkout -b <name>` で新ブランチを切る。
- **それ以外**: 現在のブランチをそのまま使う。
- **既存ブランチを rename しない。**

- **`default` が空（= 新規 repo でリモートにブランチが無い）の場合**: PR のベースが存在しないので **ブートストラップ**する。
  1. 確定履歴（未コミット作業を含まない現在の HEAD）を base ブランチ（通常 `main`）として push する必要がある。**これは default branch への push なので必ずユーザーに明示確認**。さらに auto-mode / 権限分類器が `git push origin main` をブロックすることがある → その場合は**ユーザー自身に実行してもらう**（`! git push -u origin main`）。
  2. base が出来たら以降は通常フロー（フィーチャーブランチ → commit → push → PR）。
  - 名前が `main`/`master` のブランチに居る場合は、`default` が空でも **default 扱い**（このブランチで直接 commit/push しない）。

この後どのステップでも、push 先が default branch でないことを `git rev-parse --abbrev-ref HEAD` で再確認すること。

## 2. Stage

- `git status --porcelain` で変更内容を確認。
- 関連ファイルのみ **明示的なパス指定で** stage する。`git add -A` / `git add .` は **絶対禁止** (`.DS_Store`、ログ、IDE 設定ファイルなどを巻き込む)。
- 未 stage のリストに次のいずれかが見えたら **STOP してユーザーに確認**: `.env*`, `*.pem`, `*.key`, `credentials*`, `id_rsa*`, その他 token / secret らしきもの。
- **内容（値）スキャンも必須**（特に初回 push / 巨大 import 時）: stage 済み diff に実シークレット値が無いか確認する。`git diff --cached | grep -nIE 'GOCSPX-|sk-ant-|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|eyJ[A-Za-z0-9_-]{10,}\.|xox[baprs]-|sb_secret_'` 等の高シグナルパターンを検出。1 つでも当たれば **STOP してユーザーに確認**。ファイル名が無害でも、docs / config / サンプルに値が貼られていることがある。
- 無関係な変更が混在していたら、推測せずどれを含めるかユーザーに聞く。

## 3. Commit (未 push コミットのみで ship する場合はスキップ)

**staged diff から** メッセージを生成:
- **Subject**: **日本語**で簡潔に (50 字程度・体言止め or 「〜する」。例:「死参照を修正」「PR 規約を共有ドキュメントに集約」)。**英語にしない** (claude-forge 方針)。末尾の句点無し。
- **Body**: 任意。差分から自明でない *why* を**日本語**で 1〜3 文。trivial な変更ならスキップ。
- commit 前に **必ずメッセージをユーザーに見せて** 編集の機会を与える。
- HEREDOC で commit (フォーマット保持):
  ```sh
  git commit -m "$(cat <<'EOF'
  <subject>

  <body if any>
  EOF
  )"
  ```
- pre-commit hook が失敗したら: 根本原因を fix → 再 stage → **新しい commit** を作成。`--amend` や `--no-verify` は使わない。

## 4. Push (default branch への push は absolute STOP)

```sh
# push する前に必ずチェック
branch=$(git rev-parse --abbrev-ref HEAD)
default=$(gh repo view --json defaultBranchRef -q .defaultBranchRef.name)
if [ "$branch" = "$default" ]; then
  echo "ERROR: default branch ($default) への push は禁止"; exit 1
fi
```

- 新ブランチ: `git push -u origin HEAD`
- 既存ブランチ (upstream あり): `git push`
- non-fast-forward で reject された場合: **STOP**。`--force` / `--force-with-lease` はユーザーの明示確認なしに使わない。

## 5. PR

- base branch 解決: `gh repo view --json defaultBranchRef -q .defaultBranchRef.name`
- このブランチの **全コミット** からコンテキストを集める:
  - `git log <base>..HEAD --pretty=format:'%s%n%n%b'`
  - `git diff <base>...HEAD --stat`
- **Title**: **日本語**で 70 文字以内 (英語にしない)。最新/主要 commit subject に揃えることが多い。複数 commit なら umbrella な要約を。
- **Body** はこの構造:
  ```
  ## Summary
  - <1〜3 個の bullet。何が変わって何のため>

  ## Test plan
  - [ ] <検証方法>
  ```
- **Assignee**: `--assignee @me` でユーザー自身を assignee に設定する (PR の所有者が UI で明確になる)。
- HEREDOC で create:
  ```sh
  gh pr create --base <base> --assignee @me --title "<title>" --body "$(cat <<'EOF'
  ## Summary
  - ...

  ## Test plan
  - [ ] ...
  EOF
  )"
  ```
- このブランチに既に PR がある (`gh pr view` で取得できる) なら **重複作成しない**。URL を見せて title/body を更新するか確認。
- PR レビューは Codex GitHub code review を標準にする。repository-wide automatic reviews が有効なら追加操作は不要。
- automatic reviews が有効か不明で、ユーザーが one-off review も望む場合のみ、PR 作成後に次を実行する:
  ```sh
  gh pr comment <PR URL> --body "@codex review"
  ```
- legacy の `claude-review` ラベルは、その repo が意図して Claude GitHub Actions workflows を使い続けている場合だけ付ける。新規 repo へは標準では付けない。

## 6. 報告

- PR URL を **1 行で** 出力 (ターミナルで clickable になるように)。
- Codex review が automatic / `@codex review` / 未依頼のどれかを明記する。
- Review コメントは **参考情報**。claude-forge では Branch Protection 無しの運用なので、ユーザーが内容を見て自分で merge ボタンを押す (他リポジトリで Branch Protection を有効化している場合は、その条件に従って判断)。
- 自動 merge、追加 push はしない。**merge は必ずユーザーが手動で行う方針**。ここで終了。

## やってはいけないこと

- `git push --force` をユーザーの明示確認なしに実行。
- **`gh pr merge` を絶対に実行しない。** merge はユーザーがレビュー結果を読んだ上で手動で行う。ユーザーが明示的に「merge して」と言わない限り絶対やらない。
- 失敗した hook を `--amend` で「修正」する。新 commit を作る。
- `--no-verify` / `--no-gpg-sign` で hook / 署名をスキップ (ユーザー明示要求がない限り)。
- `.env`、key file、その他 secret パターンを commit する。
- `git add -A` / `git add .` で雑に stage する。**必ず明示パス指定。**
- **main / master / default branch に直接 push する。**
