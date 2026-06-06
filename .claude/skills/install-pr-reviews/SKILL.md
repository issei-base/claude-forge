---
name: install-pr-reviews
description: 現在の cwd の GitHub リポジトリで Codex GitHub code review を有効化するための設定確認と案内を行う。ユーザーが「この repo にも PR レビュー入れて」「自動レビューを有効化して」「Codex review を入れて」「セキュリティチェックも入れて」など、PR レビュー運用を整えたい意図を示したときに発動する。legacy の Claude workflow コピーは、明示的に求められた場合だけ扱う。
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(git rev-parse:*), Bash(git remote:*), Bash(gh auth status:*), Bash(gh repo view:*)
---

# install-pr-reviews

現在の cwd にある GitHub リポジトリで、Codex GitHub code review を標準レビュー運用として使える状態にする。

Codex review は GitHub Actions workflow をコピーするのではなく、Codex cloud / Code review settings 側で repository を有効化する。repo 側でやるべきことは `AGENTS.md` の Review Guidelines 整備と、PR 作成後の `@codex review` / automatic reviews 運用の明確化。

## 手順

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

- Codex automatic reviews が有効なら、PR 作成後の追加操作は不要。
- automatic reviews が未設定/不明で one-off review が欲しい場合、PR 作成後に `gh pr comment <PR URL> --body "@codex review"` を使う。
- `claude-review` ラベルは legacy Claude workflows 用。新規 repo では標準で作らない / 付けない。

### 5. Legacy Claude workflows

ユーザーが明示的に「Claude workflow をコピーして」と言った場合だけ、旧運用として `claude-review.yml` / `claude-security-review.yml` のコピー、`claude-review` ラベル、Claude Code GitHub App、`CLAUDE_CODE_OAUTH_TOKEN` または `ANTHROPIC_API_KEY` secret の案内を行う。

既存ファイルがある場合は **絶対に上書きしない**。diff を見せてユーザー判断。

## 注意

- Codex GitHub review の repository-wide enable は Codex settings 側の操作であり、この repo のファイル編集だけでは完了しない。
- secret の値は絶対に出力ログに出さない。
- legacy Claude workflow は互換用。標準運用へ新規導入しない。
