# claude-forge

Personal Claude Code customization assets, managed in git.

```
claude-forge/
├── commands/   # slash commands → ~/.claude/commands/
├── skills/     # custom skills  → ~/.claude/skills/
├── agents/     # custom agents  → ~/.claude/agents/
├── hooks/      # hook scripts   → ~/.claude/hooks/
├── settings/
│   └── settings.example.json  # template for ~/.claude/settings.json (hand-merged)
└── install.sh  # idempotent symlink installer
```

## Setup on a new machine

```sh
git clone <this-repo-url> ~/projects/claude-forge
cd ~/projects/claude-forge
./install.sh
```

`install.sh` symlinks the four directories above into `~/.claude/`. Existing real directories there are backed up to `*.bak-<timestamp>` first, and their contents are merged forward into this repo.

`settings.json` is **not** symlinked because Claude Code rewrites it at runtime (UI preferences, oauth state, etc.). Hand-merge from `settings/settings.example.json` instead, or use the `/permissions` UI.

## What goes here

| Directory | What |
|---|---|
| `commands/` | Markdown files invoked as `/<filename>` slash commands |
| `skills/` | `<skill-name>/SKILL.md` directories that Claude can invoke |
| `agents/` | `<agent-name>.md` custom subagents |
| `hooks/` | Shell scripts referenced from `settings.json` `hooks` blocks |

## What does NOT go here

- `~/.claude/settings.json` / `settings.local.json` — runtime-mutable, machine-specific
- `~/.claude/projects/` — per-project memory and session state
- `~/.claude/plugins/` — installed via plugin marketplace, not source-controlled
- Anything containing secrets (API keys, tokens)

## Current commands

- `commands/codex-review.md` — `/codex-review` runs OpenAI Codex against the current git diff for a second-opinion review

## Current skills

| Skill | Triggers on | What it does |
|---|---|---|
| `ship` | "ship it", "PR出して", "PR作って" | Branch → commit → push → `gh pr create`. End-to-end PR workflow. |
| `codex-review` | "codex にレビューして", "セカンドオピニオン", "他のモデルにも見せて" | Hands current diff to OpenAI Codex CLI for an independent review; shows output verbatim. |
| `aws-docs` | "AWS の docs", "公式ドキュメントだと", "Lambda の上限って" | Looks up the official AWS docs via the `aws` MCP server and answers from primary sources. |
| `aws-advisor` | "AWS で X したい", "best practice for <AWS service>", "Well-Architected 的に" | Architecture/config advice grounded in AWS best-practices docs (not memory). |

## MCP servers (in `settings/settings.example.json`)

- **`obsidian`** — Obsidian vault at `/Users/issei/obsidian/issei`
- **`aws`** — official AWS managed MCP (`mcp-proxy-for-aws`). Requires `uv` (Homebrew: `brew install uv`) and local AWS credentials (`aws configure` or SSO). Region default is `ap-northeast-1` in the template — edit to taste. Auth uses IAM SigV4 against your local credentials, so what the MCP can do is bounded by your IAM policy.

To activate after `install.sh`:
1. Hand-merge the `mcpServers` block from `settings/settings.example.json` into `~/.claude/settings.json`
2. Restart Claude Code so it picks up the new servers
3. (AWS only) Make sure `aws sts get-caller-identity` returns successfully first
