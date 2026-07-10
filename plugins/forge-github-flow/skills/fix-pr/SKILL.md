---
name: fix-pr
argument-hint: "[pr-url] [修正内容]"
description: "既存のGitHub PRをworktree上で修正し、PR本文と関連Issueコメントまで一括で更新するスキル。PR URLとともに修正依頼を受け取り、ローカルworktreeの探索／不在ならworktree作成→コード修正→push→PR本文の全面更新→Issueコメント編集まで自動で完走する。以下の場合に使用: (1) PR URLを渡されて「PR修正して」「PRに○○を追加して」「レビュー指摘対応して」と依頼された場合 (2) 「/fix-pr」と呼び出された場合 (3) 他のスキル（PRレビュー結果対応等）から委譲された場合 (4) PR URLとともに変更内容・修正方針を渡されて反映を依頼された場合。新規PR作成には使用しない（新規は自動なら [[create-pr]]・対話的に確認しながらなら [[ship]]）。PR本文だけを書き換える単純編集にも使用しない。"
allowed-tools: Read, Write, Edit, Glob, Grep, Skill, Agent, Bash(git:*), Bash(gh pr view:*), Bash(gh pr edit:*), Bash(gh pr checks:*), Bash(gh repo clone:*), Bash(gh run list:*), Bash(gh run view:*), Bash(gh issue view:*), Bash(gh issue comment:*), Bash(gh api:*), Bash(sleep:*), Bash(timeout:*), Bash(ls:*), Bash(awk:*), Bash(tr:*), Bash(terraform fmt:*), Bash(terraform validate:*), Bash(terraform plan:*), Bash(prettier:*), Bash(npx prettier:*), Bash(eslint:*), Bash(npx eslint:*), Bash(ruff:*), Bash(golangci-lint:*)
---

# Fix PR

既存PRに対して、worktree上でコード修正を行い、PR本文と関連Issueコメントを最新状態に同期させるスキル。
**全フェーズを自動実行し、ユーザ介入なしで完走する。途中で承認待ちをしない。**

> **PR 系 skill の使い分け:** この `fix-pr` は**既存 PR**（PR URL）を worktree で直す専用。**新規 PR** を作るなら、対話的には [`ship`](../ship/SKILL.md) / 自動・委譲では [`create-pr`](../create-pr/SKILL.md) を使う。

## Usage

```
/fix-pr <PR URL> [修正内容の説明]
```

引数：
- `<PR URL>` — 必須。修正対象のGitHub PR URL（`github.com/<owner>/<repo>/pull/<number>`）
- `[修正内容の説明]` — 任意。会話文脈から推定できる場合は省略可

## ワークフロー全体像

**この一覧をレスポンスにコピーし、各 Phase を完了するたびにチェックを入れて進める**（Phase 3 の worktree 確立前にコードを触らない安全ステップを飛ばさないため）:

```
- [ ] Phase 1: PR情報取得
- [ ] Phase 2: 対象リポジトリ特定
- [ ] Phase 3: worktree探索 or 作成（コード変更前に必ず完了）
- [ ] Phase 4: 修正方針の整理
- [ ] Phase 5: コード修正
- [ ] Phase 6: レビュー→修正サイクル（最大3回）
- [ ] Phase 7: コミット・push
- [ ] Phase 8: CI検証＋自動修正ループ（最大3サイクル）
- [ ] Phase 9: PR本文更新・Issueコメント更新
- [ ] Phase 10: 完了報告
```

## 最重要ルール

**コード変更は必ずworktree上で行う。**
Phase 3が完了するまでファイル編集を一切行わないこと。
カレントディレクトリのままbranchをcheckoutして編集すると、進行中の他作業を破壊する可能性がある。

その他の安全ルール（force push / `gh pr merge` / `git add -A` / Co-Authored-By / 日本語 commit・PR）は [`_shared/pr-conventions.md`](../_shared/pr-conventions.md) **§0 が唯一の定義**。

## Phase 1: PR情報取得

PR URLから必要な情報を取得する。

```bash
gh pr view <PR URL> --json number,title,body,headRefName,baseRefName,headRepository,headRepositoryOwner,url,state,closingIssuesReferences,comments
```

取得情報：
- `headRefName` — PRのブランチ名（worktree探索のキー）
- `baseRefName` — マージ先ブランチ
- `title` / `body` — 現在のPRタイトル・本文（全面更新時の参照用）
- `closingIssuesReferences` — 関連Issue（`Closes #123` 等で紐づけられたもの）
- `state` — PRがopenかどうか確認。closed/mergedなら中断してユーザに報告

**中断条件：** PRがclosed/merged、URL不正、認証エラー等の場合はユーザに報告して終了。

## Phase 2: 対象リポジトリ特定

PR URL から `owner/repo` を抽出し、[`_shared/pr-conventions.md`](../_shared/pr-conventions.md) **§6** の手順（カレント確認 → `~/projects/<リポジトリ名>` 探索 → 無ければ `gh repo clone`）でローカルを準備する。default branch の最新化は不要（Phase 3 で PR ブランチの worktree に入るため）。

## Phase 3: worktree探索 or 作成

**このPhaseの完了前にファイル編集を行わないこと。**

### Step 3-1: 既存worktreeを探索

```bash
git worktree list
```

出力からPRのブランチ名（Phase 1の `headRefName`）に一致するworktreeを探す。

```bash
WORKTREE_DIR=$(git worktree list --porcelain | awk -v branch="refs/heads/<headRefName>" '
  /^worktree / {wt=$2}
  $0 == "branch " branch {print wt}
')
```

### Step 3-2: 既存worktreeがある場合

そのworktreeに移動し、リモートの最新状態と同期する。

```bash
cd "$WORKTREE_DIR"
git fetch origin <headRefName>
git status  # ローカル変更が残っていないか確認
git pull --ff-only origin <headRefName>
```

**ローカル変更が残っている場合：** ユーザに報告し、続行可否を確認する（自動でstash/破棄しない）。

### Step 3-3: 既存worktreeがない場合

リモートからブランチを取得し、新規worktreeを作成する（リポジトリと同階層の `worktrees/` に置く）。

```bash
git fetch origin <headRefName>

REPO_ROOT=$(git rev-parse --show-toplevel)
WORKTREE_DIR="${REPO_ROOT}/../worktrees/$(echo <headRefName> | tr '/' '-')"

git worktree add "$WORKTREE_DIR" <headRefName>
cd "$WORKTREE_DIR"
```

### Step 3-4: 作業環境の確認

```bash
pwd
git branch --show-current
git log --oneline -5
```

worktreeディレクトリにいること、ブランチが `headRefName` と一致していることを確認する。
**以降のPhase 4〜8はすべてworktreeディレクトリ内で実行する。**

## Phase 4: 修正方針の整理

会話文脈・引数・PRコメント・関連Issueコメントから、何を修正するかを整理する。

### 修正内容の入手元（優先順）

1. ユーザがこの呼び出しで明示的に指示した内容
2. PRレビューコメント（`gh pr view --json reviews,comments`）— ユーザが「レビュー指摘対応して」と言った場合
3. 関連Issueの新規コメント — ユーザが「Issueに追記された内容を反映して」と言った場合

### 整理項目

- 何を変えるか（機能追加 / バグ修正 / リファクタ / レビュー指摘対応）
- 影響範囲（変更ファイル候補）
- 既存PRとの整合性（PR本文に書かれた方針からのズレが生じないか）

要件が不明瞭な場合のみユーザに最小限の質問を行う。軽微な曖昧さは合理的判断で進める。

## Phase 5: コード修正

worktreeディレクトリ内で修正を実施する。

- 既存コードのスタイル・パターンに従う
- 既存の実装に対するピンポイント修正に留め、関係ない箇所まで広げない
- CLAUDE.mdの指示（リポジトリ／プロジェクト両方）に従う
- 不要なドキュメント・コメントを追加しない

## Phase 6: レビュー→修正サイクル

`doc-impl-reviewer` サブエージェントでシニアエンジニアレビューを実施する。

```
Agent tool:
  subagent_type: doc-impl-reviewer
  prompt: |
    以下のPR修正をレビューしてください。

    PR: <PR URL>
    仕様 / 修正方針: <Phase 4 で整理した方針>
    変更ファイル:
    - <file1>
    - <file2>

    前回レビューの指摘（あれば）: <...>
    イテレーション: N / 3
```

> `doc-impl-reviewer` エージェントが環境に無い場合（スキルだけ別リポジトリにコピーした等）は、本フェーズをスキップして Phase 7 に進む。

**サイクル：**
- FAIL → 指摘を修正して再レビュー（前回指摘を次の prompt に渡す）
- PASS → Phase 7 へ進む
- 最大3回で打ち切り（WARN や 3回FAIL でもそのまま Phase 7 へ。レビュー状況は完了報告でユーザに伝える）

PR修正は新規実装より変更スコープが小さいため、サイクル上限は implement-issue（5回）より少なく設定している。

## Phase 7: コミット・push

> **Codex レビュー**: 非対話 skill なので要否の確認は挟まない。ユーザーが「codex レビューも」と**明示した時だけ**、ここ（push 前）で [`codex-secondopinion`](../codex-secondopinion/SKILL.md) を **Phase 1(review) + Phase 2(triage) までで** 1 回実行する（Phase 3 の GO 待ちには入らせない。[`_shared/pr-conventions.md`](../_shared/pr-conventions.md) §4 が唯一の定義）。triage 結果は Phase 10 の報告に添える（自動では直さない）。**push 後の `@codex review` / Codex 応答ループは廃止済み**（2026-07 方針転換）。push 前の自己検証は Phase 6 のローカル `doc-impl-reviewer` ループが担う。

```bash
git status
git diff --stat
git add <変更ファイルのみ>
git commit -m "<コミットメッセージ>"
git push origin <headRefName>
```

**重要：**
- 変更したファイルのみ `git add` する（`git add .` / `-A` は使わない）
- 不要ファイル（.env、credentials等）を含めない
- Co-Authored-Byは付与しない
- コミットメッセージは**日本語**で書く（リポジトリ規約があれば優先）。なければ `feat: / fix: / refactor: / chore:` プレフィックス + 日本語の説明

**force pushはユーザの明示指示がない限り行わない。** rebase等で必要になった場合はユーザに確認する。

## Phase 8: CI検証＋自動修正ループ

push 後に CI が走る場合は完了まで待ち、FAIL なら自動修正→再 push を最大 3 サイクル繰り返す。
worktree ディレクトリにいる前提で実行する（Phase 3 で確立済み）。

### Step 8-1: CI 起動待ち＆有無確認

**起動待ち・検出は [`_shared/pr-conventions.md`](../_shared/pr-conventions.md) §5 が唯一の定義**（ship / create-pr と同一）。要点（fallback）: **15 秒 1 回の `no checks reported` で「CI なし」を確定しない**（後発 CI を取りこぼす）。worktree ディレクトリ内で 15 秒間隔・最大 ~90 秒 polling する。

```bash
for _ in $(seq 1 6); do
  gh pr checks <PR URL> 2>/dev/null | grep -q . && break
  sleep 15
done
gh pr checks <PR URL>
```

check が最後まで 1 つも現れなければこの CI Phase をスキップして Phase 9 へ。現れたら Step 8-2 の完了待ちへ。

### Step 8-2: CI 完了待ち（最大15分）

```bash
timeout 900 gh pr checks <PR URL> --watch --interval 30
```

- exit 0 → 全 PASS。Phase 9 へ。
- exit 8 → FAIL あり。Step 8-3 へ。
- exit 124 → 15 分タイムアウト。Phase 10 の完了報告で「CI 未完了」を明記してユーザに引き継ぐ（worktree/PR は維持）。

### Step 8-3: 失敗ログ取得

```bash
gh run list --branch <headRefName> --limit 5 --json databaseId,workflowName,conclusion
gh run view <run_id> --log-failed
```

失敗を [`_shared/pr-conventions.md`](../_shared/pr-conventions.md) **§3 の分類表**に沿って自動修正する（Format/Lint・Typecheck/Build・Test 失敗・Terraform validate）。自動修正対象外（設定/env・外部リソース未準備・flaky・シークレット不足）と判断したら Step 8-5 で打ち切ってユーザに報告する。

### Step 8-4: 修正→コミット→push

変更ファイルのみ `git add` し、コミット・push する。Co-Authored-By は付与しない。

```bash
git add <変更ファイルのみ>
git commit -m "fix: address CI failure (<種別>)"
git push origin <headRefName>
```

push 後 Step 8-2 に戻る。

### Step 8-5: サイクル上限と打ち切り

- 最大 3 サイクル。
- 3 サイクル消化しても PASS にならない → Phase 9 へ進み、完了報告に直近の失敗サマリを添えて終了。
- 自動修正不能（外部要因 / 仕様判断が必要 / 種別が「設定/env」等）と判断した時点で即座に Phase 9 へ進み、ユーザに引き継ぐ。

PR 本文・Issue コメント更新は CI 結果に関わらず Phase 9 で実施する（最新コード状態に合わせるため）。

## Phase 9: PR本文更新・Issueコメント更新

push完了後、PR本文と関連Issueコメントを最新状態に同期する。

### Step 9-1: PR本文の全面更新

create-pr スキルと同じ「簡潔さの方針」を遵守して、PR本文を再生成する。
**追記ではなく全面差し替え。** 元の本文の構造（テンプレートに従ったセクション構成）は維持しつつ、内容を最新の差分に合わせて書き直す。

#### PR本文作成ルール

本文の簡潔さは [`_shared/pr-conventions.md`](../_shared/pr-conventions.md) **§1 に従う**（create-pr と同一方針）。要点（fallback）:
- **含める**: 意図（なぜ）1-3 行の Summary / 何が変わったかの簡潔な要約（diff で読める詳細は書かない）/ 関連 Issue・ドキュメントへのリンク
- **含めない**: ロールバック手順・検証/進捗チェックリスト・リスク表・レビュー履歴・運用詳細・自明な diff の逐一解説

#### PRタイトルの扱い

修正内容によって元のPRタイトルが内容と乖離している場合のみタイトルも更新する。
（例: `feat: foo を追加` → 大幅修正で `feat: foo と bar を追加`）
タイトルが依然として妥当ならそのまま据え置く。

#### 投稿前セルフチェック

`gh pr edit` を実行する直前に、PR 本文を [`_shared/pr-conventions.md`](../_shared/pr-conventions.md) **§2 のチェックリスト（推敲＋構造）で自己点検**する。fix-pr は全面更新なので特に「修正分を追記しただけで終わらず既存本文の冗長部も削ったか」を確認する。

#### 実行

```bash
gh pr edit <PR URL> \
  --title "<更新後タイトル>" \
  --body "$(cat <<'EOF'
<更新後PR本文>
EOF
)"
```

タイトルを変えない場合は `--title` を省略する。

### Step 9-2: 関連Issueコメントの編集

PRが Issue と紐づいている場合のみ実施する。
紐づきは Phase 1 で取得した `closingIssuesReferences` から判定する。複数Issueに紐づいている場合は、それぞれに対して以下を実施する。

**紐づくIssueが無い場合はこのStepをスキップする。**

#### 編集対象コメントの特定

implement-issue 等で投稿された「実装PRを作成しました」コメントを編集対象とする。

```bash
gh issue view <Issue URL> --json comments --jq '.comments[] | select(.author.login == "<自分のlogin>") | {id, body, createdAt}'
```

- 「実装PRを作成しました: <PR URL>」を含むコメントを特定する
- 該当コメントが見つからない場合 → 新規コメントとして追加投稿する（Step 9-3）
- 該当コメントが見つかった場合 → そのコメントIDで編集する（Step 9-2 続き）

#### コメント編集

**投稿前にコメント本文も推敲する。** 第三者が見て納得できる最低限の情報量に絞り、冗長な箇条書き・重複説明を削る。

> **`gh api -X PATCH` は permission denied になる可能性がある。** PATCH を1回試して denied なら、**リトライせず即 Step 9-3 の新規コメント追加**にフォールバックする。
>
> なぜ `--edit-last` を使わないか: fix-pr が動くセッションでは、編集対象のコメントは別セッション（implement-issue 等）で投稿されたものを編集するケースがあり、現セッションの最終投稿とは限らないため `--edit-last` ではズレる。

```bash
gh api -X PATCH /repos/<owner>/<repo>/issues/comments/<comment_id> \
  -f body="$(cat <<'EOF'
実装PRを作成しました: <PR URL>

### 変更概要
- <最新の変更内容の箇条書き>

### 変更ファイル
- <変更ファイルリスト>
EOF
)"
```

**全面更新方針：** 元のコメントに追記するのではなく、最新の差分内容に合わせて全体を書き直す。追記モードで冗長になることを避ける。

### Step 9-3: 編集対象コメントが見つからない場合

PRが Issue と紐づいているが、編集対象の既存コメントが特定できない場合は、新規コメントを投稿する。

```bash
gh issue comment <Issue URL> --body "$(cat <<'EOF'
PRを更新しました: <PR URL>

### 変更概要
- <変更内容の箇条書き>

### 変更ファイル
- <変更ファイルリスト>
EOF
)"
```

## Phase 10: 完了報告

worktreeはそのまま残す（PRマージまで再修正に使う可能性があるため）。
カレントディレクトリは worktree のままで構わない（ユーザがどこに戻りたいかは指示されない限り変更しない）。

```markdown
## PR修正完了レポート

### 概要
- PR: <PR URL>
- ブランチ: <headRefName>
- worktree: <WORKTREE_DIR>
- worktree状態: [既存利用 / 新規作成]
- 関連Issue: <Issue URLリスト or なし>

### 修正内容
- <何をどう修正したかの簡潔な説明>

### 変更ファイル
| ファイル | 内容 |
|---------|------|

### 更新内容
- PR本文: [更新済み / 据え置き]
- PRタイトル: [更新済み / 据え置き]
- Issueコメント: [編集済み / 新規投稿 / 対象なし]

### レビュー結果（Phase 6を実行した場合のみ）
- ステータス: PASS / WARN / FAIL
- レビュー回数: N回

### CI 検証結果（Phase 8）
- ステータス: [全PASS / N サイクル修正後PASS / FAIL（打ち切り）/ タイムアウト / CIなし]
- 失敗ジョブと概要: <PASS 以外の場合のみ 1-3 行で記載>

```

## エラーハンドリング

| 状況 | 対応 |
|------|------|
| PR URLが無効 / closed / merged | ユーザに報告して終了 |
| 対象リポジトリ未クローン | `gh repo clone` で取得 |
| worktreeにローカル変更が残っている | ユーザに報告して判断を仰ぐ（勝手にstash/破棄しない） |
| ブランチがリモートに存在しない | URL確認をユーザに依頼 |
| push失敗（fast-forward不可等） | 状況を報告し、force pushの可否をユーザに確認 |
| PR編集失敗 / Issueコメント編集失敗 | エラー内容を報告（コード修正・pushは完了している前提で続行可否を判断） |
| `closingIssuesReferences` が空 | Issueコメント更新Stepはスキップ |
| 編集対象の既存Issueコメントが特定不可 | Step 9-3 で新規コメント投稿に切り替え |
| `doc-impl-reviewer` エージェントが無い | Phase 6 をスキップして Phase 7 へ |
| CI 未設定（`no checks reported`） | Phase 8 をスキップして Phase 9 へ |
| CI が 15 分以内に完了しない | Phase 8 を打ち切り、完了報告に「タイムアウト」と明記 |
| CI 失敗が外部要因 / flaky / 設定不足 | 自動修正せず Phase 8 を打ち切ってユーザに報告 |
| CI 修正サイクル 3 回消化しても FAIL | Phase 9 へ進み、完了報告に直近の失敗サマリを添える |

## 重要事項

1. **worktree作成後にのみコード変更** — Phase 3完了前のファイル編集は厳禁
2. **変更ファイルのみコミット** — 無関係なファイルを含めない
3. **PR本文は全面更新かつ簡潔** — 追記でだらだら伸ばさない（[`_shared/pr-conventions.md`](../_shared/pr-conventions.md) §1 の簡潔さ方針）
4. **Issueコメントは既存編集を優先** — 新規追加投稿は編集対象が無いときだけ
5. **ローカル変更の自動破棄禁止** — worktreeに未コミット変更があった場合は必ずユーザに判断を仰ぐ
6. その他の禁止事項（force push / merge / テスト握りつぶし）は [`_shared/pr-conventions.md`](../_shared/pr-conventions.md) §0 / §3 が唯一の定義
