---
name: implement-issue
argument-hint: "[issue-url | doc-path]"
allowed-tools: Read, Write, Edit, Glob, Grep, WebFetch, WebSearch, Skill, Agent, Bash(git:*), Bash(gh issue view:*), Bash(gh issue edit:*), Bash(gh issue comment:*), Bash(gh issue list:*), Bash(gh label list:*), Bash(gh pr view:*), Bash(gh pr create:*), Bash(gh api:*), Bash(gh repo clone:*), Bash(gh search code:*), Bash(ls:*)
description: "GitHub IssueのURLまたはドキュメントパスを受け取り、要件分析→コードベース調査→実装→レビューサイクル→PR作成までを自動で行うスキル。issue の作業開始（着手）の既定の入口。「このissueに着手して」「issueやって」のように issue を渡して作業を始めるよう指示されたらこれを使う（内部で実装計画を出しユーザ確認してから実装に入るので、いきなり暴走しない）。以下の場合に使用: (1) GitHub Issue URLを渡されて「実装して」「これやって」「着手して」「取り掛かって」「やり始めて」「対応して」と依頼された場合 (2) ドキュメントパスを渡されて「実装して」と依頼された場合 (3) 「/implement-issue」と呼び出された場合 (4) Issue URLやドキュメントを渡されて実装からPR作成までを一気通貫で依頼された場合。明示的に「計画だけ」「設計だけ」「調査だけ」を求められた場合は実装に入らず [[plan-issue]] / [[spike]] を使う。「伴走して」「一緒に進めて」「要所で相談して」と自分を巻き込みながらの進行を求められたら、止まらず完走するこの skill ではなく [[banso]] を使う — Issue URL 付きで「着手して」と併記されていても、相談・伴走の語があれば banso が優先で、この skill は発動しない。"
---

# Implement Issue

GitHub IssueのURLまたはドキュメントパスを入力として、要件理解→実装→レビュー→PR作成までを自動で遂行する。
**実装計画のユーザ確認以外は、全フェーズを自動で完了させる。途中で止まらない。**

> **`_shared/` の読み方:** `_shared/pr-conventions.md` は**この SKILL.md と同階層**の `_shared/` にある。パスを字句的に畳まず `<この SKILL.md のディレクトリ>/../_shared/pr-conventions.md` の形のまま Read する（symlink 経由で届いていても `..` は実体側に解決される）。畳んだパスを組み立て直して Read しない。

## Usage

```
/implement-issue <Issue URL or ドキュメントパス>
```

## ワークフロー全体像

**この一覧をレスポンスにコピーし、各 Phase を完了するたびにチェックを入れて進める**（Phase 4 の worktree 作成前にコードを触らない安全ステップを飛ばさないため）:

```
- [ ] Phase 1: 入力判定・要件取得・着手宣言（Todo ゲート → Issue を In Progress に）
- [ ] Phase 2: 対象リポジトリ特定
- [ ] Phase 3: コードベース調査
- [ ] Phase 4: Git準備（worktree作成） ← コード変更前に必ず完了させる
- [ ] Phase 5: 実装計画策定・提示（テストケース一覧を含む。停止せず即Phase 6へ）
- [ ] Phase 6: テスト先行（red→green）→コード実装
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

### 1.5 着手宣言 — Issue を In Progress にしてから作業に入る（Issue URL の場合のみ）

要件を取得したら、**Phase 2 以降（調査・実装）に入る前に**対象 Issue を「進行中」にする。この手順を後回しにしない — board を見た人が「誰も着手していない」と誤読するのを防ぐのが目的。

「進行中」の表明は **Project board の Status フィールドのみ**で行う。repo に `in progress` 系のラベルが存在しても付けない — Status とラベルの二重管理は必ず食い違い、「Status を動かして」という依頼にラベルで応えると誤りになる。**例外は Phase 3 のコードベース調査で対象 repo の CLAUDE.md にラベル運用が明記されているのを確認できた場合のみ**（§1.5 時点ではまだ CLAUDE.md を読んでいないため判定しない。該当したら Phase 3 後に追ってラベルも付与する）。

**Step 1: アサイン**

```bash
gh issue edit <Issue URL> --add-assignee @me
```

**Step 2: Todo ゲートを通し、Project board の Status を In Progress に**（issue が GitHub Project にリンクされている場合）

```bash
# issue が載っている Project・item・Status フィールド・現在の Status を 1 クエリで取得
gh api graphql -f query='
  query($url:URI!){ resource(url:$url){ ... on Issue { projectItems(first:5){ nodes {
    id
    fieldValueByName(name:"Status"){ ... on ProjectV2ItemFieldSingleSelectValue { name } }
    project { id title
      field(name:"Status"){ ... on ProjectV2SingleSelectField { id options { id name } } } }
  } } } } }' -f url="<Issue URL>"
```

出力の `nodes` が 1 件なら、その `id`（ITEM_ID）/ `project.id`（PROJECT_ID）/ `field.id`（FIELD_ID）と、`options[]` のうち `In Progress` の id（OPT_ID。無い board では Doing 等の最も近い選択肢）を読み取る。**`nodes` が 2 件以上**（複数 Project にリンク）なら、対象 Project の選び方は [`_shared/pr-conventions.md`](../_shared/pr-conventions.md) **§7**「対象 Project が一意に決まらない場合」に従う。

**Todo ゲート** — `fieldValueByName.name`（現在の Status）を [`_shared/pr-conventions.md`](../_shared/pr-conventions.md) **§9** に照らして分岐する:

- 現在が `Todo` 相当 → そのまま In Progress へ（正常系。確認しない）
- 現在が `Backlog` 等それ以外 → **1 回だけ確認する**: 「この issue は今週の Todo に入っていません（現在: `<Status>`）。割り込みとして着手しますか？」。YES なら In Progress へ進め、NO なら着手を中止して weekly-plan での選定を案内する
- **`options[]` に `Todo` 相当が無い board / Project 非リンク** → ゲートごと skip（確認しない）
- **ユーザ応答を待てない文脈**（headless 実行など）→ 確認を省いて続行し、Phase 9 の完了報告に「Todo 外からの着手」と明記する

ID が揃ったら [`_shared/pr-conventions.md`](../_shared/pr-conventions.md) **§7** の共通 mutation（`updateProjectV2ItemFieldValue`）で Status を `In Progress` に更新する。

**skip 条件**（board 更新だけ skip し、完了報告に一言添える）:
- `projectItems` が空 — その repo は Project 運用をしていない
- Status に相当する単一選択フィールドが無い
- token に `project` スコープが無く FORBIDDEN になる（完了報告で `gh auth refresh -s project` を案内する）

**Step 3: メタデータ補完ゲート** — 欠落があれば埋めてから作業に入る

手動作成（Web/モバイル）の issue は create-issue を経由せずメタデータが欠けていることがある。着手はそれを拾う唯一の確実なタイミングなので、Phase 1 で取得済みの `labels` / `milestone` と Step 2 のクエリ結果を突き合わせ、[`_shared/pr-conventions.md`](../_shared/pr-conventions.md) **§8** の必須セット（優先度ラベル・分野ラベル・Milestone・Project の Priority / Type）に欠落があれば補完する:

- ラベル・Milestone は issue 本文から分類して `gh issue edit --add-label` / `--milestone` で設定（体系の読み方・epic ルール・判断がつかない場合の扱いは §8）
- Priority / Type フィールドは Step 2 の逆引きクエリに `fieldValueByName` を足して現在値を確認し、空なら §7 の mutation で設定（Priority は優先度ラベルと同値）
- すべて設定済みなら何もしない（このゲートは補完であり、既存の値を上書きしない）

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

**Step 2-3: ローカルリポジトリの探索と準備**

Step 2-2 で特定した対象リポジトリを、[`_shared/pr-conventions.md`](../_shared/pr-conventions.md) **§6** の手順（カレント確認 → `~/projects/<リポジトリ名>` 探索 → 無ければ `gh repo clone` → default branch を最新化）でローカルに用意する。

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

**このPhaseはPhase 6（テスト先行→コード実装）の前に必ず完了させること。**

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

## Phase 5: 実装計画策定・提示

以下を整理しユーザに提示する。**ただし承認待ちで停止せず、そのままPhase 6に進む。**
ユーザが計画に問題を感じた場合は割り込みで修正指示を出す想定。

**判断事項とテストケース一覧を要件サマリーの直後・冒頭近くに置く。** データモデル・型インターフェース・ユーザーに見える挙動など「ユーザが修正指示を出しそうな判断」ほど先に出し、機械的なリファクタリングや自明な作業は末尾に回す（下記 2. の項目内の並び順もこの基準に従う）。このスキルは停止しないため、割り込みが間に合うかは提示順で決まる。

1. **要件サマリー** - 何を実装するか（1〜3 行。長文化させず、判断事項が冒頭 10 行以内に見えるようにする）
2. **判断事項** - 曖昧な要件に対する判断とその理由
3. **テストケース一覧（自然言語）** - この実装が正しいと言える振る舞いを、正常系・境界・エラー系に分けて 1 行 1 ケースの自然言語で列挙する。Issue の受け入れ条件（完了条件）があれば必ず全て含める。テストコードは書かない — ユーザがこの一覧に割り込みで差し替え・追加できることがこの節の目的で、Phase 6 でこの一覧をそのままテストコードに落とす
4. **変更ファイル一覧** - 新規作成・修正するファイル
5. **実装順序** - 依存関係を考慮した実装ステップ
6. **ブランチ名** - 作成済みのブランチ名

## Phase 6: テスト先行（red→green）→コード実装

**テストを先に書いて落とす:**

1. Phase 5 のテストケース一覧を、repo の既存テストの流儀（ランナー・配置・命名）に従ってテストコードに落とす
2. 実装前に実行し、**新規テストが落ちることを確認する（red）**。落ちない場合はテストが振る舞いを検証できていないので書き直す。例外は**回帰固定テスト**（既に正しく動いている振る舞いをそのまま固定する契約テスト・ゴールデン等）のみ — 落とせないのは失敗ではないので、初回 green の理由を完了報告に明記する
3. 実装を進め、新規テストと既存テストが全て通る（green）まで Phase 6 を完了としない
4. スキップできるのは次の 2 つのみ: (a) テスト基盤が無い repo (b) docs のみ・設定値のみ（コード分岐を伴わない）の変更。見た目の変更でもスナップショット/ビジュアル回帰で検証できる場合はスキップしない。この 2 つ以外を理由にスキップしない。スキップしたら Phase 9 の完了報告に旨と理由を必ず書く

**実装の原則:**

- 既存コードのスタイル・パターンに厳密に従う
- 要件を忠実に実装（過剰な実装をしない）
- セキュリティベストプラクティスを適用
- CLAUDE.mdの指示に従う
- **計画から外れる判断は Deviations（計画からの逸脱）として記録する**（詳細は下記）

計画（Phase 5）から外れる判断をしたら — Phase 6 実装中・Phase 7 レビュー対応中を問わず — 「なぜ計画どおりにいかなかったか / 代わりに何を選んだか」をその場でレスポンス内に箇条書きで残す（ファイルとして repo にコミットしない）。迷う場合は保守的な選択（変更が小さく戻しやすい方）に倒す。蓄積した Deviations は Phase 8 の PR 説明（`Notes` 見出し・[`_shared/pr-conventions.md`](../_shared/pr-conventions.md) §1）と Phase 9 の完了報告に転記する。

## Phase 7: レビュー→修正サイクル

`doc-impl-reviewer` サブエージェントでシニアエンジニアレビューを実施する。

```
Agent tool:
  subagent_type: doc-impl-reviewer
  prompt: |
    以下の実装をレビューしてください。

    仕様: <要件の概要 or ドキュメントパス>
    完了条件・テストケース: <Phase 5 のテストケース一覧（Issue の受け入れ条件を含む）と、各ケースがどのテストで担保されているか（red→green の結果）>
    変更ファイル:
    - <file1>
    - <file2>

    前回レビューの指摘（あれば）: <...>
    イテレーション: N / 5
```

> `doc-impl-reviewer` エージェントが環境に無い場合（スキルだけ別リポジトリにコピーした等）は、本フェーズをスキップして Phase 8 に進む。

**サイクル：**
1. レビューエージェントに変更ファイル・要件・完了条件（テストケース一覧と担保状況）を渡し、「完了条件がテストで担保されているか」も判定対象に含めさせる
2. FAIL → 指摘を修正して再レビュー（前回指摘を次の prompt に渡す）。**4 回目以降の FAIL は個別指摘の修正より先に根本設計を疑う**
3. PASS → Phase 8へ（ユーザに確認せず自動で進む）
4. 最大5回で打ち切り（WARN や 5回FAIL でもそのまま Phase 8 に進む。レビュー状況は PR 本文には書かず、完了報告でユーザに伝える）
5. **5回FAILのまま打ち切った場合は、Phase 8 の create-pr 呼び出しの args に `draft: true（レビュー予算切れFAIL: <未解消指摘の要点1行>）` の行を渡して draft PR として作成する**（レビュー不合格のまま出す成果物を合格品と同じ見た目にしない。ready 昇格は人間が GitHub UI で判断する）。WARN 止まりや PASS は従来どおり ready

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
    draft: <Phase 7 の判定（上記サイクル 5）に従う。該当時のみ「true（レビュー予算切れFAIL: <要点1行>）」を渡し、非該当ならこの行自体を省略>
    PR説明に含める情報:
      - 要件サマリー
      - 変更ファイルと概要
      - Deviations（計画から外れた判断とその理由）があれば Notes 見出しに含める（_shared/pr-conventions.md §1。無ければ見出しごと出さない）
      - Closes #<Issue番号>（Issue 入力で、この PR が Issue を完了させる場合。merge 時の自動 close に必須。**Issue が実装先と別 repo のときは `Closes <owner>/<repo>#<番号>` の完全修飾で書く** — `#<番号>` だけだと実装先 repo の同番号 Issue を指す）
      - Related: <Issue URL or ドキュメントパス>（ドキュメント入力、または Issue の部分対応で完了させない場合）
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

### 完了処理は merge 時の自動連鎖に任せる（skill からは close しない）

- PR 本文の `Closes #<番号>`（Phase 8）により、**人間が PR を merge した時点で Issue は GitHub が自動 close** する。「issue close → Done」の自動化が入っている Project なら board もそこで `Done` に遷移する。
- **skill からは `gh issue close` を実行しない** — merge 前に閉じると、未マージの作業が完了に見える。却下時の reopen 作業も不要になる。
- **board の Status は merge まで `In Progress` のまま**にする（実装は終わりレビュー・merge 待ちの状態。skill からは動かさない）。§1.5 のとおりラベルは付けていないので、外す作業も無い。
- **`Waiting` / `Blocked` 系の列がある board でも、人間のレビュー・merge 待ちでそこへ動かさない**。それらの列は「外部の判断でブロックされ、再開に別の出来事を要する issue」（ストア審査待ち・監修待ち・外部からの回答待ち）のためのもので、merge 待ちは通常の進行中の一段階にすぎない。動かすと board 上で作業が止まって見え、merge 時の `issue close → Done` の自動遷移とも噛み合わない。
- issue が本当に外部要因でブロックされて `Waiting` へ動かす場合は、**必ず理由コメントとセットにする** — 何を待っているか・何が起きたら再開するかを issue 上で辿れるようにする。Status だけ動かしてコメントを残さない状態を作らない。
- PR が却下／作り直しになったら、再着手時に §1.5 をやり直す。

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

### 計画からの逸脱（Deviations）
- [計画から外れた判断とその理由。無ければ「なし」]

### レビュー結果
- ステータス: PASS / WARN / 5回FAIL / スキップ
- レビュー回数: N回

### テスト（red→green）
- [新規テスト N 件を先に落としてから通した / スキップ（理由）]
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
9. **テストを先に落とす** - Phase 6 は red→green の順。スキップできるのはテストで検証できない変更のみ（完了報告に理由を明記）
