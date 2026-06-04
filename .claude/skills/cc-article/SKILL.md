---
name: cc-article
description: Claude / Claude Code / AI コーディング系の記事 (Zenn・Qiita・個人ブログ・英語記事など) の URL を渡すと、生テキストで読み込んで (1) わかりやすく日本語で要約し、(2) その手法・Tips を claude-forge に採用できるか診断する。各テクを ✅採用候補 / 🤔条件付き / ❌見送り で判定し、claude-forge 上の落とし所 (どの skill / 設定 / hook / agent になるか・既存との重複) と次アクションまで提示する (実装まではしない)。ユーザーが「この記事 claude-forge に活かせる?」「<URL> を要約して採用できるか見て」「この Zenn 読んで」「Qiita のこれうちのリポジトリに入れられる?」「Claude Code のこの記事わかりやすくして」「この記事の手法うちに取り込める?」などと、CC 関連記事の URL を渡して要約 + 自リポジトリへの取り込み判断を求めたときに発動する。AWS / Claude 公式 docs を図解 HTML 教材にしたいだけなら [[doc-illustrate]]、記事をネタに X / ツイート投稿を作りたいなら [[x-buzz]] を使う。
---

# cc-article

Claude Code 関連の記事 (Zenn / Qiita / ブログ / 英語記事) の URL を渡されたら、**生テキストで読み込んで「わかりやすい要約」と「claude-forge に採用できるか診断」の 2 本立て**でチャットに返す skill。記事のテクを claude-forge の skill / 設定 / hook / agent のどこに落とせるかまで見立てる。**実装はしない** — 採用すると決めたら別 skill (`skill-creator` / `update-config` / `install-pr-reviews` / `ship`) に渡す。

判断対象は常に **claude-forge** (この toolkit リポジトリ)。cwd がどこでも、既定で `~/projects/claude-forge` を基準に既存 skill と方針を見る (cwd が既に claude-forge 内ならそれを使う)。

> 自動発火は best-effort。「記事を要約して」系は Claude が自前で済ませようとして発火しないことがある (発火 eval で確認済み)。**確実に使いたい時は `/cc-article <URL>` と明示的に呼ぶ。**

## 前提

- 記事取得は **要約モデルを挟まない生テキスト最優先** ([[doc-illustrate]] / [[aws-docs]] と同じ原則)。[[doc-illustrate]] 同梱の `extract.py` が「その他 URL = タグ剥がし」分岐で **Zenn / Qiita / 一般ブログの本文をそのまま吐く** (検証済み)。**claude-forge 原本の絶対パスで叩く** (cwd 非依存・global symlink で別プロジェクトから使っても効く): `python3 ~/projects/claude-forge/.claude/skills/doc-illustrate/scripts/extract.py <URL>`。
- 無ければ `curl -sL -A "Mozilla/5.0" <URL>` で生 HTML を取り自分で読む。**WebFetch は最後の手段** (小型モデルがコマンド名・フラグ・バージョンを幻覚する)。
- **Qiita は本文の前にナビ/UI 文言** (`searchsearchSearchLogin…`、Share ボタン、削除確認文) が混じる。`##` 見出し以降が本文なので頭のノイズは無視する。**Zenn も**先頭に著者名・絵文字・タグ、末尾に `## Discussion` + 著者プロフィール/免責が付く — 本文は最初の `##` 見出し〜`## Discussion` の直前まで。
- JS でしか描画されず本文が取れない / 有料・会員限定で途中で切れる場合は、ユーザーに本文の貼り付けを頼む (推測で埋めない)。

## ワークフロー

### 1. 記事を生テキストで読む
- 上記手段で本文を取得し、**幹を掴む**: 何の記事か / 主張・手法の核 / 具体テクニック (コマンド・設定・skill・hook・運用) / 前提 (CC のバージョン・OS・依存ツール) / つまずき所。
- 記事は **claude-forge と無関係なテクも混ざる**前提で、CC / skill / 設定 / 運用に効く部分を拾う。

### 2. claude-forge の現状を把握する (重複・方針整合チェックのため・毎回やる)
- `ls ~/projects/claude-forge/.claude/skills/` で**既存 skill 一覧**を取る (記憶のリストに頼らない・増減する)。気になる skill は SKILL.md を覗く。
- `~/projects/claude-forge/CLAUDE.md` の「約束事」と README の「現在の skill」表で**方針と既存カバー範囲**を確認する。`.claude/agents/` `.claude/settings.json` も受け皿として把握。

### 3. わかりやすく要約する (チャット出力・日本語)
- 専門用語は噛み砕き、**記事が何を主張し何を勧めているか**を最短で渡す。長文の逐語コピーはしない (構成は下記「出力フォーマット」)。
- 記事内の **CC の挙動・コマンド・フラグ・上限・「新機能」主張は鵜呑みにしない**。採用検討に効く要点は、必要に応じ公式 (`docs.claude.com`、changelog) で裏取りしてから「これは現行で有効/古い可能性」と一言添える。CC は機能の増減が速い。

### 4. claude-forge へのフィット診断
記事から拾ったテクを **1 つずつ**、ラベル + 理由 + 落とし所で判定する:
- **✅採用候補** — claude-forge の方針に合い、既存と重複せず、すぐ載せられる。
- **🤔条件付き** — 有効だが要検証 (CC の現行仕様か) / 要 MCP・CLI / 要権限追加 / 既存 skill への統合が筋、など条件付き。
- **❌見送り** — 既存 skill と重複 / 方針と衝突 (下記) / claude-forge と無関係 / 出典が怪しい・再現性低い。

**落とし所のマッピング** (どの受け皿になるか明示する):
- 繰り返す手順の自動化・ワザ → **新規 skill** か **既存 skill に統合** (`skill-creator`)
- 「X したら毎回 Y」の自動挙動 → **hook** (`settings.json`・`update-config`)
- 権限 / env / MCP の追加 → **settings.json** (`update-config`)
- 独立コンテキストで委譲したいレビュー等 → **agent** (`.claude/agents/`)
- 単なる知識・運用方針 → **CLAUDE.md か memory** (skill にはしない)
- PR 自動レビュー系の話 → 既に [[install-pr-reviews]] がある

**方針との整合 (claude-forge 固有・ここで弾く/読み替える)**:
- 記事が **カスタムスラッシュコマンド (`commands/`) 前提**でも、claude-forge は**全部 skill に統合**する方針 → 「skill 化すれば取り込める」と読み替える (そのまま ❌ にしない)。
- secret・API key・個人情報・絶対パスを**同梱前提**の手法 → コミット版には載せない (local / 環境変数へ) 形に直せるなら 🤔、無理なら ❌。
- 生成物を repo に置く前提 → claude-forge は生成物を gitignore する (`summaries/` `data/` `INTERESTS.md`)。
- 全プロジェクトで使う想定か → **global symlink 運用** (`~/.claude/skills/`) に乗るか一言。

### 5. 次アクションを提示して終わる (実装はしない)
- ✅ / 🤔 のうち**やる価値が高いもの上位**を、具体的な一歩で示す: 「これを skill にするなら `skill-creator`、設定なら `update-config`、PR レビュー系なら [[install-pr-reviews]]、できたら [[ship]] で PR」。
- 「どれを進める?」と一声かけて止まる。**この skill 自身は skill / 設定を作らない**。

## 出力フォーマット (チャット・日本語)

```
## 📄 要約: <記事タイトル>
<出典: ホスト名 / 著者 / 公開日 (分かれば)>

**ひとことで**: <1〜2 文>

**要点**
- <核となる主張・手法>
- ...

**具体テクニック**
- <コマンド / 設定 / skill / 運用ワザを箇条書き>

**前提・注意**: <CC のバージョン依存 / 依存ツール / 裏取りで分かった「古い可能性」など>

## 🔧 claude-forge へのフィット診断
| テク | 判定 | 落とし所 / 理由 |
|---|---|---|
| <テクA> | ✅採用候補 | 新規 skill 化。既存に無く方針とも整合 |
| <テクB> | 🤔条件付き | 既存 `x-buzz` に統合が筋 / 要 MCP / 現行仕様か要検証 |
| <テクC> | ❌見送り | `doc-illustrate` と重複 / commands 前提で方針外 |

## ▶️ 次の一歩
<上位 1〜3 個を具体アクションで。「進める?」で止まる>
```

## してはいけないこと

- **記事の CC 知識を鵜呑みにして採用提案しない。** コマンド・フラグ・上限・「新機能」は公式 (`docs.claude.com` / changelog) で裏取りし、古い/不確かなら明示する。CC は変化が速い。
- **記事本文を WebFetch の要約で済ませない。** 生テキスト (`extract.py` / `curl`) で読む。取れなければ貼り付けを頼む。**本文が取れていない記事を推測で要約しない。**
- **この skill で実装・コミットしない。** 採用判断と提案まで。実装は別 skill に明示的に渡す。
- **既存 skill との重複を見落とさない。** 必ず `ls ~/projects/claude-forge/.claude/skills/` で現物を見てから「新規」と言う (cwd 非依存で claude-forge を見る・重複なら統合提案にする)。
- **claude-forge の方針を破る形で採用提案しない** (スラッシュコマンド新設・secret 同梱・生成物の追跡)。読み替えられるなら読み替える。
- 記事や URL に**受講生の個人情報・非公開 URL**が含まれていたら、要約にもチャットにも残さない。

## 関連

- 取得・正確さの原則は [[doc-illustrate]] / [[aws-docs]] と同じ (生テキスト優先・主張は一次ソースで裏取り)。`extract.py` も [[doc-illustrate]] のものを流用。
- 採用すると決めたら: skill 化は `skill-creator`、設定 / hook は `update-config`、PR レビュー導入は [[install-pr-reviews]]、仕上げの PR は [[ship]]。
- skill を新設したら **README の「現在の skill」表に 1 行追記** (claude-forge の約束事)。
