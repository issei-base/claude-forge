---
name: create-pr
description: "変更をコミットして GitHub PR を作成する自動化エンジン。ブランチ作成→ステージング→コミット→push→PR 作成→CI 自動修正ループまでをユーザ確認なしで一括実行する。以下の場合に使用: (1) 「/create-pr」と明示的に呼ばれた場合 (2) implement-issue / fix-pr など他スキルから PR 作成を委譲された場合。コミットメッセージを確認しながらインタラクティブに PR を出したい場合は ship スキルを使う。単にコミットだけ・push だけしたい場合は使わない。"
argument-hint: "[branch] [commit-message]"
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(grep:*), Bash(git status:*), Bash(git diff:*), Bash(git branch:*), Bash(git stash:*), Bash(git pull:*), Bash(git checkout:*), Bash(git rev-parse:*), Bash(git add:*), Bash(git commit:*), Bash(git push:*), Bash(gh repo view:*), Bash(gh pr view:*), Bash(gh pr create:*), Bash(gh pr comment:*), Bash(gh pr checks:*), Bash(gh run list:*), Bash(gh run view:*), Bash(sleep:*), Bash(timeout:*), Bash(terraform fmt:*), Bash(terraform validate:*), Bash(terraform plan:*), Bash(prettier:*), Bash(npx prettier:*), Bash(eslint:*), Bash(npx eslint:*), Bash(ruff:*), Bash(golangci-lint:*)
---

# Create PR

変更のコミットから GitHub PR 作成までを一括で行う自動化エンジン。
**全ステップを自動で実行し、ユーザに確認を求めず PR URL を返す。**

> **ship との使い分け:** 対話的に (コミットメッセージを見せて承認してもらいながら) PR を出すなら `ship`。本スキルは「止まらずに PR まで作る + CI 失敗を自動修正する」エンジンで、主に implement-issue / fix-pr から委譲される。

## Usage

```
/create-pr [オプション引数]
```

引数が渡された場合は以下の形式で解釈する：
- `<ブランチ名> <コミットメッセージ> [PRタイトル] [PR説明]`
- 省略時はコンテキストから自動判断

## ワークフロー

```
1. 状態確認
2. ブランチ整備（必要に応じて）
3. 変更ステージング・コミット
4. プッシュ
5. PR作成
6. CI検証＋自動修正ループ（最大3サイクル）
6.5. Codex 応答ループ（§4 参照・最大2サイクル）
7. 完了報告（PR URL と CI 状況を返す）
```

全ステップをユーザ介入なしで完了させること。

## 🚫 絶対に守るルール（claude-forge 共通方針）

- **main / master / default branch に直接 push してはいけない。例外なし。** push する前に必ずカレントブランチが default でないことを確認する。
- **コミットメッセージと PR タイトルは日本語で書く。** 英語にしない (claude-forge 方針)。
- **`gh pr merge` を実行しない。** merge は人間が手動で行う。
- **Co-Authored-By を付与しない。**
- `git add .` / `git add -A` を使わない。**変更ファイルを明示パス指定で stage** する。

## Step 1: 状態確認

```bash
git status
git diff --stat
git branch --show-current
gh repo view --json defaultBranchRef -q .defaultBranchRef.name
```

以下を把握する：
- 変更されたファイル一覧
- 現在のブランチ名
- デフォルトブランチ名（main or master）

**中断条件：** 変更がない場合はユーザに報告して終了。

## Step 2: ブランチ整備

### 現在がデフォルトブランチの場合

作業ブランチに切り替える（**default branch のままコミット/push しない**）。

```bash
git stash
git pull origin <デフォルトブランチ>
git checkout -b <ブランチ名>
git stash pop  # stashに変更がある場合のみ
```

ブランチ名が引数で指定されていない場合は、変更内容から自動生成する。
命名規則: `<prefix>/yyyymmdd-<内容の要約>`（日付は JST）
- prefix: feat / fix / refactor / chore / docs

### 既に作業ブランチの場合

そのまま続行。

## Step 3: ステージング・コミット

```bash
git add <変更ファイルのみ>
git commit -m "<コミットメッセージ>"
```

**重要：**
- 変更したファイルのみを `git add` する（`git add .` や `git add -A` は使わない）
- 不要なファイル（.env、credentials、.DS_Store 等）を含めない。secret らしきものが見えたら **STOP してユーザに確認**
- Co-Authored-By は付与しない
- コミットメッセージが引数で指定されていない場合は変更内容から自動生成

### コミットメッセージ規約

リポジトリの CLAUDE.md にコミットメッセージ規約がある場合はそれに従う。
なければ以下のプレフィックスを使用：
- `feat:` - 新機能
- `fix:` - バグ修正
- `refactor:` - リファクタリング
- `chore:` - その他
- `docs:` - ドキュメント

## Step 4: プッシュ

```bash
# push 前の hard guard
branch=$(git rev-parse --abbrev-ref HEAD)
default=$(gh repo view --json defaultBranchRef -q .defaultBranchRef.name)
if [ "$branch" = "$default" ]; then
  echo "ERROR: default branch ($default) への push は禁止"; exit 1
fi
git push -u origin "$branch"
```

non-fast-forward で reject された場合は **STOP**。`--force` / `--force-with-lease` はユーザの明示確認なしに使わない。

## Step 5: PR作成

### 5-1: PRテンプレートの検索

リポジトリにPRテンプレートがあるか確認する。GitHub標準の配置場所を順に探索：

1. `.github/pull_request_template.md`
2. `.github/PULL_REQUEST_TEMPLATE.md`
3. `docs/pull_request_template.md`
4. `pull_request_template.md`（ルート直下）

最初に見つかったテンプレートを使用する。

### 5-2: PR本文作成

**テンプレートがある場合：**
テンプレートの構造（見出し・セクション）を維持し、各セクションを変更内容に基づいて埋める。
コメント（`<!-- -->`）は削除して実際の内容に置き換える。

**テンプレートがない場合：**
以下のデフォルトテンプレートを使用：

```markdown
## Summary
<変更内容の箇条書き（1-3行）>

## Changes
<変更ファイルと各変更の概要（ファイルごと1行で十分）>

## Related
- <Issue URLや関連ドキュメントがあれば記載>
```

### 5-3: 簡潔さの方針（テンプレート有無を問わず適用）

**本文の簡潔さは [`_shared/pr-conventions.md`](../_shared/pr-conventions.md) §1 に従う**（原本: `~/projects/claude-forge/.claude/skills/_shared/pr-conventions.md`）。要点（fallback）:
- **含める**: 意図（なぜ）1-3 行の Summary / 何が変わったかの簡潔な要約（diff で読める詳細は書かない）/ 関連 Issue・ドキュメントへのリンク
- **含めない**: ロールバック手順・検証/進捗チェックリスト・リスク表・レビュー履歴・運用詳細・自明な diff の逐一解説
- **例外**: diff だけでは気付けない非自明な前提だけ `Notes` に要点を。無ければ見出しごと出さない

### 5-4: 投稿前セルフチェック

`gh pr create` を実行する直前に、PR 本文を [`_shared/pr-conventions.md`](../_shared/pr-conventions.md) **§2 のチェックリスト（推敲＋構造）で自己点検**する。create-pr 固有で追加確認するもの:
- [ ] `Notes` セクションが「書くことが無いまま」存在していないか（書くことが無ければ見出しごと削除）
- [ ] テンプレートに含まれていた空セクション（`<!-- -->` のみ等）を見出しごと削除済みか

混入や空セクションが見つかったらこの時点で削除してから `gh pr create` に渡す。

### 5-5: PR作成実行

PR は **draft** で作成する（人間が内容を確認してから ready/merge する claude-forge の方針に合わせる）。

```bash
gh pr create \
  --draft \
  --base <デフォルトブランチ> \
  --assignee @me \
  --title "<PRタイトル>" \
  --body "$(cat <<'EOF'
<PR本文>
EOF
)"
```

Codex GitHub automatic reviews が有効なら追加操作は不要。未設定/不明で one-off review も必要な文脈なら、作成後に:

```bash
gh pr comment <PR URL> --body "@codex review"
```

legacy の `claude-review` ラベルは、その repo が意図して Claude GitHub Actions workflows を使い続けている場合だけ付ける。新規 repo へは標準では付けない。

**重要：**
- `--base` には Step 1 で取得したデフォルトブランチ名（main or master）を必ず指定する。
- `--assignee @me` で PR の所有者を自分にする（UI で明確になる）。
- Issue URL が渡されている場合は、Related セクションに Issue URL を記載する。
- このブランチに既に PR がある（`gh pr view` で取得できる）なら **重複作成しない**。URL を見せて title/body を更新するか判断する。

## Step 6: CI検証＋自動修正ループ

PR 作成後、CI が走る場合は完了まで待ち、FAIL なら自動修正→再 push を最大 3 サイクル繰り返す。

### Step 6-1: CI 起動待ち＆有無確認

push 直後は CI run が登録される前なので 15 秒待ってから確認する。

```bash
sleep 15
gh pr checks <PR URL>
```

`no checks reported` / 空出力ならこの Step をスキップして Step 7 へ。

### Step 6-2: CI 完了待ち（最大15分）

```bash
timeout 900 gh pr checks <PR URL> --watch --interval 30
```

- exit 0 → 全 PASS。Step 7 へ。
- exit 8 → FAIL あり。Step 6-3 へ。
- exit 124 → 15 分タイムアウト。Step 7 の完了報告で「CI 未完了」を明記してユーザに引き継ぐ（PR は維持）。

### Step 6-3: 失敗ログ取得

```bash
gh run list --branch <ブランチ名> --limit 5 --json databaseId,workflowName,conclusion
gh run view <run_id> --log-failed
```

失敗を [`_shared/pr-conventions.md`](../_shared/pr-conventions.md) **§3 の分類表**に沿って自動修正する（Format/Lint・Typecheck/Build・Test 失敗・Terraform validate）。自動修正対象外（設定/env・外部リソース未準備・flaky・シークレット不足）と判断したら Step 6-5 で打ち切ってユーザに報告する。

### Step 6-4: 修正→コミット→push

変更ファイルのみ `git add` し、コミット・push する（Co-Authored-By は付けない）。

```bash
git add <変更ファイルのみ>
git commit -m "fix: address CI failure (<種別>)"
git push origin <ブランチ名>
```

push 後 Step 6-2 に戻る。

### Step 6-5: サイクル上限と打ち切り

- 最大 3 サイクル。
- 3 サイクル消化しても PASS にならない → Step 7 の完了報告に直近の失敗サマリを添えて終了。
- 自動修正不能（外部要因 / 仕様判断が必要 / 種別が「設定/env」等）と判断した時点で即座に Step 7 へ進み、ユーザに引き継ぐ。

## Step 6.5: Codex 応答ループ

draft PR 作成済み・CI ループ通過後、Codex GitHub review の指摘へ自律対応する。
**手順・分類・収束/停止・禁止事項は [`_shared/pr-conventions.md`](../_shared/pr-conventions.md) §4 に従う**（原本: `~/projects/claude-forge/.claude/skills/_shared/pr-conventions.md`）。要点（fallback）:
- Codex のレビューコメントを取得 → 各指摘を「自動修正可 / 要人間判断」に分類 → 自動修正可のみ working tree を直し commit + push → `@codex review` を再依頼。
- 停止: 新規 critical/blocking が 0 / **最大 2 サイクル**（CI の 3 より少なく）/ 残りが要人間判断のみ。残った要人間判断は要約して Step 7 でユーザーに引き継ぐ。
- **禁止**: 指摘を黙らせるためのテスト書き換え・握りつぶし。**ループは ready 昇格も merge もしない（draft のまま）**。force push しない。同意できない指摘は dispute としてコメントし、直さない。

Codex review が無効 / コメントが付かない repo ならこの Step をスキップして Step 7 へ。

## Step 7: 完了報告

作成したPRのURLとCI検証結果をユーザに提示する。

```
PR を作成しました: <PR URL>
- ブランチ: <ブランチ名>
- タイトル: <PRタイトル>
- CI: [全PASS / N サイクル修正後PASS / FAIL（打ち切り）/ タイムアウト / CIなし]
```

CI が PASS 以外で終わった場合は、失敗ジョブ名と直近の失敗概要を 1-3 行で添える。
Step 6.5 で残った要人間判断の Codex 指摘があれば、ここで要約して引き継ぐ（自動で触らない）。
**merge はしない** — Codex GitHub code review / CI の結果をユーザが読んで手動 merge する。

## エラーハンドリング

| 状況 | 対応 |
|------|------|
| 変更なし | ユーザに報告して終了 |
| カレントが default branch | 作業ブランチを切ってから進む（直接 push 禁止） |
| push失敗 | エラー内容を報告 |
| PR作成失敗（gh CLI） | エラー内容を報告 |
| コンフリクト | ユーザに報告して判断を仰ぐ |
| CI 未設定（`no checks reported`） | Step 6 をスキップして Step 7 へ |
| CI が 15 分以内に完了しない | Step 6 を打ち切り、完了報告に「タイムアウト」と明記 |
| CI 失敗が外部要因 / flaky / 設定不足 | 自動修正せず Step 6 を打ち切ってユーザに報告 |
| CI 修正サイクル 3 回消化しても FAIL | Step 7 へ進み、完了報告に直近の失敗サマリを添える |

## 重要事項

1. **default branch へ直接 push しない** - 必ず作業ブランチを切る
2. **変更ファイルのみコミット** - 無関係なファイルを絶対に含めない
3. **Co-Authored-By は付与しない**
4. **`gh pr merge` しない** - merge は人間が手動
5. **全ステップ自動実行** - ユーザに途中確認を求めない（エラー時のみ停止して報告）
6. **テストを passing に書き換えない** - CI 自動修正でテスト失敗を直すときは仕様/実装の正しさを判断する
