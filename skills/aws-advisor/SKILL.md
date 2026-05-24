---
name: aws-advisor
description: Give AWS architecture and configuration advice grounded in Well-Architected best practices, not memory. Trigger when the user is designing, configuring, or reviewing an AWS setup and wants guidance on the right approach — e.g. "S3 bucket の権限どう設計するのがいい", "RDS のバックアップ戦略", "VPC 構成見て", "ECS と Lambda どっち", "this Terraform module 安全？", "best practice for <AWS service>", "Well-Architected 的にどう". For pure documentation lookup (what does parameter X do, what is the limit), use [[aws-docs]] instead.
---

# aws-advisor

AWS architecture/configuration advice backed by AWS's own best-practices guidance. The AWS MCP server bundles agent skills for this purpose — lean on them rather than reciting general cloud principles from memory.

## Preflight

- The `aws` MCP server must be connected (`mcp__aws__*` tools visible). If not, tell the user to set it up (see claude-forge README) and STOP.
- Clarify the user's actual context **before** advising. Ask one focused question if any of these are unknown:
  - **Workload shape**: traffic pattern, data sensitivity, team size, existing stack
  - **Constraint**: cost ceiling, latency target, compliance requirement
  - **Decision boundary**: are they choosing between A and B, or open to a third option

  Without this, advice is generic and useless. **Don't skip this step** even if it slows the response by one turn.

## Workflow

1. **Pull best-practices guidance from the MCP**
   - Use `mcp__aws__search_documentation` for the Well-Architected pillar(s) relevant to the question (Operational Excellence, Security, Reliability, Performance, Cost, Sustainability)
   - For service-specific questions, search for the service's "best practices" page (most major services have one)
   - Read 1-3 most relevant pages

2. **Frame the answer as a recommendation + tradeoffs**, not a verdict
   - Lead with the recommended approach in 1-2 sentences
   - List 2-4 concrete tradeoffs (cost, complexity, lock-in, blast radius)
   - Cite the AWS doc(s) you pulled from with markdown links
   - If multiple valid answers exist (e.g. ECS vs Lambda), say so and give the decision rule

3. **Flag risks the user didn't ask about**
   - Common ones: IAM over-privileging, public S3, missing encryption-at-rest, no backup retention, single-AZ resources, secrets in plain config
   - Limit to 2-3 — don't drown the response

## Do NOT

- Don't read AWS resource state via `call_aws` unless the user explicitly asks ("look at my actual VPC"). This skill is advisory, not investigative.
- Don't recommend services you haven't verified are still GA / available in the user's region.
- Don't give a single "right answer" when AWS docs themselves present alternatives — surface the alternatives.
- Don't combine with [[aws-docs]] automatically. They're separate intents.
