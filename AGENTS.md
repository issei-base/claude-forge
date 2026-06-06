# claude-forge Codex Guidance

This repository contains reusable agent skills. When working here with Codex, keep changes small, reviewable, and easy to port between agent surfaces.

## PR / Ship Flow

- PR creation is handled by Claude Code's `.claude/skills/ship` and `.claude/skills/create-pr` workflows.
- Codex should not create branches, commits, pushes, or PRs for this repository's normal workflow.
- If the user asks Codex to create or open a PR, explain that PR creation is Claude-owned here and offer to review the local diff or an existing PR instead.
- Codex may request or perform reviews via Codex GitHub code review, `@codex review`, or local `codex review` when asked.
- Never run `gh pr merge`; merge is a human action.

## Review Guidelines

Codex code review should focus on high-signal issues:

- Correctness bugs, edge cases, race conditions, and null/undefined handling.
- Security regressions, auth/authz gaps, secret leakage, unsafe logging, command injection, SSRF, XSS, and unsafe dependency changes.
- Tests that miss important behavior or pass while no longer asserting the intended contract.
- Changes that violate existing repository patterns or make future maintenance materially harder.

Keep review comments specific and actionable. Avoid speculative best-practice comments unless the risk is concrete.

Write all review comments, summaries, and explanations in Japanese (日本語). Keep code identifiers, file paths, commands, and quoted code in their original form (do not translate them).

## Automation Boundary

- Codex is review-only for PR operations in this repository.
- Codex may request a one-off GitHub review with `@codex review` on an existing PR if automatic Codex reviews are not known to be enabled.
- Enabling repository-wide Codex automatic reviews is done in Codex GitHub code review settings, not only by editing files in this repository.
