---
name: cc-article
description: Claude Code / AI コーディング系の記事 (Zenn・Qiita・個人ブログ・英語) の URL を渡すと、その手法・Tips で issei の Claude Code 環境を良くできるかを診断する skill。受け皿は新規 skill に限らず、**既存 skill・agent を記事の知見で磨いて育てる**こと・個人 `~/.claude` の settings.json / hook / statusline / CLAUDE.md / MCP / 何もしない（既に良い）まで等価に評価する。外部記事を toolkit へのフィードバックループにして継続的に育てる視点を持つ（内部セッションログ起点の改善は [[skill-reflect]]、こちらは外部記事起点）。各テクを ✅採用候補 / 🤔条件付き / ❌見送り で判定し、落とし所 (新規 / 既存 skill・agent の改善 / 個人設定 / 何もしない・既存との重複) と次アクションまで提示する (実装はしない)。判断材料として記事の要約も添える。ユーザーが「この記事でうちの CC 環境よくできる?」「この記事 claude-forge に活かせる?」「この手法で既存 skill を改善できる?」「<URL> をうちに採用できるか見て」「この Zenn/Qiita うちに取り込める?」「この手法うちの環境に入れられる?」などと、CC 関連記事の URL を渡して自分の CC 環境への取り込み・育成判断を求めたときに発動する。skill を増やすこと自体は目的ではない（既存改善・個人設定だけ変更・現状追認も成果）。単に記事を要約・解説してほしいだけなら発動しない (素の Claude で足りる)。AWS / Claude 公式 docs を図解 HTML 教材にしたいだけなら [[doc-illustrate]] を使う。
allowed-tools: Read, Glob, Grep, WebFetch, Bash(python3:*), Bash(curl:*), Bash(ls:*)
---

# cc-article

Claude Code 関連の記事 (Zenn / Qiita / ブログ / 英語記事) の URL を渡されたら、**その手法で issei の Claude Code 環境を良くできるかを診断する** skill。**成果物は「CC 環境改善診断」**（記事のテクを CC 環境のどこに落とせるか・既存と重複しないかの判定と次アクション）。記事の要約は、その診断を地に足の着いたものにするための**材料として添える**だけ。

**ゴールは「環境を良くする」であって「skill を増やす」ではない。** 新規 skill 化は数ある受け皿の 1 つにすぎない。受け皿は **新規 skill / agent** に限らず、**既存 skill・agent を記事の知見で磨いて育てる**こと・**個人 `~/.claude` の settings.json・hook・statusLine・CLAUDE.md・MCP・Dynamic Workflows・何もしない（既に良い）** まで等価に並べる。「新規 skill ゼロ」「既存を 1 つ磨いた」「個人設定だけ変更」「現状追認」も立派な成果として提示する。

**とりわけ「既存 skill・agent を育てる」は中心的な狙いの 1 つ。** 外部記事は toolkit を継続改善するフィードバック源 — 各テクは「新規で足すか」だけでなく「**既存のどの skill / agent をどう良くできるか**」を必ず照合する。新規追加と同格に扱い、可能なら既存への統合・強化を優先する（同じ機能を新規で再発明しない）。内部のセッションログ起点の自己改善は [[skill-reflect]]、こちらは**外部記事起点**の育成という住み分け。

**実装はしない** — 採用すると決めたら別 skill (`skill-creator` / `update-config` / `install-pr-reviews` / `ship`) に渡す。

判断対象は **issei の CC 環境** = ①共有の toolkit リポジトリ **claude-forge** (`~/projects/claude-forge`) と ②個人 **`~/.claude`** 設定の両方。cwd がどこでも、既定でこの 2 つを基準に既存 skill・設定・方針を見る (cwd が既に claude-forge 内ならそれを使う)。

> **要約だけが欲しいなら、この skill は不要**（素の Claude が直接やる）。この skill の存在価値は「自分の CC 環境を良くできるかの取り込み判断」。だから発火トリガも「環境よくできる?/採用できる?/取り込める?/入れられる?」側に寄せている。確実に使いたい時は `/cc-article <URL>` と明示的に呼ぶ。

## 前提

- 記事取得は **要約モデルを挟まない生テキスト最優先** ([[doc-illustrate]] / [[aws-docs]] と同じ原則)。[[doc-illustrate]] 同梱の `extract.py` が「その他 URL = タグ剥がし」分岐で **Zenn / Qiita / 一般ブログの本文をそのまま吐く** (検証済み)。**claude-forge 原本の絶対パスで叩く** (cwd 非依存・global symlink で別プロジェクトから使っても効く): `python3 ~/projects/claude-forge/.claude/skills/doc-illustrate/scripts/extract.py <URL>`。
- 無ければ `curl -sL -A "Mozilla/5.0" <URL>` で生 HTML を取り自分で読む。**WebFetch は最後の手段** (小型モデルがコマンド名・フラグ・バージョンを幻覚する)。
- **Qiita は本文の前にナビ/UI 文言** (`searchsearchSearchLogin…`、Share ボタン、削除確認文) が混じる。`##` 見出し以降が本文なので頭のノイズは無視する。**Zenn も**先頭に著者名・絵文字・タグ、末尾に `## Discussion` + 著者プロフィール/免責が付く — 本文は最初の `##` 見出し〜`## Discussion` の直前まで。
- JS でしか描画されず本文が取れない / 有料・会員限定で途中で切れる場合は、ユーザーに本文の貼り付けを頼む (推測で埋めない)。

## ワークフロー

### 1. 記事を生テキストで読む（診断の材料を集める）
- 上記手段で本文を取得し、**幹を掴む**: 何の記事か / 主張・手法の核 / 具体テクニック (コマンド・設定・skill・hook・運用) / 前提 (CC のバージョン・OS・依存ツール) / つまずき所。
- 記事は **CC 環境と無関係なテクも混ざる**前提で、CC / skill / 設定 / hook / 運用に効く部分を拾う（ここが診断の入力になる）。

### 2. CC 環境の現状を把握する (重複・方針整合チェックのため・毎回やる)
- `ls ~/projects/claude-forge/.claude/skills/` で**既存 skill 一覧**を取る (記憶のリストに頼らない・増減する)。気になる skill は SKILL.md を覗く。
- `~/projects/claude-forge/CLAUDE.md` の「約束事」と README の「現在の skill」表で**方針と既存カバー範囲**を確認する。`.claude/agents/` `.claude/settings.json` も受け皿として把握。
- **個人 `~/.claude` 側も受け皿**として見る: `~/.claude/settings.json`（statusLine / hook / permissions / env / MCP）や `~/.claude/CLAUDE.md`（全プロジェクト共通の作法）も「ここを直せば環境が良くなる」候補。記事のテクが skill でなく個人設定で効くなら、そこに落とす。

### 3. CC 環境改善フィット診断（この skill の主役）
記事から拾ったテクを **1 つずつ**、「**これで issei の CC 環境は良くなるか**」を軸に、ラベル + 理由 + 落とし所で判定する:
- **✅採用候補** — 環境が確かに良くなり、既存と重複せず、すぐ載せられる。
- **🤔条件付き** — 有効だが要検証 (CC の現行仕様か) / 要 MCP・CLI / 要権限追加 / 既存 skill・設定への統合が筋、など条件付き。
- **❌見送り** — 既存でカバー済み / 方針と衝突 (下記) / 環境改善に効かない・無関係 / 出典が怪しい・再現性低い。**「skill にならない」だけを理由に ❌ にしない** — 個人設定・hook・statusLine で環境が良くなるなら ✅/🤔 で拾う。

**落とし所のマッピング** (どの受け皿になるか明示する・skill に限らない):
- **【最優先で照合】既存 skill / agent を磨く（育てる）** → 記事のテクが既存の SKILL.md・references・agent のレビュー基準/手順を良くできるなら、**新規作成より優先**で「どの skill / agent をどう直すか」を具体に出す（`skill-creator` で編集 → [[ship]]）。例: 参照ファイルの分割・禁止事項の言い換え・チェック手順の明文化・description の発火精度改善・agent (`doc-reviewer` / `doc-impl-reviewer`) のレビュー観点強化
- 繰り返す手順の自動化・ワザ（既存に無いもの） → **新規 skill** (`skill-creator`)
- 「X したら毎回 Y」の自動挙動 → **hook** (claude-forge or 個人 `~/.claude` の `settings.json`・`update-config`)
- 権限 / env / MCP の追加 → **settings.json** (`update-config`)
- 端末の見た目・常時表示・個人の操作環境 → **個人 `~/.claude/settings.json`**（statusLine 等）。claude-forge のコミット版には入れない（個人の見た目設定だから・例: statusline カスタム）
- 独立コンテキストで委譲したいレビュー等 → **新規 agent** か **既存 agent の基準を強化** (`.claude/agents/`)
- 大規模・並列の移行 / 監査 / 横断調査 → **Dynamic Workflows**（CLAUDE.md の作法に沿って）
- 単なる知識・運用方針 → **CLAUDE.md か memory** (skill にはしない)
- PR 自動レビュー系の話 → 既に [[install-pr-reviews]] がある
- **既に十分カバーされている / 今の作法が裏付けられた** → **何もしない**。それも成果として明言する（skill 数を増やすことは目的ではない）

**方針との整合 (ここで弾く/読み替える)**:
- 記事が **カスタムスラッシュコマンド (`commands/`) 前提**でも、claude-forge は**全部 skill に統合**する方針 → 「skill 化すれば取り込める」と読み替える (そのまま ❌ にしない)。
- secret・API key・個人情報・絶対パスを**同梱前提**の手法 → claude-forge のコミット版には載せない (個人 `~/.claude` / local / 環境変数へ) 形に直せるなら 🤔、無理なら ❌。
- 生成物を repo に置く前提 → claude-forge は生成物を gitignore する (`summaries/` `data/` `INTERESTS.md`)。
- 全プロジェクトで使う想定か → **global symlink 運用** (`~/.claude/skills/`) か **個人 `~/.claude/settings.json`** に乗るか一言。

### 4. 診断の材料として記事を要約する (短く・チャット出力・日本語)
- **要約は診断を支える文脈であって主役ではない**。専門用語を噛み砕き、**記事が何を主張し何を勧めているか**を最短で渡す。長文の逐語コピーはしない (構成は下記「出力フォーマット」)。
- 記事内の **CC の挙動・コマンド・フラグ・上限・「新機能」主張は鵜呑みにしない**。採用検討に効く要点は、必要に応じ公式 (`docs.claude.com`、changelog) で裏取りしてから「これは現行で有効/古い可能性」と一言添える。CC は機能の増減が速い。

### 5. 次アクションを提示して終わる (実装はしない)
- ✅ / 🤔 のうち**環境改善の効きが大きいもの上位**を、具体的な一歩で示す: 「skill にするなら `skill-creator`、個人 `~/.claude` 設定 / hook / statusLine なら `update-config`、PR レビュー系なら [[install-pr-reviews]]、claude-forge を直したら [[ship]] で PR」。
- ✅/🤔 が無ければ「**今回は新規 skill ゼロ・現状で十分**」と正直に締めてよい。skill 数を増やすことは成果指標ではない。
- 「どれを進める?」と一声かけて止まる。**この skill 自身は skill / 設定を作らない**。

## 出力フォーマット (チャット・日本語)

**診断を主役に置く。** 要約は診断の前段の短い文脈として置く。

```
## 📄 要約: <記事タイトル>（診断のための文脈・短く）
<出典: ホスト名 / 著者 / 公開日 (分かれば)>

**ひとことで**: <1〜2 文>
**要点**: <核となる主張・手法を 2〜4 個>
**具体テクニック**: <コマンド / 設定 / skill / 運用ワザを箇条書き>
**前提・注意**: <CC のバージョン依存 / 依存ツール / 裏取りで分かった「古い可能性」など>

## 🔧 CC 環境改善診断（← 本題）
| テク | 判定 | 落とし所 / 理由 |
|---|---|---|
| <テクA> | ✅採用候補 | 既存 skill/agent `◯◯` を磨く（references 分割・禁止の言い換え・基準強化）|
| <テクB> | ✅採用候補 | 新規 skill / 個人 `~/.claude` 設定。既存に無く環境が良くなる |
| <テクC> | 🤔条件付き | 要 MCP / 要権限 / 現行仕様か要検証 |
| <テクD> | ❌見送り | `doc-illustrate` と重複 / 環境改善に効かない / 再現性低い |

## ▶️ 次の一歩
<効きが大きい上位 1〜3 個を具体アクションで。✅/🤔 が無ければ「現状で十分」と締める。「進める?」で止まる>
```

## してはいけないこと

- **要約だけで終わらせない。** この skill の成果物は CC 環境改善診断。要約は材料。診断と次アクションまで必ず出す。
- **「skill にならない」を理由に切り捨てない。** 個人 `~/.claude` 設定・hook・statusLine で環境が良くなるなら ✅/🤔 で拾う。逆に **skill 数を増やすこと自体を目的化しない** — 「新規 skill ゼロ・現状追認」も正しい結論として堂々と出す。
- **記事の CC 知識を鵜呑みにして採用提案しない。** コマンド・フラグ・上限・「新機能」は公式 (`docs.claude.com` / changelog) で裏取りし、古い/不確かなら明示する。CC は変化が速い。
- **記事本文を WebFetch の要約で済ませない。** 生テキスト (`extract.py` / `curl`) で読む。取れなければ貼り付けを頼む。**本文が取れていない記事を推測で要約しない。**
- **この skill で実装・コミットしない。** 採用判断と提案まで。実装は別 skill に明示的に渡す。
- **既存でのカバーを見落とさない。新規より先に「既存 skill / agent を磨けないか」を検討する。** 必ず `ls ~/projects/claude-forge/.claude/skills/` と `.claude/agents/` で現物を見て、個人 `~/.claude` 設定も思い出してから「新規」と言う (cwd 非依存で見る・新規で再発明せず、育てられるなら育てる)。
- **claude-forge の方針を破る形で採用提案しない** (スラッシュコマンド新設・secret 同梱・生成物の追跡・個人の見た目設定をコミット版に混入)。読み替えられるなら読み替える。
- 記事や URL に**受講生の個人情報・非公開 URL**が含まれていたら、要約にもチャットにも残さない。

## 関連

- 取得・正確さの原則は [[doc-illustrate]] / [[aws-docs]] と同じ (生テキスト優先・主張は一次ソースで裏取り)。`extract.py` も [[doc-illustrate]] のものを流用。**役割は別**: doc-illustrate は公式 docs → 図解 HTML 教材を作る、cc-article は CC 記事 → 自分の CC 環境（claude-forge skill + 個人 `~/.claude` 設定）への取り込み診断を返す。
- 採用すると決めたら: skill 化は `skill-creator`、個人/共有の設定・hook・statusLine は `update-config`、PR レビュー導入は [[install-pr-reviews]]、claude-forge の仕上げの PR は [[ship]]。
- skill を新設したら **README の「現在の skill」表に 1 行追記** (claude-forge の約束事)。
