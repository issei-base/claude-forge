---
name: codex-review
description: OpenAI Codex CLI を使って、現在の git 差分にセカンドオピニオンのコードレビューをかける。ユーザーが「codex にレビューしてもらって」「セカンドオピニオン」「他のモデルにも見せて」「ship する前にチェックして」「codex review」「second opinion」など、別モデルによる独立レビューを求める意図を示したときに発動する。PR を出す前や、大きめの refactor 後に特に有効。単に「これレビューして」だけなら通常の Claude レビューで対応し、この skill は発動しない。
---

# codex-review

現在の git 差分を OpenAI Codex CLI に渡して独立レビューを取る。Codex は別の学習を持つ別エージェントなので、価値は **「意見の食い違いシグナル」** にある。Claude による合成・要約ではない。

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

ユーザーが観点を指定している場合 (例:「認証周りに注意して」) はプロンプトとして渡す:
```sh
codex review --uncommitted "認証周りのリグレッションに注意して" 2>&1
```

タイムアウトは長めに (5 分以上)。大きな差分だと時間がかかる。

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
