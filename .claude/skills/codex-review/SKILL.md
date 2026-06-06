---
name: codex-review
description: OpenAI Codex CLI を使って、現在の git 差分にセカンドオピニオンのコードレビューをかける。ユーザーが「codex にレビューしてもらって」「セカンドオピニオン」「他のモデルにも見せて」「ship する前にチェックして」「codex review」「second opinion」など、別モデルによる独立レビューを求める意図を示したときに発動する。「codex に adversarial レビュー」「codex で厳しめに穴を探して」「セカンドオピニオンを批判的に」など、**別モデルによる独立レビューの意図と併せて**設計判断・セキュリティ・エッジケースを敵対的に突くことを求めたときは adversarial モードで実行する。PR を出す前や、大きめの refactor 後に特に有効。単に「これレビューして」「厳しめに見て」「批判的にレビュー」だけ（Codex を明示しない）なら通常の Claude レビューで対応し、この skill は発動しない。
allowed-tools: Read, Bash(which:*), Bash(codex review:*), Bash(git rev-parse:*), Bash(git status:*), Bash(gh repo view:*)
---

# codex-review

現在の git 差分を OpenAI Codex CLI に渡して独立レビューを取る。Codex は別の学習を持つ別エージェントなので、価値は **「意見の食い違いシグナル」** にある。Claude による合成・要約ではない。

## モード

ユーザーの言い回しから 2 モードを選ぶ。Preflight・対象判定・報告は共通で、`codex review` に渡すプロンプトだけが違う。

- **通常レビュー** (既定) — バグ・リグレッション・明らかな問題を拾う。「codex にレビュー」「セカンドオピニオン」など。
- **adversarial レビュー** — **この skill が既に選ばれている前提**（= 別モデルによる独立レビューを求められている文脈）で、「欠陥が必ずある」前提に立ち設計判断・セキュリティ・エッジケースを敵対的に突く。「codex に adversarial で」「codex で厳しめに穴を探して」「セカンドオピニオンを批判的に」など。OpenAI 公式プラグイン `codex-plugin-cc` の `/codex:adversarial-review` 相当を、プラグインを入れずに `codex review` のプロンプト指定で再現する。

Codex を明示しない単なる「厳しめにレビュー」「批判的に見て」はそもそもこの skill を発動させない（素の Claude レビューに任せる）。adversarial か迷う弱い言い回しのときは通常モードで実行し、報告の coda で「adversarial で再実行する?」と一声添える。

## Preflight

- `which codex` が成功すること。失敗したら `npm i -g @openai/codex` を案内して STOP。
- `git rev-parse --is-inside-work-tree` が true。
- レビュー対象が存在すること:
  - `git status --porcelain` に変更あり → `codex review --uncommitted`
  - feature branch にいる場合 → `gh repo view --json defaultBranchRef -q .defaultBranchRef.name` で default branch を取り、`codex review --base <default>` (フォールバック: `main` → `master`)
  - どちらも無ければ「レビュー対象が無い」と伝えて STOP

## 実行

stderr もキャプチャして実行:
```sh
codex review --uncommitted 2>&1
# または
codex review --base main 2>&1
```

ユーザーが観点を指定している場合 (例:「認証周りに注意して」) はプロンプトとして渡す。

> **重要 (codex 0.137.0 で検証)**: scope フラグ (`--uncommitted` / `--base` / `--commit`) と PROMPT は**併用できない** (`error: the argument '--uncommitted' cannot be used with '[PROMPT]'` で即エラー)。プロンプトを渡すときは scope フラグを付けず `codex review "プロンプト"` とする。この場合 codex は working tree (staged + unstaged + untracked) を既定の対象にする。

```sh
codex review "認証周りのリグレッションに注意して" 2>&1
```

> feature branch で base 差分にプロンプトを効かせる手段はこの版には無い。base 比較が要るなら**プロンプト無し**の `codex review --base <default>`、観点を効かせたいなら working tree 対象の `codex review "プロンプト"` のどちらかを選ぶ。

**adversarial モード**では、敵対的な観点を明示したプロンプトを (scope フラグ無しで) 渡す:
```sh
codex review "この差分を批判的にレビューせよ。欠陥が必ずあるという前提で、最も痛い失敗モードを探すこと。観点: (1) 設計判断の妥当性とトレードオフの検討漏れ (2) セキュリティ — 認証・認可・データ損失・レースコンディション・入力検証 (3) エッジケース・境界値・エラーパスの考慮漏れ (4) 既存挙動を壊す後方互換性リスク。表面的な lint 指摘より設計・前提の穴を優先せよ。" 2>&1
```
ユーザーが追加の観点を指定していれば、上記プロンプトの末尾に足す。

タイムアウトは長めに (5 分以上)。大きな差分だと時間がかかる (adversarial は通常より長くなりやすい)。

## 報告

- **Codex の出力をそのまま (verbatim) 見せる。** 要約・言い換え・「改善」はしない。Claude との意見の食い違いを含めて、ユーザーは Codex が実際に何と言ったかを見たい。
- verbatim ブロックの後に短い coda (最大 2〜4 行):
  - Codex が severity をタグ付けしていればその集計 (例: "high 3 / med 5 / low 2")
  - Claude として **同意しない** 指摘があれば具体的に (file:line 込みで理由)
  - 最初に見るべき指摘を強調
- Codex の提案を自動適用しない。何に対応するかはユーザーが決める。

## エラー時

- 認証エラー (`Not logged in`): `codex login` を案内して STOP
- ネットワーク / タイムアウト: エラーをそのまま見せて再試行するか確認
- レートリミット: エラーを見せて待機を提案

## スコープ外

- `codex apply` や `codex exec` はここでは使わない。この skill はレビュー専用。
- [[ship]] skill と自動連結しない。ユーザーが「codex review してから ship」と言ったら別ステップで順に実行 (途中で Codex の出力を読めるように)。
