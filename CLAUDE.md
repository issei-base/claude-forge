# CLAUDE.md

claude-forge は Claude Code のカスタム skill 集であり、**それ自体が 1 つの Claude Code プロジェクト**。この repo で作業する時の作法をまとめる。

## このリポジトリは何か

- **1 repo・複数プラグインの marketplace**。skill / agent / hook の**実体は `plugins/<plugin>/` に置き**、この repo を Claude Code で開いた時の project スコープ (`.claude/skills` `.claude/agents` `.claude/hooks`) はそこへの**相対 symlink** で構成する。だから claude-forge を開けば従来どおり全 skill が **project スコープ**で自動発火し、同時に `claude plugin install` でも配れる。プラグインは 3 つ: `forge-github-flow` (PR/Issue/レビュー体制 + main 直 push 防止 hook) / `forge-workstyle` (進め方・調査・レビューのモード) / `forge-skill-dev` (skill 開発ツール agent)。
- **スコープは開発フロー系 skill のみ**。個人用途の skill (記事消化・Mac 環境メンテ等) は private repo **claude-forge-personal** (`~/projects/claude-forge-personal`) に分離してある (2026-07-06)。新しい skill の置き場所判断: 開発ワークフロー・他人のプロジェクトでも意味がある → ここ / 自分の学習・自分のマシン・チーム内部にしか意味がない → personal 側。両 repo とも `install.sh` で `~/.claude/skills/` へ symlink するので実働は union。
- **この repo が skill の source of truth**。使い方: (1) **プラグイン** — `claude plugin marketplace add issei-base/claude-forge` → `claude plugin install forge-github-flow@claude-forge` 等（呼び名は `forge-github-flow:ship` に namespace 化）。(2) **project スコープ** — claude-forge を開く、または使いたい skill を相手プロジェクトの `.claude/skills/` に `cp -RL`（symlink 実体化。`cp -R` だと壊れた symlink がコピーされる）。(3) **global** — 各 skill を `~/.claude/skills/<name>` に symlink すると全プロジェクトで使える（原本は claude-forge・編集は一箇所）。スクリプトは `Path(__file__).resolve()` で原本パスに解決されるので、symlink 経由でも data/config は claude-forge 側を見て壊れない。
- project 設定は `.claude/settings.json`（コミット版・skill 用の権限 + `aws` MCP）。repo を開くと自動適用される。個人 / マシン固有・ランタイム上書きは `.claude/settings.local.json`（gitignore 済み）か `~/.claude/settings.json` へ（コミット版を汚さない）。

## レイアウト

| パス | 役割 |
|---|---|
| `.claude-plugin/marketplace.json` | マーケットプレイス定義。`owner` + `plugins[]` (3 プラグイン・各 `source: ./plugins/<name>`)。lint E8 が `plugins/` 直下と 1:1 一致を守る |
| `plugins/<plugin>/.claude-plugin/plugin.json` | 各プラグインの manifest (`name`==ディレクトリ名 / `version` / `description`)。中身を変えた PR では `version` を patch bump する |
| `plugins/<plugin>/skills/<name>/SKILL.md` | **skill 本体 (実体)**。`{assets,references,scripts}/` も実体側に同梱。description で自動発火 or `/<name>`（プラグイン経由なら `<plugin>:<name>`）で明示呼び |
| `plugins/forge-github-flow/hooks/` | `hooks.json` + `git-push-guard.py`（`${CLAUDE_PLUGIN_ROOT}` 参照）。プラグイン install 側の settings 配線は不要 |
| `.claude/skills/<name>` | `plugins/<plugin>/skills/<name>` への**相対 symlink** (`ln -s ../../plugins/...`)。project スコープ発火・install.sh・lint は symlink 経由で実体を見る |
| `.claude/skills/_template/SKILL.md.tmpl` | 新規 skill の雛形（**実体のまま**・配布しない。`_` 始まり = lint/install/発火の対象外。`.tmpl` なので skill 登録もされない） |
| `.claude/agents/<name>.md` | `plugins/<plugin>/agents/<name>.md` への**相対 symlink**（6 agent: doc-reviewer / doc-impl-reviewer / skill-reviewer / leak-auditor / fact-checker / skill-empirical-tester） |
| `.claude/hooks/skill-lint.py` | Stop hook（**実体**・repo 開発専用で配布しない）。SKILL.md を編集したターン終了時に `tests/lint_skills.py` を走らせ、壊れてたら `exit 2` で停止をブロック |
| `.claude/hooks/git-push-guard.py` | `plugins/forge-github-flow/hooks/git-push-guard.py` への **symlink**。PreToolUse hook (Bash) で宛先が `main`/`master` の `git push` を harness 層で deny。`rm -rf`/`sudo` 等は settings の permissions.deny 済みなので扱わない |
| `tests/` | skill の検証ハーネス。`lint_skills.py` (決定的 lint・E1–E8/W1–W3・Stop hook が使用) + `eval_triggers.py` (発火 eval) + `triggers.json` (発火 fixture) + `test_scripts.py` (スクリプトの unittest) |
| `install.sh` | 全 skill + agent を `~/.claude/` に symlink (global 運用)。`_`/SKILL.md 無しの dir はスキップ。`--dry-run` 可 |
| `.claude/settings.json` | project スコープ設定（skill 共通の権限 + `aws` MCP・サニタイズ済み）。**このタスクでは変更しない**（hook パスは symlink 経由で生きる）。個人用上書きは `.claude/settings.local.json`（gitignore） |
| `.github/workflows/` | `skill-lint.yml` (CI lint・label gate なし) のみ。PR レビューは Codex GitHub code review に一本化（review 用 workflow は持たない） |
| `LICENSE` | MIT (cp -RL / fork / plugin install を許可) |

> skill / agent の**全一覧と各トリガ**は README の「現在の skill」「現在の agent」表が source of truth。CLAUDE.md は作業作法だけを扱い、個々の skill 説明は重複させない（PR フローの 3 skill だけは作法と密結合なので下の「PR / ship フロー」で詳述する）。

## 約束事

- **スラッシュコマンドは作らない。すべて skill に統合**する (Anthropic の方針)。`commands/` は置かない。明示呼びは `/<skill-name>`。
- **新規 skill は所属プラグインを判断して `plugins/<plugin>/skills/<name>/` に実体を置き、`.claude/skills/<name>` に相対 symlink を張る**（`ln -s ../../plugins/<plugin>/skills/<name> .claude/skills/<name>`）。所属判断の目安: **PR / Issue / レビュー体制 → `forge-github-flow`** / **進め方・調査・レビューのモード → `forge-workstyle`** / **skill 開発ツール → `forge-skill-dev`**。symlink を張り忘れる/実体だけ足すと lint **E7** が止める。既存 skill を直す時も実体 (`plugins/...`) を編集する（`.claude/skills/<name>` は symlink なので実体を指す）。**プラグインの中身を変えた PR では、その `plugin.json` の `version` を patch bump する**。
- **skill を足す/直す時**は SKILL.md の frontmatter の `name` と `description` を正確に — `description` が自動発火のトリガなので、発動すべきフレーズ例を具体的に書く（新規は `_template/SKILL.md.tmpl` を土台に）。`name` は必ずディレクトリ名と一致させる (ズレると skill が呼べない)。新規 skill は `tests/triggers.json` に fixture を最低 1 つ足す (正例 + 紛らわしい負例)。無いと CI lint (`--strict`) と Stop hook の W2 が指摘する。
- **`gh`/`git` 等の外部コマンドを叩く skill は `allowed-tools` で最小スコープを宣言**する (例: `create-issue` / `plan-issue` の frontmatter)。実際の権限ゲートは `.claude/settings.json` の allow-list + 対話承認 + ship の hard guard だが、SKILL.md 側にも宣言しておくと意図が明示され読み手にも優しい。
- **SKILL.md の書き方 craft (model の遵守精度を上げる)**: 禁止/例外は「使うのは X のみ。通常は Y」と断定で書く (曖昧な「〜など」は AI が多用する・稀なものは全面禁止で矯正)。難判断は「A を見る→B と比べる→C を確認」の順序つき手順にする。重複を書かず粒度を揃える。lookup 参照は `references/` に種別分割し、横断ルールは `_shared/` に集約。詳細は `_template/SKILL.md.tmpl` の「書き方の作法」。
- **SKILL.md を編集したターンは Stop hook (`skill-lint.py`) が `tests/lint_skills.py` を強制**する。`name`↔dir ズレ・description 欠落・名前重複・SKILL.md 欠落ディレクトリ (E6) があるとターンが止まる。同じ lint は CI (`.github/workflows/skill-lint.yml`) でも `--strict` で走る多層防御 (Stop hook はローカル限定)。意図的にスキップしたい時だけ環境変数 `SKILL_LINT_HOOK=0`。**lint (決定的) が見られない発火設計・craft は `skill-reviewer` agent が担う。SKILL.md を触った `ship` は §3.6 で skill-reviewer を必ず 1 回通す**(区切りで 1 回・編集のたびではない。agent 起動はモデル判断なので hook では自動化できず、ship のゲートに寄せた)。
- **正確さが要る skill** (`aws-docs`) は、記憶ではなく一次ソースから答える。数値・価格・上限・コマンド構文は逐語引用し、出典を残す。Web 取得は要約モデルを挟まない生テキスト優先 (`curl`、docs は `.md`、AWS は `aws` MCP)。
- **コミットしないもの**: `.claude/settings.local.json` / `*.local.*`、secrets (API key・token)、個人 MCP の vault/絶対パス、skill の実行時生成物、第三者の個人情報や非公開 URL (個人系 skill とその生成物は claude-forge-personal 側で管理)。
- README に skill を 1 行追記する (新しい skill を足したら「現在の skill」表を更新)。
- **skill / agent を新規追加・改名・削除したら、`claude-forge-dashboard` の社員名鑑 `dashboard/app/lib/company.ts` にも反映する**（使い方=duty・呼び出し語=trigger まで書く。`/toolkit` は inventory-uploader が自動更新するが `/company` は静的名簿なので手動）。確認は `python3 ~/projects/claude-forge-dashboard/ops/roster_check.py`。deploy 前にも同じチェックが走り、名鑑がズレていると deploy は止まる。**プロジェクト repo の `.claude/skills` に置く project skill は DEPARTMENTS ではなく `RESIDENT`（客先常駐・kind キー無し）に足す**（roster_check は `~/.claude` 配下しか見ないため、DEPARTMENTS に入れると drift で deploy が止まる）。

## PR / ship フロー

役割分担は固定:

| 役割 | 担当 | 発火/操作 |
|---|---|---|
| PR 作成 | Claude Code / Codex どちらでも | Claude は `ship` / `create-pr` skill。Codex も同じ規約（feature branch・日本語コミット・main 直 push 禁止）で可（2026-07-11 に review-only を撤回） |
| PR レビュー | Codex（openai codex プラグイン） | `ship` の push 前確認（§3.8）→ ユーザーが `/codex:review` を実行（ユーザー起動専用・Claude は案内のみ）。GitHub 側 automatic review は既定オフ |
| merge 判断 | 人間 | GitHub UI で内容を見て手動 merge |

PR を作る/直す skill は 3 つ。**「新規 / 既存」×「対話 / 自動」の 2 軸**で使い分ける（重複ではなく別セル）:

| | 新規 PR を作る | 既存 PR を直す |
|---|---|---|
| **対話的**（自分で見ながら） | `ship` | — |
| **自動・非対話**（止まらず完走） | `create-pr` | `fix-pr` |

- `ship` — 人が確認しながら新規 PR を出す（自然言語「ship して/PR出して」で発火）。push 直前に Codex レビュー（`/codex:review`）の要否を 1 回確認し（§3.8・`_shared/pr-conventions.md` §4。YES ならユーザーのコマンド実行を待つ）、PR 作成後は CI の収束ループ（最大 3 サイクル・`_shared` §3/§5 共有）まで自動で回す（**merge はしない**）。create-pr との差は「作成段階が対話的か非対話か」だけで、CI ループは共通。
- `create-pr` — 主に `implement-issue` / `fix-pr` から**委譲される自動エンジン**（非対話・CI 自動修正ループ付き）。人間が直接 PR を出すなら `ship` を使う。
- `fix-pr` — **PR URL** を受け取り worktree で既存 PR を直す（コード修正 + PR 本文 + Issue コメントを同期）。新規 PR 作成には使わない。

- **共通の hard guard と書式規約**（main 直 push 禁止 / merge は人間 / force push・`git add -A` 禁止 / Co-Authored-By 不可 / コミット・PR は日本語）は `_shared/pr-conventions.md` §0 が唯一の定義。ここには再掲しない。main 直 push 禁止は `git-push-guard.py` hook が harness 層でも deny する（solo private repo 等で例外が要るときは settings の env `GIT_PUSH_GUARD_DISABLE=1` でその repo だけオプトアウト — claude-forge-personal が使用）。
- PR は feature branch → `gh pr create`（Claude は `ship` / `create-pr`。2026-07-11 に「PR 作成は Claude 一本化・Codex は review-only」を撤回し、Codex からも同じ規約で作ってよい。旧 stub `.agents/skills/ship` は削除済み）。PR レビューは **push 前の `/codex:review`（openai codex プラグイン・ユーザー起動専用）** を標準にする（2026-07 方針転換: GitHub 側 automatic review + PR 後の応答ループはトークン消費とレビュー待ちが大きく廃止。2026-07-11 に自作 `codex-secondopinion` skill も廃止しプラグインへ一本化。例外的に GitHub 側 review が要る repo は Codex settings で手動有効化）。**PR 作成後に `@codex review` は投げない**。
- legacy の Claude GitHub Actions review workflows（`claude-review.yml` / `claude-security-review.yml`）は**この repo では**撤去済み。旧 workflow を併用する repo（例: tsumugu は Claude + Codex の二重レビューを意図的に採用）はその repo 側で自前管理する。
- Branch Protection はこの repo では off (理由は README 参照)。

## Dynamic Workflows を使うとき

大規模並列作業 (移行・監査・横断調査) 限定の機能。作法は [docs/dynamic-workflows.md](docs/dynamic-workflows.md) を読んでから使う (使いどころの選別・`Ctrl+G` でのスクリプト確認・破壊的変更の 2 段階分割・停止条件の 3 分割・`/usage` でのコスト確認)。
