# claude-forge

Claude Code のカスタム skill 集。**それ自体が 1 つの Claude Code プロジェクト**として動く — clone して Claude Code で開けば、`.claude/skills/` の skill がそのまま有効になる (project スコープ)。

```
claude-forge/                    # 1 repo・複数プラグインの marketplace
├── .claude-plugin/
│   └── marketplace.json        # マーケットプレイス定義。owner + plugins[] (下記 3 プラグイン) を宣言
├── plugins/                    # ★ skill / agent / hook の実体はここに置く
│   ├── forge-github-flow/      #   Issue→計画→実装→PR→レビュー対応 + main 直 push 防止 hook
│   │   ├── .claude-plugin/plugin.json    # name / version / description
│   │   ├── skills/             #   create-issue, plan-issue, implement-issue, create-pr,
│   │   │                       #   ship, fix-pr, _shared
│   │   ├── agents/             #   leak-auditor.md, doc-impl-reviewer.md
│   │   └── hooks/              #   hooks.json + git-push-guard.py (${CLAUDE_PLUGIN_ROOT} 参照)
│   ├── forge-workstyle/        #   実装に被せる進め方モード
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/             #   banso, grill-me, spike, doc-review, aws-docs
│   │   └── agents/             #   doc-reviewer.md, fact-checker.md
│   └── forge-skill-dev/        #   skill 開発ツール
│       ├── .claude-plugin/plugin.json
│       └── agents/             #   skill-reviewer.md, skill-empirical-tester.md
├── .agents/
│   └── skills/ship/            # Codex repo-scoped stub。PR 作成は Claude に任せ、Codex は review-only
├── .codex/
│   ├── config.toml             # Codex project config。Stop hook で skill lint を走らせる
│   └── hooks/skill-lint.py     # Codex Stop hook: tests/lint_skills.py を実行
├── .claude/                    # ★ この repo を開いた時の project スコープ。実体は持たず plugins/ への相対 symlink
│   ├── skills/                 # <name> → ../../plugins/<plugin>/skills/<name> の symlink (13 skill + _shared)
│   │   ├── <skill-name> -> ../../plugins/<plugin>/skills/<skill-name>   # SKILL.md/scripts/references は実体側
│   │   └── _template/           #   新規 skill の雛形 (実体のまま・配布しない)
│   ├── agents/                 # <name>.md → ../../plugins/<plugin>/agents/<name>.md の symlink (6 agent)
│   ├── hooks/
│   │   ├── skill-lint.py        #   Stop hook (実体): SKILL.md 編集ターンで lint を強制 (壊れてたら exit 2 で停止)
│   │   └── git-push-guard.py -> ../../plugins/forge-github-flow/hooks/git-push-guard.py  # symlink
│   ├── settings.json           # project 設定 (権限 + aws MCP + hooks)。開くと自動適用・コミットする
│   └── settings.local.json     # 個人/マシン固有の上書き (gitignore 済み・コミットしない)
├── tests/                      # skill の検証ハーネス (lint_skills.py = 決定的・上の hook が使用 / eval_triggers.py = 発火テスト / test_scripts.py = unittest)
├── .github/workflows/          # skill-lint (CI lint) のみ。PR レビューは push 前の /codex:review (openai codex プラグイン)
├── install.sh                  # 全 skill + agent を ~/.claude に symlink (global 運用)。--dry-run 可
├── CLAUDE.md                   # この repo で作業する際の作法 (Claude / コントリビュータ向け)
├── LICENSE                     # MIT
└── README.md                   # このファイル
```

> **構成: 実体は `plugins/`、`.claude/` は相対 symlink。** skill / agent / hook の本体は各プラグイン (`plugins/<plugin>/`) に置き、この repo を Claude Code で開いた時の project スコープ (`.claude/skills` `.claude/agents` `.claude/hooks`) はそこへの**相対 symlink** で構成する。だから claude-forge を開けば従来どおり全 skill が project スコープで発火し、同時に marketplace として `claude plugin install` でも配れる。lint E7 が「plugins/ の実体 ⇔ .claude/ の symlink」の 1:1 を守る。

> **方針: スラッシュコマンドは使わず、すべて Skills に統合** (Anthropic の最近のガイドラインに沿う)。Skill は description で自動発火するが、明示呼びしたい時は `/skill-name` でも呼べる。`commands/` ディレクトリは置かない。

> **方針: claude-forge が skill の source of truth。** 使い方は 2 通り — **project スコープ** (この repo を開く / 使いたい skill を相手の `.claude/skills/` に `cp -R`) と、**global** (各 skill を `~/.claude/skills/` に symlink して全プロジェクトで使う)。global symlink でも原本は claude-forge 1 箇所なので「どこで編集したか分からなくなる」問題は起きない — 編集は常に claude-forge 側、各プロジェクトはそれを参照するだけ。

> **スコープ: この repo は開発フロー系 skill のみ。** 個人用途の skill (記事消化・Mac 環境メンテ等) は別の private repo に分離してある (2026-07-06)。両 repo とも同じ `install.sh` 方式で `~/.claude/skills/` へ symlink するので、実働はその union になる。

## PR 作成とレビューの役割分担

claude-forge では **PR 作成は Claude Code、PR レビューは Codex** に分ける。レビューは GitHub 側の automatic review ではなく、**push 前の `/codex:review`**（openai 公式 codex プラグイン `codex@openai-codex`・ユーザー起動専用）で行う（2026-07 方針転換。2026-07-11 に自作 `codex-secondopinion` skill を廃止しプラグインへ一本化）。

| 役割 | 担当 | 発火/操作 |
|---|---|---|
| PR 作成 | Claude Code | Claude の `ship` skill / `create-pr` skill |
| PR レビュー | Codex（openai codex プラグイン） | `ship` の push 前確認 → ユーザーが `/codex:review` を実行（Claude は案内のみ）。GitHub 側 automatic review は既定オフ |
| merge 判断 | 人間 | GitHub UI で内容を見て手動 merge |

Codex はこの repo では branch / commit / push / PR 作成をしない。`.agents/skills/ship` は、Codex に「PR 作って」と頼まれた時に Claude の `ship` skill へ戻すための review-only stub。

> PR 関連の詳しい運用（Codex review の有効化・Branch Protection・運用フロー）は後半の [PR レビュー運用](#pr-レビュー運用) に集約。ここは役割分担の要約のみ。

## 使い方

**1) この repo の skill を試す / 育てる**

```sh
git clone git@github.com:issei-base/claude-forge.git ~/projects/claude-forge
```

`~/projects/claude-forge` を Claude Code で開くだけ。`.claude/skills/` の skill が project スコープで有効になる。SKILL.md を編集すれば即反映 (この repo が source of truth)。

**2) プラグインとして使う (推奨・他人にも配れる)**

claude-forge は **1 repo・複数プラグインの marketplace** でもある。marketplace を追加して、欲しいプラグイン単位で入れる:

```sh
claude plugin marketplace add issei-base/claude-forge
claude plugin install forge-github-flow@claude-forge   # Issue→PR フロー + main 直 push 防止 hook
claude plugin install forge-workstyle@claude-forge      # 伴走・尋問・spike・doc-review・aws-docs
claude plugin install forge-skill-dev@claude-forge      # skill 開発ツール agent
```

プラグイン経由で入れた skill の**呼び名は `プラグイン名:skill名` に namespace 化**される (例: `forge-github-flow:ship` / `forge-workstyle:banso`)。project スコープの plain な skill 名とは衝突しない。`forge-github-flow` には main/master 直 push を deny する hook が同梱され、install 側の `settings.json` を触らずに効く。

**3) 別のプロジェクトに 1 つだけコピーする**

単発で 1 skill だけなら、そのプロジェクトの `.claude/skills/` にコピー。`.claude/skills/<name>` は今は plugins/ への **symlink** なので、`-L` を付けて**実体を辿ってコピー** (`cp -R` だと壊れた symlink がコピーされる):

```sh
mkdir -p /path/to/project/.claude/skills
cp -RL ~/projects/claude-forge/.claude/skills/ship /path/to/project/.claude/skills/
```

(Claude Code で作業中なら「ship skill をこのプロジェクトにコピーして」と頼んでもよい。) コピー先を開けば有効になる。**Windows では symlink が壊れる**ため `cp -RL` 相当が使えないことがある — その場合は上の **プラグイン install** を使うのが確実。

**4) ツールキットを全プロジェクトで使う (global symlink)**

各 skill を **user スコープ (`~/.claude/skills/`) に symlink** する。原本は claude-forge のままなので編集は一箇所・全プロジェクトに即反映。同梱の `install.sh` が全 skill + agent をまとめて symlink する (skill は `_` 始まり・SKILL.md 無しの dir をスキップ、agent は `.claude/agents/*.md` のみ対象＝`.gitkeep` 等は無視):

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
| `.claude-plugin/marketplace.json` | マーケットプレイス定義。`owner` と `plugins[]` (3 プラグイン・各 `source: ./plugins/<name>`) を宣言 |
| `plugins/<plugin>/` | **skill / agent / hook の実体**。各プラグインは `.claude-plugin/plugin.json` (name/version/description) + `skills/` + `agents/` + `hooks/` を持つ |
| `.claude/skills/` | 実体は持たず `plugins/<plugin>/skills/<name>` への**相対 symlink** (+ 配布しない雛形 `_template/`)。開くと project スコープで自動発火 or `/skill-name` で明示呼び |
| `.claude/agents/` | `plugins/<plugin>/agents/<name>.md` への**相対 symlink** |
| `.claude/hooks/` | `skill-lint.py` は実体 (repo 開発専用・配布しない)、`git-push-guard.py` は `plugins/forge-github-flow/hooks/` への **symlink**。`settings.json` の `hooks` ブロックから参照される |
| `.agents/skills/` | Codex repo-scoped skills。現状 `ship` は PR 作成を Claude に任せる review-only stub |
| `.codex/` | Codex project config / hooks。Stop hook で `tests/lint_skills.py` を走らせる |
| `tests/` | skill の検証ハーネス。`lint_skills.py` (決定的 lint・hook が使用) + `eval_triggers.py` (発火 eval) + `triggers.json` (発火 fixture) |
| `.claude/settings.json` | project スコープ設定。skill 共通の権限 + `aws` MCP + `hooks`（**サニタイズ済み・公開可なものだけ**） |
| `.github/workflows/` | `skill-lint.yml` (CI lint) のみ。PR レビューは push 前の `/codex:review` (openai codex プラグイン) |

## ここに置かないもの

- `.claude/settings.local.json` — 個人 / マシン固有の設定・ランタイム上書き先 (`*.local.*` は `.gitignore` 済み)。公開する `.claude/settings.json` には skill 共通の最小限だけ入れる
- secrets を含むもの全て (API key、token など) と、個人 MCP の vault/絶対パス
- **第三者の個人情報・非公開 URL** — 永続 memory や repo に残さない。commit 前の混入監査は `leak-auditor` agent が担う
- **個人用途の skill とその生成物** (記事消化・Mac メンテ等) — 別の private repo (claude-forge-personal) で管理し、この repo には置かない (2026-07-06 分離)

## Skill と Agent の使い分け

claude-forge には 2 種類の拡張がある。**どちらも `description` に「やってほしいこと」を書いておくと Claude がそれを見て選ぶ**が、選ばれ方・走る場所・役割が違う。skill は**あなたの発話に一致すると会話の中で自動発火**し、agent は **Claude が委譲先として選ぶ**（あなたの発話だけで直接は起動しない）。詳しい発火条件は後述の [発火のしくみ](#発火のしくみ何がキッカケで動くか)。

- **Skill** = 再利用可能な手順・ワークフロー。**メインの会話コンテキストの中で**走り、会話の文脈をそのまま引き継ぐ。対話的に進める作業に向く (PR 作成、投稿生成、図解化、Issue→実装→PR の一連など)。実体は `.claude/skills/<name>/SKILL.md`。
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

## 全体像（関係図）

skill 同士の受け渡し・振り分けと、skill → agent（委譲先・自動発火しない）の関係。

**読み方** — 形と色で役割を表す（ソリッド配色＋白文字で GitHub のライト/ダーク両方で読める）: PR 生成エンジン＝二重枠（青）、通常の skill＝角丸（灰）、AWS＝緑、agent（委譲先）＝六角（紫）。**実線＝流れ・受け渡し、点線＝agent への委譲。** 細部は下の各表を参照。

```mermaid
flowchart TB
    classDef engine fill:#2563eb,stroke:#1e40af,stroke-width:1px,color:#ffffff;
    classDef skill  fill:#475569,stroke:#1e293b,stroke-width:1px,color:#ffffff;
    classDef aws    fill:#15803d,stroke:#14532d,stroke-width:1px,color:#ffffff;
    classDef agent  fill:#7c3aed,stroke:#5b21b6,stroke-width:1px,color:#ffffff;

    %% ── デリバリ：Issue → PR ──
    subgraph DELIVERY["デリバリ : Issue → 計画 → 実装 → PR"]
        direction LR
        CIS("create-issue"):::skill
        SPK("spike"):::skill
        GRL("grill-me<br/>尋問モード"):::skill
        PLI("plan-issue"):::skill
        IMP("implement-issue"):::skill
        FPR("fix-pr"):::skill
        DRV("doc-review"):::skill
        BNS("banso<br/>伴走モード"):::skill
        CPR[["create-pr<br/>PRエンジン"]]:::engine
        SHIP[["ship<br/>対話的にPR"]]:::engine
        BAN("banso<br/>伴走モード"):::skill
    end

    %% ── AWS 一次ソース ──
    subgraph AWSG["AWS 一次ソース"]
        AWD("aws-docs"):::aws
    end

    %% ── 委譲先 agent（自動発火しない）──
    subgraph AGENTS["レビュー / 検証 agent（委譲先・自動発火しない）"]
        direction LR
        DRA{{"doc-reviewer"}}:::agent
        DIR{{"doc-impl-reviewer"}}:::agent
        SRV{{"skill-reviewer"}}:::agent
        SET{{"skill-empirical-tester"}}:::agent
        LKA{{"leak-auditor"}}:::agent
        FCK{{"fact-checker"}}:::agent
    end

    %% デリバリの流れ
    CIS --> PLI
    SPK --> PLI
    GRL --> PLI
    PLI --> IMP --> CPR
    FPR --> CPR
    BAN --> SHIP

    %% agent への委譲（点線）
    PLI -. 計画レビュー .-> DRV
    DRV -. 委譲 .-> DRA
    IMP -. コードレビュー .-> DIR
    SHIP -. 漏洩監査 .-> LKA
    SHIP -. SKILL.md変更時の作法 .-> SRV
    SHIP -. skill実測(実質変更時) .-> SET
    DRV -. 事実照合(claim単位) .-> FCK
```

> 個人系 skill (link-triage / cc-tune / playbook-sync / explain-article / doc-illustrate / make-slides / make-kadai / gemini-multimodal / interest-profile / storage-cleanup) は private repo へ分離済み。`skill-empirical-tester` は ship §3.6（新規 skill / 実質変更のとき）、`fact-checker` は doc-review の fact 観点から委譲される。加えて skill 開発・教材検証時には明示委譲でも使う。

## 発火のしくみ（何がキッカケで動くか）

skill と agent では「動き出すキッカケ」が違う。

- **skill（自動発火する）** — あなたの**自然文メッセージが SKILL.md の `description`（下表「発動するフレーズ」）に一致**すると、Claude が自動で選んで発火する。明示したいときは `/skill-name`。`description` に並べた具体フレーズが事実上のトリガなので、発動させたい言い回しをそこに書いてある。
  - 例外: `disable-model-invocation: true` を付けた skill は**自動発火せず `/skill-name` でのみ**起動する（誤発火が致命的な副作用 skill 向け。現状この設定の skill は無い）。
- **agent（自動発火しない）** — メインの Claude が**タスクを agent の `description` に照らして委譲**する／`@agent-name` で**明示呼び**する／**skill が `Agent` tool 経由で**呼ぶ、のいずれか。会話の流れだけでは起動しない。

> まとめ: skill は「あなたの言葉が description に一致 → 自動発火（＋ `/name`）」、agent は「委譲 or `@name`（会話では自動発火しない）」。各 skill の具体トリガは下の「現在の skill」表、各 agent は「現在の agent」表の『いつ呼ばれる』列を参照。

## 現在の skill

description で自動発火 (model-invoked)。明示的に呼びたい時は `/skill-name` でも可。

description の各セルは **1 行のエッセンス**。詳しい挙動・前提・ガードは各 `SKILL.md` 本体を参照。

| Skill | 発動するフレーズ | 中身 |
|---|---|---|
| `ship` | 「ship して」「PR出して」「PR作って」 | 変更を branch→commit→push→PR まで対話的に。push 直前に Codex ローカルレビューの要否を 1 回確認し、PR 作成後は CI の収束ループまで自動で回す（merge はしない）。**default branch への直接 push を hard guard で禁止** |
| `aws-docs` | 「AWS の docs」「公式ドキュメントだと」「Lambda の上限って」 | `aws` MCP server で公式 docs を引いて一次ソースから回答 |
| `spike` | 「WebSocket と SSE どっち採用すべき?」「スパイクして GO/NO-GO 出して」 | 実装前の**タイムボックス調査**で `GO`/`NO-GO`/`INCONCLUSIVE` を根拠付きで返す（意思決定ドキュメント。作ると決めた後は `plan-issue`） |
| `banso` | 「伴走して」「一緒に作ろう」「勝手に進めず要所で相談して」「私も理解しながら進めたい」 | 自律に任せきりにせず要所で止まって巻き込む**協働（伴走）モード**。①盲点マップ＋曖昧点を質問 → ②複数案をプロトタイプで提示 → ③実装計画を承認 → ④非自明な判断を **memory** に蓄積 → ⑤最後に理解確認、の 5 ゲートで止まる。`implement-issue`（止まらず完走）の**対**。PR 化は `ship` に委譲 |
| `grill-me` | 「グリルして」「質問攻めにして」「尋問して」「この計画を質問で詰めて」 | 実装前の計画・企画・PRD を**一問一答の尋問**で固める（Matt Pocock の grilling を土台に改良）。手戻りコストが高い分岐から質問・推奨案付き・事実は調べて決定だけ問う・5 問ごとに決定マップ・矛盾検知。締めは決定サマリー → ADR / `plan-issue` / `banso` へ橋渡し（**実装しない**） |

### Issue → 計画 → 実装 → PR ワークフロー

Issue 管理から実装・PR まで一気通貫で繋げるための一連のスキル。カレント/`~/projects/` 配下のローカルリポジトリ・`gh`・`Agent` tool ベースで動く。コードレビューは `doc-impl-reviewer` agent、計画/ドキュメントの多観点レビューは `doc-review` skill (中核は `doc-reviewer` agent に委譲) が担当する。

> **PR を作る 3 skill の使い分け**（迷ったらここ）:
>
> | | 新規 PR を作る | 既存 PR を直す |
> |---|---|---|
> | **対話的**（自分で見ながら） | `ship` | — |
> | **自動・非対話**（止まらず完走） | `create-pr` | `fix-pr` |
>
> 軸は「**新規 / 既存**」×「**対話 / 自動**」の 2 つだけ。`ship`=人が確認しながら新規 PR を出す（push 前に Codex ローカルレビューの要否を確認・PR 作成後は CI の収束ループまで自動・merge はしない）、`create-pr`=主に `implement-issue` 等から**委譲される自動エンジン**（同じ CI ループ付き・作成段階が非対話）、`fix-pr`=**PR URL** を受け取り worktree で既存 PR を直す（PR 本文・Issue コメントも同期）。

| Skill | 発動するフレーズ | 中身 |
|---|---|---|
| `create-issue` | 「Issue作って」「タスク登録して」「この Issue リライトして」 | GitHub Issue を新規作成 / リライト。本文は**概要だけ**に絞る（実装詳細は `plan-issue` 側へ） |
| `plan-issue` | 「実装計画を立てて」「設計して」(Issue URL とともに) | Issue を調査し、第三者が実装できる計画を **Issue コメント**として投稿（投稿前に `doc-review`） |
| `implement-issue` | 「実装して」「これやって」(Issue URL / ドキュメントパスとともに) | 要件取得→**worktree で**実装→`doc-impl-reviewer` レビュー→`create-pr` で PR→Issue コメントまで自動完走 |
| `fix-pr` | 「PR修正して」「レビュー指摘対応して」(PR URL とともに) | 既存 PR を **worktree で**修正→push→**CI 自動修正ループ**→PR 本文・Issue コメント更新まで自動完走 |
| `create-pr` | 「/create-pr」/ 他スキルからの委譲 | コミット→push→PR→**CI 自動修正ループ**まで止まらず実行する **PR エンジン**（対話なら `ship`。主に `implement-issue`/`fix-pr` 用） |
| `doc-review` | 「/doc-review」/ `plan-issue` からの委譲 | **多観点レビュー*ワークフロー***。`doc-reviewer` agent + security/ops/cost を並列起動し集約・修正・再レビュー（単発は `doc-reviewer` agent 直接） |

## 現在の agent

`.claude/agents/<name>.md` のカスタム subagent。skill と違い、メインの Claude が「このタスクはこの専門家に任せる」と判断したとき (または明示的に依頼したとき) に呼ばれる。description が委譲のトリガ。

| Agent | 役割 | いつ呼ばれる |
|---|---|---|
| `doc-impl-reviewer` | 仕様書・設計ドキュメントに基づく**実装コード**をシニアエンジニア視点で厳格レビュー。仕様整合性 / セキュリティ / エラーハンドリング / 品質を確信度 80 以上で指摘し、修正案を JSON で返す。`git diff` で対象を拾い lint / test で裏取りするが、**コードは変更しない** (Edit/Write 不所持) | 「仕様どおり実装できてるか見て」「この実装レビューして」、PR 前のセルフレビュー |
| `doc-reviewer` | 技術**ドキュメントそのもの**を、扱う技術の専門家ペルソナ (AWS / Cloudflare / K8s / security…) でレビュー。正確性 / 完全性 / 明確性 / 実用性 / 構成を、主張は公式 docs で裏取り (`WebFetch`/`WebSearch`) して指摘 | 「このドキュメントレビューして」「技術的に間違ってないか」「設計書の抜け漏れチェック」、教材・解説のレビュー |
| `skill-reviewer` | **SKILL.md** を claude-forge の craft 規約 (CLAUDE.md「約束事」+ `_template`「書き方の作法」) でレビュー。決定的 lint (E1–E6/W1–W3) が見られない**発火設計 / 断定の書き方 / 順序つき手順 / 重複・粒度 / 方針整合**を確信度 80 以上で指摘し JSON で返す。lint の指摘は再掲せず、**SKILL.md は変更しない** | 「この skill レビューして」「SKILL.md の作法チェック」「発火が誤らないか」、新規/改修 skill を ship する前 |
| `leak-auditor` | **commit 対象の差分**を「コミットしないもの」(secret/絶対パス/第三者の個人情報/非公開 URL/個人 MCP の vault/生成物/`*.local.*`) の観点で監査。漏洩は偽陰性が高コストなので「疑わしきは報告」、各検出に**本来の置き場所** (env/local/`~/.claude`/gitignore/削除) を添え、secret 値はマスク。**ファイルは変更しない** | 「漏洩チェックして」「commit 前に secret 混入見て」「これ公開して大丈夫か」、**`ship` の §3.7 ゲートから自動**（新規ファイル・設定/ドキュメントを含む diff のとき） |
| `fact-checker` | **草稿の事実主張**を claim 単位で一次ソースに照合。数値/上限/価格/コマンド構文/サービス挙動/「公式が言っている」系を、記憶でなく primary source (aws MCP/公式 docs/`curl` の生テキスト・要約取得 (WebFetch 等) は使わず取得不可なら UNVERIFIABLE) から VERIFIED/REFUTED/UNVERIFIABLE で判定し出典 URL と逐語引用を残す。偽陽性が最も危険なので**疑わしきは VERIFIED にしない**。**草稿は変更しない** | 「この教材の事実が正しいか裏取りして」「AWS の数値・上限・価格が合ってるか」「出典を確認して」、資料を外部公開する前 |
| `skill-empirical-tester` | **SKILL.md を第三者視点で実際に当てて成果物の質を実測** (empirical-prompt-tuning)。成功条件からルーブリックを作り、代表シナリオで手順を擬似トレース / 成果物を検査して各観点を採点し、失敗パターンを「症状→原因→回避ルール」のチートシートに蒸留。改善提案を返すが **SKILL.md は変更しない** (Edit/Write 不所持)。実測 (scripts/前提/出力パス) と擬似トレースを出力で明示分離。静的作法は `skill-reviewer`、発火率は `tests/eval_triggers.py` と棲み分け | 「この skill 実際に試して質を測って」「成果物を採点して」「empirical に評価して」、新規/改修 skill を ship する前 |

> [公式 subagent docs](https://code.claude.com/docs/en/sub-agents) のベストプラクティス (focused / proactive な description・最小ツール・`git diff` 起点) に揃え、確信度フィルタと一次ソース検証を追加。

## skill と運用を壊さない仕組み (hooks + lint)

skill は `SKILL.md` の `name` がディレクトリ名と一致していないと**呼べなくなる**（しかもエラーも出ず無言で）。これを編集ミスで踏まないよう、`tests/` に検証ハーネスを置き、`.claude/hooks/` で自動化している。運用ルール（main 直 push 禁止）も同じ hooks 層で機械化している。

| ツール | 何をするか | いつ走るか |
|---|---|---|
| `.claude/hooks/git-push-guard.py` | **Claude の PreToolUse hook**。Bash の `git push` を実行前に解析し、宛先が `main`/`master` なら `permissionDecision: deny` で機械ブロック（ラッパ・サブシェル・クォート経由も検知）。「main 直 push 禁止」を ship の散文ガードからツール強制に格上げしたもの | 自動（claude-forge を開いた Claude Code の全 Bash 呼び出し） |
| `tests/lint_skills.py` | SKILL.md を持つ全 skill の構造を**決定的に**検証（`name`↔dir 一致 / `description` 必須 / 名前重複なし / SKILL.md 欠落ディレクトリ検出 / `triggers.json` に fixture があるか）。`.claude/agents/` があれば **agent 層も検証**（A1–A4）。`plugins/` があれば **プラグイン層も検証**（**E7**: `plugins/<plugin>/skills\|agents` の実体 ⇔ `.claude/` の symlink が 1:1 か＝実体を足したのに symlink 忘れ・plugins 外を指す orphan symlink の両方向を検出 / **E8**: `marketplace.json` の `plugins[]` ⇔ `plugins/` 直下ディレクトリ一致・各 `plugin.json` の name==ディレクトリ名・version 存在）。ネット・依存なし・一瞬。`_` 始まり (`_template`/`_shared`) は対象外・agents/ や plugins/ が無い repo ではその層は no-op | `python3 tests/lint_skills.py` を手動、または下の hook が自動実行 |
| `.claude/hooks/skill-lint.py` | **Claude の Stop hook**。SKILL.md を編集した（git で dirty な）ターンの終了時に上の lint を走らせ、ERROR があれば `exit 2` でターンを止める | 自動（claude-forge を Claude Code で開いて作業中のみ）。一時的に黙らせたい時は環境変数 `SKILL_LINT_HOOK=0` |
| `.codex/hooks/skill-lint.py` | **Codex の Stop hook**（上の Claude hook と対）。Codex でこの repo を触った時も、ターン終了時に同じ `lint_skills.py` を走らせて壊れた SKILL.md を止める | 自動（Codex セッションで作業中のみ） |
| `.github/workflows/skill-lint.yml` | **CI lint**。同じ `lint_skills.py` を PR / main push で走らせる多層防御（Stop hook はローカル限定なので、web 編集や hook 無しマシン経由の破損もここで止まる）。label gate なし・トークン消費ゼロ | `plugins/**` `.claude/**` `.claude-plugin/**` `tests/**` を触る PR で自動 |
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
| `aws` | **コミット版 `.claude/settings.json`**（開くと自動ロード） | AWS 公式ドキュメント MCP (`awslabs.aws-documentation-mcp-server`)。`aws-docs` / `fact-checker` / `make-kadai` の一次ソース経路。ツール名は `search_documentation` / `read_documentation`。前提: `uv` (`brew install uv`) のみ — 公開 docs を引くだけなので **AWS credentials 不要**。旧 `mcp-proxy-for-aws` 構成は素の `uvx` で cryptography のビルドに失敗し起動しないため置き換えた |
| `obsidian` | **個人用**（`~/.claude/settings.json` か `.claude/settings.local.json`） | vault パスがマシン固有なのでコミットしない。例: `npx -y mcp-obsidian /path/to/vault` |

有効化:

1. `aws` は claude-forge を開けば自動ロードされる。AWS credentials は不要（公開 docs の検索/取得のみ）。初回は `uvx` がパッケージを取得するので数十秒かかることがある。
2. `obsidian` など個人 MCP は自分の `~/.claude/settings.json` か `.claude/settings.local.json` に足す（公開ファイルには入れない）。
3. MCP を足したら Claude Code を再起動して認識させる。

## PR レビュー運用

標準は **push 前の `/codex:review`**（openai 公式 codex プラグイン `codex@openai-codex`）。`ship` が push 直前に「Codex レビューをかける?」を 1 回確認し、YES ならユーザー自身が `/codex:review` を実行してから PR を出す（PR の初版を Codex-clean にする前倒し）。`/codex:review` / `/codex:adversarial-review` は `disable-model-invocation` の**ユーザー起動専用** — Claude は自然言語で頼まれても `codex` CLI を直接叩かず、コマンドの実行を案内する。

**2026-07 方針転換**: 以前は Codex GitHub automatic review + PR 作成後の応答ループ（最大 3 サイクル）を標準にしていたが、トークン消費とレビュー到着待ち（30 秒 polling × 最大 ~5 分 × サイクル数）が大きく廃止した。**PR 作成後に `@codex review` は投げない**。2026-07-11 には自作の `codex-secondopinion` skill も廃止し、openai 公式プラグインに一本化した（ジョブ管理・バックグラウンド実行・`/codex:rescue` での委譲が付くため）。

| 方式 | 位置づけ |
|---|---|
| `/codex:review` / `/codex:adversarial-review`（プラグイン・ローカル） | 標準。ship の push 前確認で YES と答えたとき / レビューしたいときにユーザーが起動 |
| Codex GitHub automatic reviews | 原則使わない。例外的に GitHub 側の自動レビューが要る repo だけ [Codex code review settings](https://chatgpt.com/codex/settings/code-review) で手動有効化（応答ループは回さない・指摘対応は人間が読んで `fix-pr` に依頼） |

**merge は手動。** Codex も Claude の PR skill（`ship` / `create-pr`）も merge を絶対に行わない。レビューを読んだ上で人間が判断。

### Branch Protection: claude-forge では **off**

このリポジトリは Solo dev の dotfiles なので **Branch Protection は有効化していません**。理由:
- Codex / Claude の review は意思決定支援として使い、approve 必須の機械ゲートにはしない
- approve 必須の Protection を残すと、Solo dev では毎回 admin bypass の儀式が発生して実益がない
- main への直 push は **PreToolUse hook (`.claude/hooks/git-push-guard.py`) が harness 層で機械 deny** し、`ship` skill 側の hard guard (散文) が二層目として補強する — Claude 経由の push はツール強制で止まる。Branch Protection が無い分、GitHub 側 (自分のシェルからの直 push) は防がない点だけ留意

### 運用フロー (現状)

1. Claude Code の `ship` skill で push 直前に Codex レビューの要否を確認（要るならユーザーが `/codex:review` を実行し、差分を直してから push）
2. `ship` / `create-pr` で PR 作成 → CI の収束ループ（最大 3 サイクル）
3. **内容を見てユーザーが手動で merge**

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

codex プラグインは user スコープでインストールしてあるので `/codex:review` はどの repo でもそのまま使える（cwd の git 差分が対象・repo 側の準備は不要）。例外的に GitHub 側の automatic review も欲しい repo は、[Codex code review settings](https://chatgpt.com/codex/settings/code-review) でその repo を手動有効化し、`AGENTS.md` に Review Guidelines を置く（旧 `install-pr-reviews` skill は方針転換で廃止 — 手順が要れば git 履歴の同 skill を参照）。
