---
name: codex-review
description: Get a second-opinion code review from OpenAI Codex on the current git diff. Trigger when the user asks for a Codex review, a second opinion, an independent check before merging, or says things like "codex にレビューしてもらって", "セカンドオピニオン", "他のモデルにも見せて", "ship する前にチェックして", "codex review", "second opinion". Especially valuable before opening a PR or after a non-trivial refactor. Do NOT trigger for casual "review this" without a clear cross-model intent — that's just normal Claude review.
---

# codex-review

Hand the current git diff to OpenAI Codex CLI for an independent review. Codex is a separate agent with its own training; the value is **disagreement signal**, not synthesis.

## Preflight

- `which codex` must succeed. If not: tell user to install (`npm i -g @openai/codex`) and STOP.
- `git rev-parse --is-inside-work-tree` must be true.
- There must be something to review:
  - `git status --porcelain` (uncommitted) → use `codex review --uncommitted`
  - Otherwise on a feature branch → resolve default branch via `gh repo view --json defaultBranchRef -q .defaultBranchRef.name` (fallback: `main` then `master`) and use `codex review --base <default>`
  - Nothing to review → say so and STOP

## Run

Execute with stderr captured:
```sh
codex review --uncommitted 2>&1
# OR
codex review --base main 2>&1
```

If the user provided custom instructions (e.g. "認証周りに注意して"), pass them as the prompt:
```sh
codex review --uncommitted "認証周りのリグレッションに注意して" 2>&1
```

Set a generous timeout (≥5 minutes). Codex can take a while on large diffs.

## Report

- **Show the Codex output verbatim.** Do not summarize, paraphrase, or "improve" it. The user wants to see what Codex actually said, including disagreements with Claude.
- After the verbatim block, add a short coda (2-4 lines max):
  - Count of findings by severity if Codex tagged them (e.g. "3 high / 5 med / 2 low")
  - Anywhere you (Claude) **disagree** with Codex's finding — be specific about why, file:line if possible
  - Flag findings the user should look at first
- Do NOT auto-apply Codex's suggestions. The user decides what to act on.

## When errors happen

- Auth error (`Not logged in`): tell user to `codex login` and STOP
- Network/timeout: show the error verbatim and ask whether to retry
- Rate limit: show the error and suggest waiting

## Out of scope

- Don't run `codex apply` or `codex exec` here. This skill is review-only.
- Don't combine with the `ship` skill automatically. If the user wants "codex review → ship", they'll say so; do them as separate steps so they can read Codex's output between.
