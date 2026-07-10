---
name: create-issue
argument-hint: "[issue-url (リライト時のみ)]"
description: "GitHub Issue の作成・リライトを行うスキル。新規作成と既存Issueのリライト（第三者が実装できる粒度への改善）に対応。対象リポジトリはカレントの git リポジトリ（または明示指定した owner/repo）。以下の場合に使用: (1) タスクの Issue を作成したいとき (2) 「Issue作って」「タスク登録して」「チケット切って」と依頼されたとき（今は直さないバグ・後でやる作業の起票を含む） (3) 「/create-issue」と呼び出されたとき (4) 会話で議論した内容をIssueとしてまとめたいとき (5) 既存IssueのURLを渡されて「内容を修正して」「リライトして」と依頼されたとき"
allowed-tools: Read, Glob, Grep, Bash(gh issue create:*), Bash(gh issue edit:*), Bash(gh issue view:*), Bash(gh issue list:*), Bash(gh api:*), Bash(gh project:*), Bash(gh repo view:*), Bash(git remote:*), Bash(python3:*), Bash(base64:*)
---

# GitHub Issue 管理スキル

GitHub の Issue を作成・リライトする。**第三者が読んで着手できる「概要」**を作るのが目的で、実装手順や計画は含めない（それは plan-issue の役割）。

## 対象リポジトリの決定

1. ユーザが `owner/repo` または Issue URL を明示した → それを対象にする
2. それ以外 → **カレントの git リポジトリ**を対象にする（`gh repo view --json nameWithOwner -q .nameWithOwner` で確認）
3. カレントが git リポジトリでない → ユーザに対象リポジトリを確認する

以降、`gh` のリポジトリ指定は `--repo <owner/repo>` で行う（カレントリポジトリなら省略可）。

## モード判定

入力に応じて以下のモードを選択する:

- **既存IssueのURL が渡された場合** → [B. リライトモード](#b-リライトモード)
- **それ以外** → [A. 新規作成モード](#a-新規作成モード)

## 両モード共通ルール

**Issue 本文に含めないもの（冗長化の主因。plan-issue や実作業プレイブックの領域）:**
[`_shared/pr-conventions.md`](../_shared/pr-conventions.md) §1「原則含めないもの」共通項（ロールバック手順・検証/進捗チェックリスト・リスク表・運用詳細）に加え、Issue 固有で:
- 具体的な実装手順・作業ステップ・コード変更箇所の特定
- 技術的な調査結果・設計判断の詳細
- 参考 URL 一覧の羅列

> 目安: Issue 本文は背景・ゴール・スコープが見渡せる分量（全体 30-50 行・スクロールせず読み切れる）。網羅性が必要な情報は plan-issue の計画コメント側に積む。

**投稿 / 更新前セルフチェック（`gh issue create` / `gh issue edit` の直前に必ず 1 パス）:**
[`_shared/pr-conventions.md`](../_shared/pr-conventions.md) §2 のチェックリスト（推敲＋構造）に加え:
- [ ] 上記 Issue 固有除外が混入していないか
- [ ] 各セクションが概要レベル（新規 1-3 行 / リライト 1-5 行）に収まっているか
- [ ] （リライト時のみ）既存本文の有用な情報を削りすぎていないか（背景・前提が失われていないか）

混入・冗長化・情報欠落が見つかったらこの時点で直してから実行する。

---

## A. 新規作成モード

### 0. Issueテンプレートの取得

対象リポジトリに Issue テンプレートがあれば取得して、その構造に従う。無ければデフォルト構造を使う。

```bash
# テンプレート一覧を確認（.github/ISSUE_TEMPLATE/ 配下）
gh api repos/<owner/repo>/contents/.github/ISSUE_TEMPLATE 2>/dev/null --jq '.[].name'

# 該当テンプレートがあれば中身を取得
gh api repos/<owner/repo>/contents/.github/ISSUE_TEMPLATE/<file> --jq '.content' | base64 -d
```

- 複数テンプレートがあればタスクの性質に最も合うものを選ぶ。
- テンプレートが無いリポジトリでは、以下のデフォルト構造を使う:

```markdown
## 背景・なぜやるのか
<1-3行>

## ゴール（完了条件）
<完了状態で記述>

## スコープ
- やること
- やらないこと
```

### 1. 会話コンテキストからドラフト作成

それまでの会話内容を元に、テンプレートの各セクションを**概要レベル**で埋める。
- **Issue本文は概要のみ**。各セクション1-3行程度の箇条書きに収める
- 「なぜやるのか」は背景・動機を1-3行で
- 「ゴール」は完了条件を明確に

### 1.5 規模判定：大きめタスクは親（エピック）＋子に分割する

ドラフトを作ったら、タスクの規模を判定する。**1 つの PR で完結しない／複数の独立した作業に分解できる大きめタスク**なら、単一 Issue ではなく **親 Issue（エピック）＋子 Issue 群**として作る。

**大きめと判断する目安（いずれか）:**
- 完了までに複数の PR が必要、または着手単位が 3 つ以上に分かれる
- 「機能群」「〜の刷新」「〜への移行」など、明らかに複数サブタスクを含む
- スコープの「やること」が箇条書きで 4 つ以上に膨らむ

**分割する場合の手順:**

1. **親 Issue（エピック）を作る** — 本文は背景・ゴール・スコープ（子の一覧は sub-issue が自動表示するので箇条書きは最小限）。`epic` ラベルを付与（無ければ作成）。
2. **子 Issue をそれぞれ作る** — 各子は「第三者が 1 単位で着手できる」粒度。通常の新規作成フロー（§1〜§3）に従う。
3. **親子をリンクする**（GitHub ネイティブ sub-issue。`gh issue create` には sub-issue 化のフラグが無いので GraphQL を使う）:

```bash
# 親・子それぞれの node id を取得
PARENT_ID=$(gh issue view <親番号> --repo <owner/repo> --json id -q .id)
CHILD_ID=$(gh issue view <子番号> --repo <owner/repo> --json id -q .id)

# 子を親の sub-issue にする
gh api graphql -f query='
mutation($parent:ID!,$child:ID!){
  addSubIssue(input:{issueId:$parent, subIssueId:$child}){ subIssue { number } }
}' -f parent="$PARENT_ID" -f child="$CHILD_ID"
```

4. 全子をリンクしたら、**親の URL を主として返し**、子の番号・タイトルも一覧で添える。

分割せず単一 Issue で十分なら、そのまま §2 以降に進む。判断に迷う規模ならユーザに「親子に分けますか？」と一言確認する。

含めない項目・分量目安は**両モード共通ルール**参照。

**タイトルの自動生成:**
- タイトルは会話コンテキストから自動生成する（ユーザに確認しない）
- 期限・EOLがある場合は、バッファを見込んだ対応期限を `[YYYY/MM]` プレフィックスとして付与する
  - 例: EOL が 2026/9/15 → `[2026/08] Cloudflare Pages Build Image v1 → v3 移行対応`
  - バッファは内容の規模に応じて2週間〜1ヶ月程度を目安に逆算する

### 2. ユーザへのインタビュー

ドラフトを提示した上で、会話から読み取れなかった**不明点がある場合のみ**質問する。
- ラベル・関連Issueはユーザから指定がない限り空欄とする
- **アサインは既定で自分（`@me`）**にする（ユーザが別のアサイン先を明示した場合のみそれに従う）
- 内容の修正確認は不要（そのまま作成する）
- 不明点がなければインタビューをスキップして即座にIssue作成に進む

### 2.5 投稿前セルフチェック

**両モード共通ルール**のセルフチェックを通してから Step 3 に進む。

### 3. Issue作成

`gh` CLIで作成する:

```bash
gh issue create \
  --repo <owner/repo> \
  --title "タイトル" \
  --assignee @me \
  --body "$(cat <<'EOF'
本文
EOF
)"
```

- カレントリポジトリで作成するなら `--repo` は省略可
- **アサインは既定で `--assignee @me`（自分）**。ユーザが別アサインを明示した場合はそれに置き換える
- ラベルはユーザから明示的に指定があった場合のみ `--label` を含める
- 作成後、Issue URLをユーザに返す

### 3.5 Project の Type フィールドを分類して設定（Project 管理リポジトリの場合）

作成した Issue が GitHub Project で管理されていて、その Project に単一選択フィールド **Type** があれば、タスクの性質を分類して Type を設定する。**Type フィールドが無ければこの手順を skip**（その旨を報告に一言添える）。

**分類の基準（タスクの性質 → Type 選択肢にマップ。実選択肢はそのProjectの定義に従い最も近いものを選ぶ）:**
- `feature`: 新機能・新しい入力手段・モード追加
- `fix`: 不具合修正・正確性/堅牢性の改善（既存挙動の取りこぼし解消）
- `refactor`: 挙動を変えない内部改善
- `docs`: ドキュメント
- `chore`: 設定・依存・アセット更新などの雑務
- `perf`: パフォーマンス改善
- `test`: テストの追加・整備
- `infra`: CI・インフラ・デプロイ

**設定手順（gh + GraphQL）:**

```bash
OWNER=<owner>; PNUM=<project番号>; ISSUE_URL=<作成したissueのURL>
TYPE_VALUE=feature   # 上の基準で分類した値

PROJECT_ID=$(gh project view $PNUM --owner $OWNER --format json -q .id)
gh project field-list $PNUM --owner $OWNER --format json > /tmp/fields.json
FIELD_ID=$(python3 -c "import json;print(next((f['id'] for f in json.load(open('/tmp/fields.json'))['fields'] if f['name']=='Type'),''))")
OPT_ID=$(python3 -c "import json;print(next((o['id'] for f in json.load(open('/tmp/fields.json'))['fields'] if f['name']=='Type' for o in f.get('options',[]) if o['name']=='$TYPE_VALUE'),''))")
# FIELD_ID が空（Type フィールド無し）なら skip

ITEM_ID=$(gh project item-add $PNUM --owner $OWNER --url "$ISSUE_URL" --format json -q .id)  # 追加済みでも item id を返す

gh api graphql -f query='
  mutation($p:ID!,$i:ID!,$f:ID!,$o:String!){
    updateProjectV2ItemFieldValue(input:{projectId:$p,itemId:$i,fieldId:$f,value:{singleSelectOptionId:$o}}){ projectV2Item{ id } }
  }' -f p="$PROJECT_ID" -f i="$ITEM_ID" -f f="$FIELD_ID" -f o="$OPT_ID"
```

- **§1.5 で親子分割した場合は子 Issue それぞれに Type を設定**する。親エピックは container なので Type は基本空欄でよい。
- 対象 Project が一意に決まらない場合（複数紐づくなど）は、その issue を管理する Project（通常はリポジトリのロードマップ）を選ぶ。判断できなければユーザに確認するか skip して報告する。

---

## B. リライトモード

既存IssueのURLを受け取り、第三者が実装できる粒度に本文をリライトする。
実装手順や計画は含めない（それは plan-issue の役割）。

### 1. 既存Issueの内容を取得

```bash
gh issue view <ISSUE_NUMBER or URL> --repo <owner/repo>
```

タイトル・本文・ラベル・コメントを確認する。

### 2. Issueテンプレートの取得（任意）

リポジトリにテンプレートがあれば構造の参考にする（A-0 と同じ取得方法）。無ければ既存本文の構造を尊重する。

### 3. リライトドラフト作成

既存の本文と会話コンテキストを元に、第三者が実装に着手できる概要にリライトする。

**リライトの基準:**
- **背景・動機**: なぜこのタスクが必要なのか、前提知識がなくても理解できるように書く
  - 略語・社内用語には補足を入れる
  - 関連する制約（期限、依存関係、影響範囲）を明記する
- **ゴール**: 完了条件を具体的かつ検証可能な形で書く
  - 「〜する」ではなく「〜の状態になっている」のように完了状態で記述する
  - 曖昧な表現（「適切に」「必要に応じて」）を避け、具体的な条件に置き換える
- **スコープ**: やること・やらないことの境界を明確にする
- **各セクション**: 1-5行程度の箇条書き。概要レベルを維持しつつ、情報の抜け漏れをなくす

**リライトに含めないもの・分量目安:** **両モード共通ルール**参照（新規作成モードと同じ）。

### 4. ユーザへの確認

リライト前後の差分がわかるようにドラフトを提示し、確認を求める。
- 既存の内容から大きく変わる箇所をハイライトする
- ユーザの承認を得てからIssueを更新する

### 4.5 更新前セルフチェック

ユーザ承認後、`gh issue edit` の直前に**両モード共通ルール**のセルフチェック（リライト固有の「削りすぎていないか」確認を含む）を通してから Step 5 に進む。

### 5. Issue本文の更新

```bash
gh issue edit <ISSUE_NUMBER or URL> \
  --repo <owner/repo> \
  --body "$(cat <<'EOF'
リライト後の本文
EOF
)"
```

- タイトルも改善が必要な場合は `--title` オプションを追加する
- 更新後、Issue URLをユーザに返す

---

## plan-issue への橋渡し

Issue を作成・リライトしたら、ユーザが「計画も立てて」と言えば、その Issue URL を `plan-issue` に渡して実装計画コメントを作成できる。Issue 本文には概要だけを置き、実装の詳細は計画コメント側に積み上げる、という役割分担を保つ。
