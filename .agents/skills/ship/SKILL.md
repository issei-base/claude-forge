---
name: ship
description: Retired Codex PR-creation stub. Do not create branches, commits, pushes, or pull requests from Codex in this repository. If the user says "ship", "PR出して", "PR作って", "open a PR", or asks Codex to create a PR, explain that PR creation is handled by Claude Code's ship workflow and offer Codex review of the local diff or an existing PR instead.
---

# ship

Codex is review-only for PR operations in this repository. PR creation is intentionally owned by Claude Code's `.claude/skills/ship` and `.claude/skills/create-pr` workflows.

## Behavior

- Do not create branches.
- Do not stage files.
- Do not commit.
- Do not push.
- Do not create pull requests.
- Do not merge pull requests.

If the user asks Codex to ship or create a PR:

1. Say that this repo keeps PR creation in Claude Code.
2. Point them to the Claude `ship` workflow.
3. Offer one of the review-only Codex paths:
   - Review the local uncommitted diff with `codex review --uncommitted`.
   - Review a feature branch with `codex review --base <default-branch>`.
   - On an existing GitHub PR, request `@codex review` if automatic reviews are not enabled.

## Completion

Keep the answer short. Do not run mutating git or `gh pr create` commands.
