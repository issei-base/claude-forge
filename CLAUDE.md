# CLAUDE.md

claude-forge は Claude Code のカスタム skill 集であり、**それ自体が 1 つの Claude Code プロジェクト**。この repo で作業する時の作法をまとめる。

## このリポジトリは何か

- `.claude/skills/<name>/SKILL.md` 形式の skill 群。この repo を Claude Code で開くと **project スコープ**で自動発火する。
- **この repo が skill の source of truth**。使い方は 2 通り: (1) **project スコープ** — claude-forge を開く、または使いたい skill を相手プロジェクトの `.claude/skills/` に `cp -R`。(2) **global** — 各 skill を `~/.claude/skills/<name>` に symlink すると全プロジェクトで使える（原本は claude-forge・編集は一箇所）。スクリプトは `Path(__file__).resolve()` で原本パスに解決されるので、symlink 経由でも data/config は claude-forge 側を見て壊れない。
- project 設定は `.claude/settings.json`（コミット版・skill 用の権限 + `aws` MCP）。repo を開くと自動適用される。個人 / マシン固有・ランタイム上書きは `.claude/settings.local.json`（gitignore 済み）か `~/.claude/settings.json` へ（コミット版を汚さない）。

## レイアウト

| パス | 役割 |
|---|---|
| `.claude/skills/<name>/SKILL.md` | skill 本体。description で自動発火 or `/<name>` で明示呼び |
| `.claude/skills/<name>/{assets,references,scripts}/` | skill 同梱のテンプレ・参照資料・補助スクリプト (任意) |
| `.claude/skills/_template/SKILL.md.tmpl` | 新規 skill の雛形 (`_` 始まり = lint/install/発火の対象外。`.tmpl` なので skill 登録もされない) |
| `.claude/agents/` | カスタム agent (doc-reviewer / doc-impl-reviewer / skill-reviewer / leak-auditor / fact-checker) |
| `.claude/hooks/skill-lint.py` | Stop hook。SKILL.md を編集したターン終了時に `tests/lint_skills.py` を走らせ、壊れてたら `exit 2` で停止をブロック |
| `.claude/hooks/git-push-guard.py` | PreToolUse hook (Bash)。宛先が `main`/`master` の `git push` を harness 層で deny し、「main 直 push 禁止」を ship の散文ガードから格上げ。`rm -rf`/`sudo` 等は settings の permissions.deny 済みなので扱わない |
| `tests/` | skill の検証ハーネス。`lint_skills.py` (決定的 lint・Stop hook が使用) + `eval_triggers.py` (発火 eval) + `triggers.json` (発火 fixture) + `test_scripts.py` (スクリプトの unittest) |
| `install.sh` | 全 skill + agent を `~/.claude/` に symlink (global 運用)。`_`/SKILL.md 無しの dir はスキップ。`--dry-run` 可 |
| `.claude/settings.json` | project スコープ設定（skill 共通の権限 + `aws` MCP・サニタイズ済み）。個人用上書きは `.claude/settings.local.json`（gitignore） |
| `.github/workflows/` | `skill-lint.yml` (CI lint・label gate なし) のみ。PR レビューは Codex GitHub code review に一本化（review 用 workflow は持たない） |
| `LICENSE` | MIT (cp -R / fork を許可) |
| `summaries/` | doc-illustrate の旧出力先 (`.gitignore` 済み・**追跡しない**)。現在の既定出力は repo 外の `~/Downloads/` |

## 約束事

- **スラッシュコマンドは作らない。すべて skill に統合**する (Anthropic の方針)。`commands/` は置かない。明示呼びは `/<skill-name>`。
- **skill を足す/直す時**は `.claude/skills/<name>/SKILL.md` を編集 (新規は `_template/SKILL.md.tmpl` を土台に)。frontmatter の `name` と `description` を正確に — `description` が自動発火のトリガなので、発動すべきフレーズ例を具体的に書く。`name` は必ずディレクトリ名と一致させる (ズレると skill が呼べない)。新規 skill は `tests/triggers.json` に fixture を最低 1 つ足す (正例 + 紛らわしい負例)。無いと CI lint (`--strict`) と Stop hook の W2 が指摘する。
- **`gh`/`git` 等の外部コマンドを叩く skill は `allowed-tools` で最小スコープを宣言**する (例: `create-issue` / `plan-issue` の frontmatter)。実際の権限ゲートは `.claude/settings.json` の allow-list + 対話承認 + ship の hard guard だが、SKILL.md 側にも宣言しておくと意図が明示され読み手にも優しい。
- **SKILL.md の書き方 craft (model の遵守精度を上げる)**: 禁止/例外は「使うのは X のみ。通常は Y」と断定で書く (曖昧な「〜など」は AI が多用する・稀なものは全面禁止で矯正)。難判断は「A を見る→B と比べる→C を確認」の順序つき手順にする。重複を書かず粒度を揃える。lookup 参照は `references/` に種別分割し、横断ルールは `_shared/` に集約。詳細は `_template/SKILL.md.tmpl` の「書き方の作法」。
- **SKILL.md を編集したターンは Stop hook (`skill-lint.py`) が `tests/lint_skills.py` を強制**する。`name`↔dir ズレ・description 欠落・名前重複・SKILL.md 欠落ディレクトリ (E6) があるとターンが止まる。同じ lint は CI (`.github/workflows/skill-lint.yml`) でも `--strict` で走る多層防御 (Stop hook はローカル限定)。意図的にスキップしたい時だけ環境変数 `SKILL_LINT_HOOK=0`。
- **正確さが要る skill** (`aws-docs` / `aws-advisor` / `doc-illustrate`) は、記憶ではなく一次ソースから答える。数値・価格・上限・コマンド構文は逐語引用し、出典を残す。Web 取得は要約モデルを挟まない生テキスト優先 (`curl`、docs は `.md`、AWS は `aws` MCP)。
- **コミットしないもの**: `.claude/settings.local.json` / `*.local.*`、secrets (API key・token)、個人 MCP の vault/絶対パス、`summaries/` / `INTERESTS.md` / `data/` の生成物、受講生の個人情報や非公開 URL。
- README に skill を 1 行追記する (新しい skill を足したら「現在の skill」表を更新)。

## PR / ship フロー

役割分担は固定:

| 役割 | 担当 | 発火/操作 |
|---|---|---|
| PR 作成 | Claude Code | Claude の `ship` skill / `create-pr` workflow |
| PR レビュー | Codex | Codex automatic reviews / PR コメントの `@codex review` |
| merge 判断 | 人間 | GitHub UI で内容を見て手動 merge |

PR を作る/直す skill は 3 つ。**「新規 / 既存」×「対話 / 自動」の 2 軸**で使い分ける（重複ではなく別セル）:

| | 新規 PR を作る | 既存 PR を直す |
|---|---|---|
| **対話的**（自分で見ながら） | `ship` | — |
| **自動・非対話**（止まらず完走） | `create-pr` | `fix-pr` |

- `ship` — 人が確認しながら新規 PR を出す（自然言語「ship して/PR出して」で発火）。PR 作成後は CI + Codex レビューの収束ループ（CI 最大 3 / Codex 最大 3 サイクル・`_shared/pr-conventions.md` §3/§4 共有）まで自動で回す（**merge はしない**）。create-pr との差は「作成段階が対話的か非対話か」だけで、収束ループは共通。
- `create-pr` — 主に `implement-issue` / `fix-pr` から**委譲される自動エンジン**（非対話・CI 自動修正ループ付き）。人間が直接 PR を出すなら `ship` を使う。
- `fix-pr` — **PR URL** を受け取り worktree で既存 PR を直す（コード修正 + PR 本文 + Issue コメントを同期）。新規 PR 作成には使わない。

- **コミットメッセージと PR タイトルは日本語で書く** (`ship` / `create-pr` / `fix-pr` 共通・手動コミットも)。英語の subject / title にしない。コミット本文の bullet も日本語。
- PR 作成は Claude Code に一本化する。変更を出す時は Claude の `ship` skill (「ship して」) または `create-pr` workflow を使い、feature branch → commit/push → `gh pr create` まで進める。
- PR レビューは **Codex GitHub code review** を標準にする。repository-wide automatic reviews は Codex settings で有効化し、未設定/不明なら PR 作成後に `@codex review` をコメントして one-off review を依頼する。
- Codex は PR 作成をしない。Codex 側の `.agents/skills/ship` は review-only 方針を返す stub。
- legacy の Claude GitHub Actions review workflows（`claude-review.yml` / `claude-security-review.yml`・`claude-review` ラベル）は撤去済み。PR レビューは Codex に一本化する（旧 Claude workflow を使う repo はその repo 側で自前管理する）。
- **main への直接 push は禁止** (ship skill の hard guard)。**merge は人間が手動**で行う (workflow も ship も merge しない)。
- Branch Protection はこの repo では off (理由は README 参照)。

## Dynamic Workflows を使うとき

Claude Code 本体の機能 (Opus 4.8〜・リサーチプレビュー)。タスクを JS オーケストレーションスクリプトに変換し、最大 1,000 サブエージェント (同時 16 並列) を並列実行する。**skill ではない**ので claude-forge に足すものではないが、この repo で大規模作業をする時の作法を決めておく。claude-forge の原則 (生成と評価の分離・worktree 隔離・最小権限) と地続き。

- **使いどころを選ぶ**: コードベース全体の移行 / 監査 / 横断調査など**大規模・並列向き**だけ。単一ファイルの小修正・即応が要る対話・スコープが曖昧なタスクには使わない (収束せずトークンを浪費する)。
- **起動**: プロンプトに `workflow` キーワード / 調査なら `/deep-research` / 自動判断させるなら `/effort ultracode` (常時 ON は避け、重いタスクの前後だけ)。
- **承認前に必ず `Ctrl+G` で生成スクリプトを確認**し、スコープと編集範囲が想定どおりか見てから走らせる。実行中は `/workflows` で監視し、暴走したら止める。
- **プロンプトにスコープ・出力形式・検証ルール・編集ポリシーを明示**する (例: 対象ディレクトリを限定、「各変更後にテスト」、`Do not modify any files`)。
- **破壊的変更は 2 段階に割る**: ①読み取り専用フェーズ (分析のみ・変更なし) → 結果確認 → ②変更フェーズ。ship/worktree で隔離する文化と同じ。
- **コストは通常の数倍〜数十倍**。実行前後に `/usage` で差分を確認する習慣をつける。
- 出典: [Orchestrate subagents at scale with dynamic workflows (公式 docs)](https://code.claude.com/docs/en/workflows)。リサーチプレビューなので仕様は変わりうる — 数値・操作は使う時点の docs で再確認。
