---
name: aws-docs
description: Look up the official AWS documentation for a specific service, API, parameter, limit, or behavior — and answer from primary sources rather than training-time memory. Trigger when the user asks how an AWS service works, what a parameter means, what the limits/quotas are, the exact syntax for a config, or asks to verify a claim about AWS. Phrases like "S3 の lifecycle rule の書き方", "Lambda の同時実行数上限って", "公式ドキュメントだと", "AWS の docs 見て", "is this still true about <AWS service>". Use INSTEAD of answering from memory when the question is about specific API shape, current limits, or service behavior that may have changed.
---

# aws-docs

Answer AWS questions from primary documentation, not from training data. The AWS MCP server (`aws` in mcpServers) provides `search_documentation` and `read_documentation` — use them.

## Preflight

- The `aws` MCP server must be connected. Check by listing available `mcp__aws__*` tools. If `search_documentation` and `read_documentation` are not visible, tell the user the MCP server is not active (see claude-forge README for setup) and STOP.

## Workflow

1. **Search** with `mcp__aws__search_documentation`
   - Use the user's exact terms first. AWS docs are keyword-sensitive.
   - If 0 results, try synonyms (e.g. "concurrent executions" ↔ "concurrency limit") — at most 3 query attempts.

2. **Read** the most relevant 1-3 results with `mcp__aws__read_documentation`
   - Prefer the official service docs page over blog posts or whitepapers
   - For limits/quotas, prefer the Service Quotas page
   - For API shape, prefer the API Reference

3. **Answer** the user with:
   - The specific fact they asked for, **quoted verbatim** if it's a limit, parameter name, or syntax
   - A markdown link to the source doc (always — never an unsourced AWS claim)
   - If the docs contradict your prior knowledge, say so explicitly ("My earlier statement was wrong — the docs say X")

## Do NOT

- Don't paraphrase a number/limit/quota — quote it. AWS changes these.
- Don't answer if the docs were inconclusive. Say "I couldn't find this in the docs — here's the closest page" and link.
- Don't use `call_aws` here. This skill is read-only docs lookup, not live API queries.
- Don't combine with [[aws-advisor]] automatically. If the user wants design advice, that skill triggers separately.
