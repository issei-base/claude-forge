---
name: skill-reflect
description: "Claude Code のセッションログ (jsonl) から claude-forge の自スキルが「不発・空振り・誤発火・出力をユーザーに大幅修正された」signal を拾い、該当 SKILL.md の改善案を出す skill。「最近のセッションでうちのスキルが空振りした所を拾って改善案を出して」「セッションログから skill の不発を検出して直す案を」「自分のスキルを自己改善して」「skill-reflect」「/skill-reflect」などで発動する。外部記事からの採用診断は [[cc-tune]]、新規スキルの作成は skill-creator、定量の発火回数は usage dashboard を使う。改善案を出すだけで自分ではコミットしない（適用は承認後に [[ship]] へ委譲）。単に新しいスキルを作りたいだけ・コードのバグレビューだけなら使わない。"
allowed-tools: Read, Edit, Glob, Grep, Bash(ls:*), Bash(jq:*), Bash(grep:*)
---

# skill-reflect

claude-forge の skill が実運用で「思ったように効かなかった」箇所を、**自分の Claude Code セッションログ (jsonl) から拾い上げ**、該当 `SKILL.md` への**具体的な改善案**に変換する skill。

成果物は **改善案（signal → 該当 skill → 直す SKILL.md と差分案 → 確信度）**。記事の採用診断 ([[cc-tune]]) の「自分のスキル版」にあたる。**この skill 自身はコミット・PR をしない** — 適用は承認を取ってから [[ship]] に渡す。

> **境界**: 発火回数の**定量**観測は usage dashboard（claude-forge/tools の observability sink）の仕事。skill-reflect は**定性** — 「なぜ空振ったか／何を直せば効くか」を会話から読む。新規スキルを作るのは `skill-creator`。外部記事を採用できるか診断するのは [[cc-tune]]。

## 重要: 非破壊・leak ガードの原則

- **既定は「提案まで」**。SKILL.md / triggers.json の編集はユーザーが「適用して」と承認した分だけ行う。承認なしに勝手に書き換えない。
- **改善案に leak を混ぜない**。提案する SKILL.md 文面に**絶対パス・内部 hostname・credential・受講生の個人情報・非公開 URL** を埋め込まない（claude-forge「コミットしないもの」方針）。例示が要るならプレースホルダ (`<owner>/<repo>`、`<URL>`) にする。
- **jsonl をメインに丸読みしない**。session jsonl は数 MB になる。本文スキャンは**サブエージェント (Explore / general-purpose) に委譲**し、メインには signal の構造化結果だけ返させる（pepabo / sonicgarden と同じ理由）。

## 自律実行ルール（cron / Routines / `/loop` から呼ばれた時）

- ユーザーへの確認・質問は一切しない。
- **編集は適用しない**。改善案を `data/skill-reflect/<YYYY-MM-DD>.md`（gitignore 済みの `data/` 配下）に書き出すか、価値が高い案だけ [[create-issue]] で Issue 化して人間のレビューに回す（sonicgarden 方式：適用は必ず人間ゲートを通す）。
- エラーはログに残して継続する。

---

## 手順

### Section 1: 対象セッションを特定する

既定は**直近の自分のセッション**。`<encoded-cwd>` は cwd の `/` を `-` に置換したもの。

```bash
# 現在のプロジェクトの直近セッション（mtime 降順、まず 5 本）
ls -t ~/.claude/projects/<encoded-cwd>/*.jsonl 2>/dev/null | head -5
```

- 既定スコープ = **現在のプロジェクトの直近 5 セッション**。
- ユーザーが「全プロジェクト」「先週分」等と指定したら `~/.claude/projects/*/*.jsonl` に広げる。
- claude-forge の skill は global symlink で**どのプロジェクトでも発火**しうるので、「最近 claude-forge 系の作業をしたプロジェクト」をユーザーに一言確認してよい（自律実行時は現在のプロジェクトに固定）。

### Section 2: signal を抽出する（サブエージェントに委譲）

特定した jsonl を**サブエージェントに丸投げ**し、次の「うまくいかなかった signal」を拾わせる。生ログはサブ側で消費し、メインには下記 JSON だけ返させる。

拾う signal（sonicgarden の分類を claude-forge 向けに調整）:

- **誤発火 / 空振り**: ユーザーの依頼に対し、別の skill が発火した／どの skill も発火しなかったが本来はある skill が出るべきだった（= `description` のトリガー過不足）。
- **直後の否定・修正**: skill 実行直後にユーザーが「違う」「そうじゃない」「やめて」「やり直して」と言った。
- **同じ指示の繰り返し**: 同じ修正をユーザーが何度も与えている（skill に内面化できていない手順）。
- **収束しないループ**: 同じステップが何度も走って進まない。
- **出力の大幅書き直し**: skill の出力をユーザーが大きく書き換えた／破棄した。
- **前提ミス**: skill がパス・コマンド・依存ツールの前提を間違えた。

サブエージェントに返させる形（短い JSON。長文の散文を返させない — それ自体が「完了扱い」され次工程が止まる原因になる）:

```json
{ "signals": [
  { "skill": "<claude-forge の skill 名 or 'NONE/unknown'>",
    "type": "misfire|no-fire|correction|repeat|loop|rewrite|wrong-premise",
    "evidence": "<該当やり取りの 1〜2 行要約（leak 無し）>",
    "session": "<jsonl ファイル名>",
    "confidence": "high|medium|low" }
] }
```

### Section 3: signal を改善案にマッピングする

各 signal を、該当 skill の `SKILL.md` への**具体的な一手**に変換する。`.claude/skills/<skill>/SKILL.md` を Read して現状を確認してから書く。

| signal type | 典型的な直し方 |
|---|---|
| misfire / no-fire | `description` のトリガー文を調整（発動フレーズ追加 / 紛らわしい skill との境界・「〜なら使わない」明記）。`triggers.json` に正例 or 負例を追加 |
| correction / repeat | 繰り返される指示を SKILL.md の手順・ガードに**内面化**（チェック項目化・既定値化） |
| loop | 収束条件・上限・中断条件を手順に明記 |
| rewrite | 出力フォーマット／品質基準を SKILL.md に固定 |
| wrong-premise | 前提（パス・依存ツール・バージョン）の確認ステップを追加 |

確信度の低い signal（low）は「要確認」として残し、勝手に直さない。

### Section 4: ゲート（提案を確定する前に）

- **publicity-review**: 提案する文面に leak（絶対パス・hostname・credential・PII・非公開 URL）が無いか自分で点検する。
- **発火 eval への影響**: `description` を変える提案なら、対応する `triggers.json` の正例／紛らわしい負例も**セットで**提案する。適用後に harness が緑になることを確認する:

```bash
python3 ~/projects/claude-forge/tests/lint_skills.py --strict   # 構造 lint（name↔dir・description・fixture 有無）
python3 ~/projects/claude-forge/tests/eval_triggers.py          # 発火 eval（モデル判定）
```

（SKILL.md を編集したターンは Stop hook `skill-lint.py` も `lint_skills.py` を強制する。緑になるまで直す。）

### Section 5: 提示 → 承認で適用 → ship に委譲

改善案を表で提示する:

```
## 🔁 skill-reflect: 改善案
| 該当 skill | signal | 改善案（SKILL.md の一手） | 確信度 |
|---|---|---|---|
| <skill> | <type> | <description トリガー追加 / 手順にガード 等> | high |
```

- 「どれを適用する?」と聞いて**止まる**。
- 承認された案だけ `SKILL.md`（必要なら `triggers.json`）を Edit し、Section 4 の harness を緑にする。
- README「現在の skill」表の文言に影響する変更なら 1 行直す（claude-forge の約束事）。
- コミット／PR は自分でやらず [[ship]] に渡す（コミット・PR タイトルは日本語 — [[commit-pr-japanese]]）。

## 週次自動化（任意・ローカル）

無人で回したい場合の **github 管理された一式**を `scripts/` に同梱している（絶対パスは持たず、$HOME とスクリプト位置から動的解決するので public repo でも安全）:

- `scripts/cron-run.sh` — headless `claude -p "/skill-reflect …"` を回すラッパ。提案のみ・編集/コミットはしない。
- `scripts/cron-prompt.md` — 無人実行用プロンプト（直近7日・skill を実際に呼んだ最新20セッションに絞る／高価値の案だけ cwd の repo に issue 1件起票／無ければ起票しない）。
- `scripts/install-cron.sh` — launchd plist を**ローカル生成**して登録（plist は machine-specific なのでコミットしない）。

```bash
# 既定: 毎週月曜 09:00（ローカル時刻）。曜日/時刻は env で変更可。
bash .claude/skills/skill-reflect/scripts/install-cron.sh
SKILL_REFLECT_WEEKDAY=5 SKILL_REFLECT_HOUR=17 bash .claude/skills/skill-reflect/scripts/install-cron.sh  # 例: 金17時
bash .claude/skills/skill-reflect/scripts/install-cron.sh --uninstall                                    # 解除
```

- **ローカル実行が必須**: 入力が `~/.claude/projects/*/*.jsonl`（ローカルのセッションログ）。クラウド Routines のサンドボックスからは読めない。
- **bypassPermissions で走る**: 無人実行は承認プロンプトに答えられないためゲートを切る（autonomous モードは read-only + issue 起票のみ）。許可した上で install する。
- 一時停止 `touch ~/.skill-reflect-auto/PAUSED` / モデル変更 `echo <model> > ~/.skill-reflect-auto/MODEL` / ログ `~/.skill-reflect-auto/run.log`。

## 落とし所・関連

- skill の品質ループの「定性」担当。`tests/`（lint + 発火 eval）と usage dashboard（定量）の上に乗る改善提案レイヤー。
- 無人で回したい場合は `schedule` skill / Routines から `/skill-reflect` を叩き、自律実行ルールに従って Issue 化する（適用は人間ゲート）。
- 新規スキルが要ると分かったら `skill-creator`、外部記事の採用検討は [[cc-tune]]、適用後の PR は [[ship]]。
