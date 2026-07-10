---
name: install-pr-reviews
description: "現在の cwd の GitHub リポジトリで、Codex GitHub code review（GitHub 側 automatic review）を**オプトイン**でセットアップする skill（Codex settings 側の有効化手順の案内 + AGENTS.md の Review Guidelines 整備 + PR 作成後の運用確認。破壊操作なし）。2026-07 以降の claude-forge の既定は GitHub 側 review ではなく、push 前のローカル [[codex-secondopinion]]（ship §3.8 の確認ゲート）— この skill は「この repo は GitHub 側の自動レビューも欲しい」と敢えて選ぶ repo 専用。ユーザーが「この repo にも PR レビュー入れて」「自動レビューを有効化して」「Codex review をセットアップして」「PR レビュー運用を整えたい」「レビュー体制を作って」など、repo のレビュー体制づくりを求めたときに発動する（発動したらまず既定がローカル事前レビューであることを伝え、GitHub 側 review が本当に要るか確認する）。今ある差分を一度レビューしてほしいだけなら [[codex-secondopinion]]（そちらはレビューの実行、こちらは体制のセットアップ）。"
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(git rev-parse:*), Bash(git remote:*), Bash(gh auth status:*), Bash(gh repo view:*)
---

# install-pr-reviews

現在の cwd にある GitHub リポジトリで、Codex GitHub code review（GitHub 側 automatic review）を**オプトイン**で使える状態にする。claude-forge の既定は push 前のローカル codex-secondopinion — この skill は、それに加えて GitHub 側の自動レビューも欲しい repo だけが使う。

Codex review は GitHub Actions workflow をコピーするのではなく、Codex cloud / Code review settings 側で repository を有効化する。repo 側でやるべきことは `AGENTS.md` の Review Guidelines 整備と、有効化後の運用の明確化。

## 手順

### 0. 既定を伝えて要否を確認

有効化の案内に入る前に、必ずユーザーに次を伝えて確認する: 「claude-forge の既定は GitHub 側 review ではなく、push 前のローカル codex-secondopinion（ship の確認ゲート）。この repo では GitHub 側の自動レビュー**も**欲しい?」YES の返答が無ければここで STOP し、以降のステップに進まない。

### 1. Preflight

並列で確認:
- `git rev-parse --is-inside-work-tree` が true でなければ「git リポジトリで実行してください」と伝えて STOP
- `git remote get-url origin` が github.com を指していなければ STOP（Codex GitHub review は GitHub PR が前提）
- top-level `AGENTS.md` があるか確認。無ければ、Review Guidelines を含む最小 `AGENTS.md` の追加を提案する（勝手に作らない）
- `gh auth status` が通るなら `gh repo view --json nameWithOwner,url,defaultBranchRef` で対象 repo を特定する。未認証なら URL は `git remote get-url origin` から読み取る。

### 2. Codex 側の有効化を案内

ユーザーに次を案内する:

```
Codex GitHub code review の有効化は repo 内の workflow 追加ではなく、Codex settings で行います。

1. Codex cloud をこの repository に設定
2. https://chatgpt.com/codex/settings/code-review を開く
3. 対象 repository の Code review を有効化
4. 毎 PR で走らせたい場合は Automatic reviews も有効化
5. repo の `AGENTS.md` に Review Guidelines を置く

one-off review は PR コメントで `@codex review`。
特定観点を足すなら `@codex review for security regressions` のように書けます。
```

### 3. `AGENTS.md` の Review Guidelines を確認

既存 `AGENTS.md` がある場合:
- `Review Guidelines` / `Review guidelines` 相当の節があるか見る
- high-signal な観点（correctness / security / tests / maintainability）に絞れているか確認
- Claude 固有の workflow / label 前提だけが書かれていたら、Codex review 前提に更新する提案をする

無い場合は、次の最小形を提案する:

```md
## Review Guidelines

- Focus on correctness bugs, edge cases, security regressions, and missing tests.
- Keep comments specific and actionable.
- Avoid speculative best-practice comments unless the risk is concrete.
```

### 4. ship 運用を確認

- GitHub 側 automatic review を有効化しても、Claude の PR skill（ship / create-pr / fix-pr）は**応答ループを回さない**（`_shared/pr-conventions.md` §4）。付いた指摘は人間が読み、対応するなら [[fix-pr]] に依頼する運用になることを伝える。
- Codex review に専用ラベルは不要。旧 Claude workflow 用の `claude-review` ラベルも新規には作らない / 付けない。

## 注意

- 既定がローカル事前レビューになった経緯は 2026-07 方針転換（トークン消費とレビュー待ち時間の削減。`_shared/pr-conventions.md` §4）。要否確認は手順 0 で必ず行う。
- Codex GitHub review の repository-wide enable は Codex settings 側の操作であり、この repo のファイル編集だけでは完了しない。
- secret の値は絶対に出力ログに出さない。
