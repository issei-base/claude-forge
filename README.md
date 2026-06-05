# claude-forge

Claude Code のカスタム skill 集。**それ自体が 1 つの Claude Code プロジェクト**として動く — clone して Claude Code で開けば、`.claude/skills/` の skill がそのまま有効になる (project スコープ)。

```
claude-forge/
├── .agents/
│   └── skills/ship/            # Codex repo-scoped stub。PR 作成は Claude に任せ、Codex は review-only
├── .codex/
│   ├── config.toml             # Codex project config。Stop hook で skill lint を走らせる
│   └── hooks/skill-lint.py     # Codex Stop hook: tests/lint_skills.py を実行
├── .claude/
│   ├── skills/                 # カスタム skill。開くと project スコープで自動発火
│   │   └── <skill-name>/
│   │       ├── SKILL.md         #   本体。frontmatter の description で発火 / `/skill-name` で明示呼び
│   │       ├── scripts/         #   skill が呼ぶ補助スクリプト (任意)
│   │       ├── references/      #   実行時に読み込む参照資料・雛形 (任意)
│   │       └── assets/          #   同梱テンプレ・画像など (任意)
│   ├── agents/                 # カスタム subagent (<agent-name>.md)。独立コンテキストで委譲実行
│   │   ├── doc-impl-reviewer.md #   実装コードを第三者レビュー (確信度80+・コードは変更しない)
│   │   └── doc-reviewer.md      #   技術ドキュメントを専門家ペルソナでレビュー
│   ├── hooks/                  # settings.json の hooks ブロックから参照するスクリプト
│   │   └── skill-lint.py        #   Stop hook: SKILL.md 編集ターンで lint を強制 (壊れてたら exit 2 で停止)
│   ├── settings.json           # project 設定 (権限 + aws MCP + hooks)。開くと自動適用・コミットする
│   └── settings.local.json     # 個人/マシン固有の上書き (gitignore 済み・コミットしない)
├── tests/                      # skill の検証ハーネス (lint_skills.py = 決定的・上の hook が使用 / eval_triggers.py = 発火テスト / test_scripts.py = unittest)
├── .github/workflows/          # skill-lint (CI lint) + legacy Claude review workflows
├── install.sh                  # 全 skill + agent を ~/.claude に symlink (global 運用)。--dry-run 可
├── data/                       # skill の実行時生成物 (各種ログ等)。gitignore 済み
├── summaries/                  # doc-illustrate の生成 HTML。gitignore 済み・追跡しない
├── INTERESTS.md                # interest-profile の生成物。gitignore 済み・非公開
├── CLAUDE.md                   # この repo で作業する際の作法 (Claude / コントリビュータ向け)
├── LICENSE                     # MIT
└── README.md                   # このファイル
```

> **方針: スラッシュコマンドは使わず、すべて Skills に統合** (Anthropic の最近のガイドラインに沿う)。Skill は description で自動発火するが、明示呼びしたい時は `/skill-name` でも呼べる。`commands/` ディレクトリは置かない。

> **方針: claude-forge が skill の source of truth。** 使い方は 2 通り — **project スコープ** (この repo を開く / 使いたい skill を相手の `.claude/skills/` に `cp -R`) と、**global** (各 skill を `~/.claude/skills/` に symlink して全プロジェクトで使う)。global symlink でも原本は claude-forge 1 箇所なので「どこで編集したか分からなくなる」問題は起きない — 編集は常に claude-forge 側、各プロジェクトはそれを参照するだけ。

## PR 作成とレビューの役割分担

claude-forge では **PR 作成は Claude Code、PR レビューは Codex** に分ける。

| 役割 | 担当 | 発火/操作 |
|---|---|---|
| PR 作成 | Claude Code | Claude の `ship` skill / `create-pr` workflow |
| PR レビュー | Codex | Codex automatic reviews / PR コメントの `@codex review` |
| merge 判断 | 人間 | GitHub UI で内容を見て手動 merge |

Codex はこの repo では branch / commit / push / PR 作成をしない。`.agents/skills/ship` は、Codex に「PR 作って」と頼まれた時に Claude の ship workflow へ戻すための review-only stub。

## 使い方

**1) この repo の skill を試す / 育てる**

```sh
git clone git@github.com:issei-base/claude-forge.git ~/projects/claude-forge
```

`~/projects/claude-forge` を Claude Code で開くだけ。`.claude/skills/` の skill が project スコープで有効になる。SKILL.md を編集すれば即反映 (この repo が source of truth)。

**2) 別のプロジェクトで skill を使う**

2 通り。**単発で 1 つだけ**なら、そのプロジェクトの `.claude/skills/` にコピー:

```sh
mkdir -p /path/to/project/.claude/skills
cp -R ~/projects/claude-forge/.claude/skills/ship /path/to/project/.claude/skills/
```

(Claude Code で作業中なら「ship skill をこのプロジェクトにコピーして」と頼んでもよい。) コピー先を開けば有効になる。

**ツールキットを全プロジェクトで使う**なら、各 skill を **user スコープ (`~/.claude/skills/`) に symlink** する。原本は claude-forge のままなので編集は一箇所・全プロジェクトに即反映。同梱の `install.sh` が全 skill + agent をまとめて symlink する (`_` 始まり・SKILL.md 無しの dir はスキップ):

```sh
./install.sh             # 全部まとめて (~/.claude/skills, ~/.claude/agents へ)
./install.sh --dry-run   # 何が link されるか確認だけ
```

個別にやるなら手で symlink してもよい:

```sh
ln -sfn ~/projects/claude-forge/.claude/skills/ship ~/.claude/skills/ship   # skill ごとに
ln -sfn ~/projects/claude-forge/.claude/agents/doc-reviewer.md ~/.claude/agents/doc-reviewer.md  # agent も
```

スクリプトは `Path(__file__).resolve()` で原本パスに解決されるので、symlink 経由でも data/config は claude-forge 側を見て壊れない。`cp -R` はコピーがドリフトするが他人に配るのに向き、symlink は単一の source of truth を保てる。**user スコープの skill は権限が project 設定と別** なので、`codex`/`gws`/`aws` MCP 等を全プロジェクトで使うなら許可を `~/.claude/settings.json` にも入れる。

この repo を開くと `.claude/settings.json` (project 設定) が**自動適用**される — skill 用の権限 (codex / gws) と `aws` MCP が有効になる (初回はフォルダ設定の trust 確認が入る)。**個人 / マシン固有の設定** (obsidian の vault パス、フル権限許可、secret) は `.claude/settings.local.json` (gitignore 済み) か `~/.claude/settings.json` に置く。Claude Code はランタイムで設定を書き換えるので、自分用の調整は local 側に入れてコミット版を汚さない。

## ここに置くもの

| ディレクトリ | 用途 |
|---|---|
| `.claude/skills/` | `<skill-name>/SKILL.md` 形式の skill。description で自動発火 or `/skill-name` で明示呼び |
| `.claude/agents/` | `<agent-name>.md` のカスタム subagent |
| `.claude/hooks/` | `settings.json` の `hooks` ブロックから参照されるスクリプト (現状 `skill-lint.py` = SKILL.md 編集時の lint ゲート) |
| `.agents/skills/` | Codex repo-scoped skills。現状 `ship` は PR 作成を Claude に任せる review-only stub |
| `.codex/` | Codex project config / hooks。Stop hook で `tests/lint_skills.py` を走らせる |
| `tests/` | skill の検証ハーネス。`lint_skills.py` (決定的 lint・hook が使用) + `eval_triggers.py` (発火 eval) + `triggers.json` (発火 fixture) |
| `.claude/settings.json` | project スコープ設定。skill 共通の権限 + `aws` MCP + `hooks`（**サニタイズ済み・公開可なものだけ**） |
| `.github/workflows/` | `skill-lint.yml` + legacy Claude PR review workflows |

## ここに置かないもの

- `.claude/settings.local.json` — 個人 / マシン固有の設定・ランタイム上書き先 (`*.local.*` は `.gitignore` 済み)。公開する `.claude/settings.json` には skill 共通の最小限だけ入れる
- secrets を含むもの全て (API key、token など) と、個人 MCP の vault/絶対パス
- doc-illustrate が生成する HTML (`summaries/`)、interest-profile の生成物 (`INTERESTS.md` / `data/interests/`) — いずれも `.gitignore` 済み

## Skill と Agent の使い分け

claude-forge には 2 種類の拡張がある。**どちらも description に「やってほしいこと」を書いておくと Claude が自動で発火**するが、走る場所と役割が違う。

- **Skill** = 再利用可能な手順・ワークフロー。**メインの会話コンテキストの中で**走り、会話の文脈をそのまま引き継ぐ。対話的に進める作業に向く (PR 作成、投稿生成、図解化、レッスン宿題の記入、Issue→実装→PR の一連など)。実体は `.claude/skills/<name>/SKILL.md`。
- **Agent (subagent)** = 特定タスクを委譲する専門ワーカー。**独立した別コンテキストウィンドウで**走り、結果のサマリーだけをメインに返す。会話履歴は見えず渡されたタスクだけで動く。ツールを絞ったり別 model を割り当てたりでき、「本流を汚さず大量の出力を処理」「第三者視点で独立レビュー」「並列で探索」に向く (実装レビュー、ドキュメントレビューなど)。実体は `.claude/agents/<name>.md`。

| | Skill | Agent (subagent) |
|---|---|---|
| 走る場所 | メインの会話コンテキスト内 | 独立した別コンテキスト |
| 文脈 | 会話の流れを共有・引き継ぐ | 会話履歴は見えない (タスクだけ受け取る) |
| 返すもの | 会話の続きとして作業を進める | 結果のサマリーだけ |
| ツール / model | セッションの権限で動く | `tools` で限定・`model` も個別指定可 |
| 明示呼び | `/skill-name` | `@agent-name` |
| 向く用途 | 文脈を引き継ぐ対話的ワークフロー | 文脈隔離・独立レビュー・並列調査 |

**迷ったら skill。** 文脈の隔離・ツール制限・独立した第三者視点が欲しいとき、または出力が大量でメインの会話を汚したくないときに agent を選ぶ。skill から `Agent` tool で agent を呼んで組み合わせることもできる (例: `doc-review` skill が `doc-reviewer` agent に委譲)。([公式: Choose between subagents and main conversation](https://code.claude.com/docs/en/sub-agents#choose-between-subagents-and-main-conversation))

## 現在の skill

description で自動発火 (model-invoked)。明示的に呼びたい時は `/skill-name` でも可。

| Skill | 発動するフレーズ | 中身 |
|---|---|---|
| `ship` | 「ship して」「PR出して」「PR作って」 | branch → commit → push → `gh pr create`。**main / default branch への直接 push は絶対禁止** の hard guard 付き |
| `codex-review` | 「codex にレビュー」「セカンドオピニオン」「他のモデルにも見せて」 | 現在の差分を Codex CLI に渡し、出力を逐語的にユーザーに見せる |
| `install-pr-reviews` | 「この repo にも PR レビュー入れて」「Codex review 入れて」 | 現在 cwd の GitHub repo で Codex GitHub code review を有効化するための設定確認と案内。`AGENTS.md` の Review Guidelines を整え、automatic reviews / `@codex review` 運用へ寄せる。legacy Claude workflow コピーは明示要求時だけ |
| `aws-docs` | 「AWS の docs」「公式ドキュメントだと」「Lambda の上限って」 | `aws` MCP server で公式 docs を引いて一次ソースから回答 |
| `aws-advisor` | 「AWS で X したい」「best practice for <service>」「Well-Architected 的に」 | Well-Architected docs に基づくアーキテクチャ助言 (推奨 + tradeoffs) |
| `doc-illustrate` | 「このページ図解にして」「`<URL>` をわかりやすく」「受講生用に HTML にして」 | AWS / Claude(Anthropic) の公式ページを手描き風の図解 HTML に要約。取得は要約モデルを挟まない生テキスト優先 (`curl` / docs は `.md`)、数値・価格は逐語引用。出力は `summaries/` (gitignore 済み) |
| `make-kadai` | 「受講生のシートの6回目の課題に ALB 出して」「`<URL>` の課題欄に `<テーマ>` の課題を書き込んで」「次回の宿題作って」 | 受講生カリキュラムシートの「次回までの宿題（課題欄）」へ、テーマ指定のハンズオン課題を生成し **Sheets API で自動書き込み**。セル特定 (`N回目`/`次回までの宿題` ラベル検出) と read/write は `scripts/sheet_kadai.py` が決定的に担当、課題文は直近課題をテンプレに踏襲して生成。AWS 手順は `aws-docs`/`aws-advisor` で裏取り。読み書きは `gws` CLI 経由 (独自 OAuth クライアントで gcloud 既定クライアントの scope ブロックを回避・`gws auth login` の一度きり認証)、空きセルのみ・上書きはガード。受講生 URL は repo/memory に保存しない |
| `interest-profile` | 「プロファイル更新」「興味プロファイル sync」「興味を見せて」 | 会話履歴から興味プロファイルを `INTERESTS.md` に蓄積・更新。生成物 (`INTERESTS.md` / `data/interests/`) は会話抜粋を含むため **gitignore 済み・非公開**。[nyanta012/cc-personalize](https://github.com/nyanta012/cc-personalize) を元に改変 |
| `cc-article` | 「この記事 claude-forge に活かせる?」「`<URL>` 要約して採用できるか見て」「この Zenn/Qiita 読んで」 | Claude Code 関連記事 (Zenn / Qiita / ブログ / 英語) の URL を生テキストで読み込み、**わかりやすい要約 + claude-forge への採用診断**の 2 本立てでチャットに返す。各テクを ✅採用候補 / 🤔条件付き / ❌見送り で判定し、落とし所 (skill / 設定 / hook / agent・既存との重複) と次アクションまで提示。取得は `doc-illustrate` の `extract.py` 流用 (要約モデルを挟まない)、CC の挙動主張は公式で裏取り。**実装はせず**判断と提案まで (やるなら `skill-creator` / `update-config` / `ship` へ)。自動発火は best-effort (「要約して」系は Claude が自前で済ませがち・発火 eval で確認済み)、確実に使うなら `/cc-article <URL>` |

### Issue → 計画 → 実装 → PR ワークフロー

Issue 管理から実装・PR まで一気通貫で繋げるための一連のスキル。カレント/`~/projects/` 配下のローカルリポジトリ・`gh`・`Agent` tool ベースで動く。コードレビューは `doc-impl-reviewer` agent、計画/ドキュメントの多観点レビューは `doc-review` skill (中核は `doc-reviewer` agent に委譲) が担当する。

| Skill | 発動するフレーズ | 中身 |
|---|---|---|
| `create-issue` | 「Issue作って」「タスク登録して」「この Issue リライトして」 | カレント (or 指定) リポジトリの GitHub Issue を新規作成 / リライト。Issue 本文は**概要だけ**に絞る (実装詳細は `plan-issue` 側へ)。投稿前に冗長セクション混入をセルフチェック |
| `plan-issue` | 「実装計画を立てて」「設計して」(Issue URL とともに) | Issue を分析→インタビュー→コードベース調査 (`Agent`/Explore)→第三者が実装できる計画を **Issue コメント**として投稿。投稿前に `doc-review` でレビュー。雛形は同梱 `references/plan-template.md` |
| `implement-issue` | 「実装して」「これやって」(Issue URL / ドキュメントパスとともに) | 要件取得→対象リポ特定→**worktree で**実装→`doc-impl-reviewer` レビュー (最大5回)→`create-pr` で PR 作成→Issue コメントまで自動完走 |
| `fix-pr` | 「PR修正して」「レビュー指摘対応して」(PR URL とともに) | 既存 PR を worktree で修正→push→**CI 自動修正ループ**→PR 本文・Issue コメント更新まで自動完走 |
| `create-pr` | 「/create-pr」/ 他スキルからの委譲 | コミット→push→PR 作成→**CI 失敗の自動修正ループ**まで止まらず実行する PR エンジン。PR review は Codex GitHub automatic reviews / 必要時の `@codex review` を標準にする。対話的に出したいなら `ship`、これは `implement-issue`/`fix-pr` 用のエンジン |
| `doc-review` | 「/doc-review」/ `plan-issue` からの委譲 | **多観点レビュー*ワークフロー***。中核を `doc-reviewer` agent に委譲しつつ security/ops/cost を `Agent` tool で並列追加起動し、リーダーが集約・修正・再レビュー (最大3ラウンド)。単発の軽いドキュメントレビューは `doc-reviewer` agent を直接使う |

## 現在の agent

`.claude/agents/<name>.md` のカスタム subagent。skill と違い、メインの Claude が「このタスクはこの専門家に任せる」と判断したとき (または明示的に依頼したとき) に呼ばれる。description が委譲のトリガ。

| Agent | 役割 | いつ呼ばれる |
|---|---|---|
| `doc-impl-reviewer` | 仕様書・設計ドキュメントに基づく**実装コード**をシニアエンジニア視点で厳格レビュー。仕様整合性 / セキュリティ / エラーハンドリング / 品質を確信度 80 以上で指摘し、修正案を JSON で返す。`git diff` で対象を拾い lint / test で裏取りするが、**コードは変更しない** (Edit/Write 不所持) | 「仕様どおり実装できてるか見て」「この実装レビューして」、PR 前のセルフレビュー |
| `doc-reviewer` | 技術**ドキュメントそのもの**を、扱う技術の専門家ペルソナ (AWS / Cloudflare / K8s / security…) でレビュー。正確性 / 完全性 / 明確性 / 実用性 / 構成を、主張は公式 docs で裏取り (`WebFetch`/`WebSearch`) して指摘 | 「このドキュメントレビューして」「技術的に間違ってないか」「設計書の抜け漏れチェック」、教材・解説のレビュー |

> [公式 subagent docs](https://code.claude.com/docs/en/sub-agents) のベストプラクティス (focused / proactive な description・最小ツール・`git diff` 起点) に揃え、確信度フィルタと一次ソース検証を追加。

## skill を壊さない仕組み (lint + Stop hook)

skill は `SKILL.md` の `name` がディレクトリ名と一致していないと**呼べなくなる**（しかもエラーも出ず無言で）。これを編集ミスで踏まないよう、`tests/` に検証ハーネスを置き、`.claude/hooks/` で自動化している。

| ツール | 何をするか | いつ走るか |
|---|---|---|
| `tests/lint_skills.py` | SKILL.md を持つ全 skill の構造を**決定的に**検証（`name`↔dir 一致 / `description` 必須 / 名前重複なし / SKILL.md 欠落ディレクトリ検出 / `triggers.json` に fixture があるか）。ネット・依存なし・一瞬。`_` 始まり (`_template`) と SKILL.md 無しの retired dir (`ohayou`) は対象外 | `python3 tests/lint_skills.py` を手動、または下の hook が自動実行 |
| `.claude/hooks/skill-lint.py` | **Stop hook**。SKILL.md を編集した（git で dirty な）ターンの終了時に上の lint を走らせ、ERROR があれば `exit 2` でターンを止める | 自動（claude-forge を開いて作業中のみ）。一時的に黙らせたい時は環境変数 `SKILL_LINT_HOOK=0` |
| `.github/workflows/skill-lint.yml` | **CI lint**。同じ `lint_skills.py` を PR / main push で走らせる多層防御（Stop hook はローカル限定なので、web 編集や hook 無しマシン経由の破損もここで止まる）。label gate なし・トークン消費ゼロ | `.claude/skills/**` か `tests/**` を触る PR で自動 |
| `tests/eval_triggers.py` | `description` が意図どおり**発火**するかを `claude -p` に採点させる近似テスト（`triggers.json` の代表クエリ→期待 skill）。非決定的・トークン消費 | `description` を大きく変えた時に `python3 tests/eval_triggers.py`（`--dry-run` で無料確認） |

- lint は **全 skill をまとめて**チェックする（1 個直しただけでも全部見るので、巻き添えの破損も拾う）。
- 設計の切り分け: **lint は「発火するか」は証明しない**（構造の健全性だけ）。**eval は本物のルーターの近似**（モデルに判定させる）。詳細は [`tests/README.md`](tests/README.md)。
- パターンの出典: 「Stop で決定論ゲート → `exit 2` でブロック」は [Zenn の harness 記事](https://zenn.dev/dx_pm_product/articles/claude-code-agents-skills-hooks) の手法を、検査が一瞬な claude-forge 向けに簡略化（記事の PostToolUse marker 二段構えは省き、git-dirty スコープに）したもの。

> **skill ごとの個別 README は作らない方針。** skill の説明は **`SKILL.md` 本体**（model 向け手順 = そのままドキュメント）と、上の「現在の skill」表に集約する。込み入った人間向け補足が要る時だけ `references/` に置く（実行時のみ読まれるので model コンテキストを汚さない）。理由は二重管理とドリフトを避けるため。

## 外部プラグイン (参考)

claude-forge 自前の skill とは**別軸**。Anthropic 公式マーケットプレイス (`claude-plugins-official`) の外部プラグインを **user スコープ (グローバル `~/.claude/`)** に入れて使う。この repo にはコミットされず、claude-forge の skill ではなく全プロジェクトで使う汎用ツールという位置づけ。

> **この VSCode 拡張では `/plugin` の対話 TUI が無効** ("isn't available in this environment")。代わりにターミナルの `claude plugin …` CLI で入れる。入れた後は **`Developer: Reload Window`** (または Claude Code 再起動) で現在のセッションに反映される (プラグインは起動時読み込みのため)。

### feature-dev (導入済み)

いきなりコードを書かず、7 フェーズで機能開発を進めるワークフロー (Discovery → コードベース探索 → 要件確認 → アーキ設計 → 実装 → レビュー → 仕上げ)。同梱の agent 3 本 (`code-explorer` / `code-architect` / `code-reviewer`) が各フェーズで働く。

| 操作 | コマンド |
|---|---|
| 使う | `/feature-dev <作りたい機能>` (引数なしでも対話で進む) |
| マーケット追加 | `claude plugin marketplace add anthropics/claude-plugins-official` |
| インストール | `claude plugin install feature-dev@claude-plugins-official` |
| 確認 | `claude plugin list` / `claude plugin details feature-dev` |
| 無効化 / 削除 | `claude plugin disable feature-dev@claude-plugins-official` / `claude plugin uninstall feature-dev@claude-plugins-official` |

トークンコスト: 常時 ~243 tok/session、`/feature-dev` 起動時 ~1.6k。設定は `~/.claude/settings.json` の `enabledPlugins` / `extraKnownMarketplaces` に入り、コミット版 `.claude/settings.json` は汚さない。

> マーケットプレイス名は `claude-plugins-official` (公式)。`claude-plugin-directory` は存在しないので注意。

## MCP servers

| サーバー | どこに置くか | 用途 / 前提 |
|---|---|---|
| `aws` | **コミット版 `.claude/settings.json`**（開くと自動ロード） | AWS 公式マネージド MCP (`mcp-proxy-for-aws`)。`aws-docs` / `aws-advisor` が必要とする。前提: `uv` (`brew install uv`) と AWS credentials (`aws configure` か SSO)。リージョン default は `ap-northeast-1`（適宜編集）。IAM SigV4 でローカル credentials を使うので実行範囲は各自の IAM ポリシーに従う |
| `obsidian` | **個人用**（`~/.claude/settings.json` か `.claude/settings.local.json`） | vault パスがマシン固有なのでコミットしない。例: `npx -y mcp-obsidian /path/to/vault` |

有効化:

1. `aws` は claude-forge を開けば自動ロードされる。`aws sts get-caller-identity` が通る状態にしておく（creds が無ければ接続失敗するだけで無害）。
2. `obsidian` など個人 MCP は自分の `~/.claude/settings.json` か `.claude/settings.local.json` に足す（公開ファイルには入れない）。
3. MCP を足したら Claude Code を再起動して認識させる。

## PR レビュー運用

標準は **Codex GitHub code review**。repo に `AGENTS.md` の Review Guidelines を置き、Codex settings で Code review / Automatic reviews を有効化する。automatic reviews が未設定または不明な PR では、必要に応じて PR コメントで `@codex review` を投げる。

Codex review は GitHub workflow ファイルをこの repo からコピーする方式ではない。repository-wide の有効化は [Codex code review settings](https://chatgpt.com/codex/settings/code-review) で行う。

| 方式 | 位置づけ |
|---|---|
| Codex automatic reviews | 標準。Claude で PR 作成後、自動で high-signal review を受ける |
| `@codex review` | one-off。automatic reviews が不明な repo や、特定 PR だけ見たい時 |
| `.github/workflows/claude-review.yml` / `claude-security-review.yml` | legacy fallback。既存 repo 互換のため残すが、新規導入の標準にはしない |

**merge は手動。** Codex / workflow / ship skill は merge を絶対に行わない。レビューを読んだ上で人間が判断。

### Branch Protection: claude-forge では **off**

このリポジトリは Solo dev の dotfiles なので **Branch Protection は有効化していません**。理由:
- Codex / Claude の review は意思決定支援として使い、approve 必須の機械ゲートにはしない
- approve 必須の Protection を残すと、Solo dev では毎回 admin bypass の儀式が発生して実益がない
- main への直 push は `ship` skill 側の hard guard でガードしている (ツール強制ではなく規律で担保)

### 運用フロー (現状)

1. Claude Code の `ship` skill / `create-pr` workflow で PR 作成
2. Codex automatic reviews が有効なら Codex が PR review を post
3. automatic reviews が未設定/不明でレビューが欲しい場合は `@codex review` を PR コメント
4. **内容を見てユーザーが手動で merge**

### (参考) Branch Protection を効かせる場合

個人開発でも main への直 push や未解決コメントを強めに防ぎたい時の reference として、効かせる場合の設定例を残しておく:

```sh
gh api -X PUT /repos/<OWNER>/<REPO>/branches/main/protection --input - <<'EOF'
{
  "required_status_checks": { "strict": false, "contexts": [] },
  "enforce_admins": false,
  "required_pull_request_reviews": { "required_approving_review_count": 1, "dismiss_stale_reviews": true, "require_code_owner_reviews": false },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true,
  "required_linear_history": false
}
EOF
```

- approve 必須にすると Solo dev では毎回 admin bypass が必要になりやすいので、必要な時だけ使う
- Codex / Claude review を required approval の代替にしない。重大指摘を読むための補助線として扱う
- Free プランの **private repo では Branch Protection / Rulesets が使えない**。public または GitHub Pro が前提

### 他リポジトリに横展開する

そのリポジトリの cwd で Claude Code を起動して **「この repo にも PR レビュー入れて」** と言うと `install-pr-reviews` skill が発火し、Codex GitHub code review の有効化手順、`AGENTS.md` Review Guidelines、`@codex review` 運用を確認する。明示的に呼びたい時は `/install-pr-reviews` でも OK。

legacy の Claude GitHub Actions workflows を使い続けたい repo では、明示的に「Claude workflow をコピーして」と依頼する。その場合のみ `claude-review` ラベル、Claude Code GitHub App、`CLAUDE_CODE_OAUTH_TOKEN` / `ANTHROPIC_API_KEY` secrets を案内する。
