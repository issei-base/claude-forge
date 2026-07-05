---
name: implement-issue
argument-hint: "[issue-url | doc-path]"
description: "GitHub IssueのURLまたはドキュメントパスを受け取り、要件分析→コードベース調査→実装→レビューサイクル→PR作成までを自動で行うスキル。issue の作業開始（着手）の既定の入口。「このissueに着手して」「issueやって」のように issue を渡して作業を始めるよう指示されたらこれを使う（内部で実装計画を出しユーザ確認してから実装に入るので、いきなり暴走しない）。以下の場合に使用: (1) GitHub Issue URLを渡されて「実装して」「これやって」「着手して」「取り掛かって」「やり始めて」「対応して」と依頼された場合 (2) ドキュメントパスを渡されて「実装して」と依頼された場合 (3) 「/implement-issue」と呼び出された場合 (4) Issue URLやドキュメントを渡されて実装からPR作成までを一気通貫で依頼された場合。明示的に「計画だけ」「設計だけ」「調査だけ」を求められた場合は実装に入らず [[plan-issue]] / [[spike]] を使う。"
---

# Implement Issue

GitHub IssueのURLまたはドキュメントパスを入力として、要件理解→実装→レビュー→PR作成までを自動で遂行する。
**実装計画のユーザ確認以外は、全フェーズを自動で完了させる。途中で止まらない。**

## Usage

```
/implement-issue <Issue URL or ドキュメントパス>
```

## ワークフロー全体像

**この一覧をレスポンスにコピーし、各 Phase を完了するたびにチェックを入れて進める**（Phase 4 の worktree 作成前にコードを触らない安全ステップを飛ばさないため）:

```
- [ ] Phase 1: 入力判定・要件取得
- [ ] Phase 2: 対象リポジトリ特定
- [ ] Phase 3: コードベース調査
- [ ] Phase 4: Git準備（worktree作成） ← コード変更前に必ず完了させる
- [ ] Phase 5: 実装計画策定・提示（停止せず即Phase 6へ）
- [ ] Phase 6: コード実装
- [ ] Phase 7: レビュー→修正サイクル（最大5回）
- [ ] Phase 8: PR作成（create-pr スキルを Skill tool で呼び出す）
- [ ] Phase 9: 完了報告
```

## 最重要ルール

**コード変更は必ずworktree上で行う。**
Phase 4（Git準備）が完了するまで、一切のファイル編集を行わないこと。
これを怠るとmainブランチを直接変更する事故が起きる。
worktreeを使うことで、元の作業ディレクトリに影響を与えずに実装を進められる。

## Phase 1: 入力判定と要件取得

引数の形式から入力タイプを自動判定する。

### Issue URLの場合

GitHubのURLパターン（`github.com/*/issues/*`）を検出したらIssue URLとして扱う。

```bash
gh issue view <URL> --json title,body,labels,assignees,milestone,comments
```

取得した情報から以下を整理：
- 要求されている機能・修正の概要
- 受け入れ条件（Acceptance Criteria）
- 技術的なキーワード・制約
- 関連Issue・PRへの言及
- **対応方針がコメントに書かれている場合はそれを優先採用する**（plan-issue で投稿した計画コメントがあれば最優先）

### ドキュメントパスの場合

指定ファイルを読み込み、以下を抽出：
- 目的・背景
- 機能要件・非機能要件
- 技術仕様（API、データ構造、インフラ等）
- 制約条件
- 対象ファイル/ディレクトリ

### 要件の曖昧さへの対応

要件が明らかに不足・矛盾している場合のみユーザに質問する。
質問する場合は最小限にまとめ、提案を添える。
曖昧さが軽微なら、合理的な判断で進めてPhase 5の計画に明記する。

## Phase 2: 対象リポジトリ特定

Issueのリポジトリがそのまま実装先とは限らない（例: タスク管理用 Issue だが実装先は別リポジトリ）。

**Step 2-1: カレントディレクトリの確認（最初に必ず実施）**

```bash
pwd
git rev-parse --is-inside-work-tree 2>/dev/null && git remote -v
```

- Gitリポジトリである → リモートURLからリポジトリ名を取得し、対象リポジトリの候補とする
- Gitリポジトリでない → Step 2-2へ

**Step 2-2: 対象リポジトリの特定（優先順）**

1. Issue本文・コメントに対象リポジトリやURLの記載がある → そのリポジトリ
2. ドキュメントパスが指定されている → そのファイルが属するリポジトリ
3. Step 2-1でカレントディレクトリがGitリポジトリだった → そのリポジトリ
4. 上記で判断できない → ユーザに確認

**Step 2-3: ローカルリポジトリの探索（クローン前に必ず実施）**

カレントディレクトリが対象リポジトリそのものであれば、そのまま使用する。
そうでない場合は `~/projects/` 配下に既にクローンされていないか確認する。

```bash
ls ~/projects/<リポジトリ名> 2>/dev/null
```

- カレントディレクトリが対象リポジトリ → そのまま使用
- `~/projects/<リポジトリ名>` に存在する → そのディレクトリを使用（`cd` して default branch を最新化）
- どちらにもない → `gh repo clone <owner>/<repo> ~/projects/<リポジトリ名>` でクローン

**複数リポジトリが対象の場合：**
Phase 4〜8 をリポジトリごとに繰り返す。完了報告（Phase 9）は全リポジトリ分をまとめて行う。

```bash
cd <リポジトリパス>
```

## Phase 3: コードベース調査

Agent tool（`subagent_type: Explore`）で並列調査を行う。

**調査項目：**
- 変更対象のファイル・クラス・関数の特定
- 既存の類似実装パターン
- 影響を受ける依存コード（呼び出し元、テスト等）
- 設定ファイルやDB変更の必要性
- プロジェクトのコーディング規約・パターン（CLAUDE.md含む）
- リポジトリのコミットメッセージ規約

## Phase 4: Git準備（worktree作成）

**このPhaseはPhase 6（コード実装）の前に必ず完了させること。**

### worktreeによる作業ディレクトリ作成

元のリポジトリを汚さず、isolated な環境で実装を進めるためworktreeを使用する。

```bash
# デフォルトブランチ特定・最新化
DEFAULT_BRANCH=$(git remote show origin | grep 'HEAD branch' | awk '{print $NF}')
git checkout $DEFAULT_BRANCH
git fetch origin && git pull origin $DEFAULT_BRANCH

# ブランチ名を決定（日付はJSTベース yyyymmdd形式）
BRANCH_NAME="<prefix>/yyyymmdd-<issue番号>-<機能名>"

# worktree作成（リポジトリのルートと同階層に配置）
REPO_ROOT=$(git rev-parse --show-toplevel)
WORKTREE_DIR="${REPO_ROOT}/../worktrees/$(echo $BRANCH_NAME | tr '/' '-')"
git worktree add -b "$BRANCH_NAME" "$WORKTREE_DIR" "$DEFAULT_BRANCH"

# worktreeに移動
cd "$WORKTREE_DIR"
```

**ブランチ命名規則：**
- `feat/yyyymmdd-<issue番号>-<機能名>` - 新機能
- `fix/yyyymmdd-<issue番号>-<内容>` - バグ修正
- `refactor/yyyymmdd-<issue番号>-<対象>` - リファクタリング
- `chore/yyyymmdd-<issue番号>-<内容>` - その他

Issue番号がない場合（ドキュメント入力時）は番号部分を省略。

### worktree作成の確認

```bash
pwd  # worktreeディレクトリにいることを確認
git branch --show-current  # 作業ブランチであることを確認
```

**以降のPhase 5〜8はすべてworktreeディレクトリ内で実行する。**

### 4.5 着手したら In Progress に（アサイン＋ラベル＋board）

着手時に対象 Issue を「進行中」にする:
- **アサイン**: 自分をアサインする（`gh issue edit <番号> --repo <owner/repo> --add-assignee @me`。既に自分がアサイン済みなら no-op）。
- **ラベル**: `in progress` ラベルを付与（`gh issue edit <番号> --repo <owner/repo> --add-label "in progress"`。ラベルが無ければ作成する）。
- **board**（リンク済み Project に Status フィールドがある場合）: Status を `In Progress` に（projectV2 GraphQL: `addProjectV2ItemById`→`updateProjectV2ItemFieldValue`、要 `project` スコープ）。board/scope が無ければ skip し、その旨を完了報告に明記。

## Phase 5: 実装計画策定・提示

以下を整理しユーザに提示する。**ただし承認待ちで停止せず、そのままPhase 6に進む。**
ユーザが計画に問題を感じた場合は割り込みで修正指示を出す想定。

1. **要件サマリー** - 何を実装するか
2. **変更ファイル一覧** - 新規作成・修正するファイル
3. **実装順序** - 依存関係を考慮した実装ステップ
4. **判断事項** - 曖昧な要件に対する判断とその理由
5. **ブランチ名** - 作成済みのブランチ名

## Phase 6: コード実装

- 既存コードのスタイル・パターンに厳密に従う
- 要件を忠実に実装（過剰な実装をしない）
- セキュリティベストプラクティスを適用
- CLAUDE.mdの指示に従う

## Phase 7: レビュー→修正サイクル

`doc-impl-reviewer` サブエージェントでシニアエンジニアレビューを実施する。

```
Agent tool:
  subagent_type: doc-impl-reviewer
  prompt: |
    以下の実装をレビューしてください。

    仕様: <要件の概要 or ドキュメントパス>
    変更ファイル:
    - <file1>
    - <file2>

    前回レビューの指摘（あれば）: <...>
    イテレーション: N / 5
```

> `doc-impl-reviewer` エージェントが環境に無い場合（スキルだけ別リポジトリにコピーした等）は、本フェーズをスキップして Phase 8 に進む。

**サイクル：**
1. レビューエージェントに変更ファイルと要件を渡す
2. FAIL → 指摘を修正して再レビュー（前回指摘を次の prompt に渡す）。**4 回目以降の FAIL は個別指摘の修正より先に根本設計を疑う**
3. PASS → Phase 8へ（ユーザに確認せず自動で進む）
4. 最大5回で打ち切り（WARN や 5回FAIL でもそのまま Phase 8 に進む。レビュー状況は PR 本文には書かず、完了報告でユーザに伝える）

> 上限が [`fix-pr`](../fix-pr/SKILL.md) の 3 回より多いのは、新規実装はゼロから設計するため指摘が複数観点に及びやすいから（fix-pr は変更スコープが限定的で 3 回で収束しやすい）。

## Phase 8: PR作成・Issueコメント

レビューPASS後、ユーザに確認せず即座に `create-pr` スキルを **Skill tool** 経由で呼び出す。
（`create-pr` はサブエージェントではなく SKILL.md ベースのスキルなので、Agent tool ではなく Skill tool を使う）

```
Skill tool:
  skill: create-pr
  args: |
    リポジトリ: <worktreeパス>
    変更ファイル: <変更ファイルリスト>
    コミットメッセージ: <変更内容に基づくメッセージ>
    PRタイトル: <要件を簡潔に表すタイトル>
    PR説明に含める情報:
      - 要件サマリー
      - 変更ファイルと概要
      - Related: <Issue URL or ドキュメントパス>
```

`create-pr` 側でブランチ作成・コミット・push・PR作成を一括実施するため、本スキルから個別に `gh pr create` 等を叩かないこと。

### IssueへのPRコメント投稿

**入力がIssue URLの場合のみ実行する。** PR作成後、対象IssueにPR URLをコメントとして投稿する。

**投稿前にコメント本文を推敲する**（[`_shared/pr-conventions.md`](../_shared/pr-conventions.md) §2 準拠）: 第三者が見て納得できる最低限の情報量に絞り、冗長な箇条書き・重複説明・蛇足を削る。変更ファイルが多い場合は主要なものに絞り、全列挙はしない。

```bash
gh issue comment <Issue URL> --body "$(cat <<'EOF'
実装PRを作成しました: <PR URL>

### 変更概要
- <変更内容の箇条書き（簡潔に）>

### 変更ファイル
- <主要な変更ファイル>
EOF
)"
```

## Phase 9: クリーンアップ・完了報告

### 完了したら Done に（クローズ＋ラベル＋board）

PR 作成後（実装が一通り終わったら）、対象 Issue を「完了」にする:
- **ラベル**: `in progress` を外し `done` を付与（`gh issue edit <番号> --repo <owner/repo> --remove-label "in progress" --add-label "done"`）。
- **クローズ**: `gh issue close <番号> --repo <owner/repo> --reason completed`。あわせて PR 本文に `Closes #<番号>` を入れておくと merge 時にも自動でクローズされる。
- **board**（§4.5 で更新した場合）: Status を `Done` に。
- merge は人間が別途行う。PR が却下／作り直しになったら issue を reopen し `done`→`in progress` に戻す。

### worktreeのクリーンアップ

PR作成・Issueコメント完了後、元のリポジトリディレクトリに戻る。
worktreeは残しておく（PRがマージされるまで必要になる可能性があるため）。

```bash
cd <元のリポジトリパス>
```

### 完了報告

```markdown
## 実装完了レポート

### 概要
- 入力: [Issue URL or ドキュメントパス]
- リポジトリ: [リポジトリ名]
- ブランチ: [ブランチ名]
- worktree: [worktreeパス]
- PR: [PR URL]
- Issueコメント: [投稿済み / 対象外（ドキュメント入力）]

### 実装内容
- [要件に対して何を実装したかの簡潔な説明]

### 変更ファイル
| ファイル | タイプ | 内容 |
|---------|-------|------|

### レビュー結果
- ステータス: PASS / WARN / 5回FAIL / スキップ
- レビュー回数: N回
```

## エラーハンドリング

| 状況 | 対応 |
|------|------|
| Issue URLが無効 | URLを確認してもらうよう依頼 |
| ドキュメントが見つからない | パスを確認してもらうよう依頼 |
| 対象リポジトリが不明 | ユーザに確認 |
| Git外ディレクトリ | どのリポジトリで作業するかユーザに確認 |
| `doc-impl-reviewer` エージェントが無い | Phase 7 をスキップして Phase 8 へ |
| レビュー5回FAIL | PR作成に進み、完了報告でユーザに伝える（PR本文には記載しない） |
| gh CLI未認証 | 認証手順をガイド |

## 重要事項

1. **worktree作成後にのみコード変更** - Phase 4完了前のファイル編集は厳禁
2. **変更ファイルのみコミット** - 無関係なファイルを含めない（create-pr が担保）
3. **ユーザ介入なしで完走** - 計画を提示しつつ停止せずPR作成・Issueコメントまで自動完了する
4. **最小変更** - 要件に記載された内容のみ実装
5. **Issueリポジトリ≠実装先リポジトリ** - 必ずPhase 2で対象リポジトリを特定する
6. **worktreeで作業** - 元のリポジトリを汚さず、isolatedな環境で実装する
7. **PR作成後にIssueコメント** - Issue URL入力時は必ずIssueにPR URLをコメントする
8. **merge は人間が手動** - 本スキルは PR 作成まで。`gh pr merge` しない
