---
name: aws-advisor
description: AWS のアーキテクチャ・設定に関する助言を、記憶ではなく Well-Architected ベストプラクティスに基づいて行う。ユーザーが AWS 構成を設計・設定・レビューしていて適切なアプローチの助言を求めているときに発動する。「S3 bucket の権限どう設計するのがいい」「RDS のバックアップ戦略」「VPC 構成見て」「ECS と Lambda どっち」「この Terraform module 安全？」「best practice for <AWS service>」「Well-Architected 的にどう」などのフレーズ。純粋な docs 検索 (パラメータ X の意味、上限値) は [[aws-docs]] を使うこと。
---

# aws-advisor

AWS のアーキテクチャ / 設定助言を、AWS 自身のベストプラクティスガイダンスに基づいて行う。`aws` MCP server がこの目的のエージェント skill を bundle しているので、それを使う。記憶からの一般論を語るのは避ける。

## Preflight

- `aws` MCP server が接続されている (`mcp__aws__*` tool が見える) こと。無ければ「MCP server を設定してください (claude-forge README 参照)」と伝えて STOP。
- 助言する **前に** ユーザーのコンテキストを確認する。以下のうち不明なものがあれば、1 個だけ focused な質問をする:
  - **ワークロード形状**: トラフィックパターン、データの機密度、チーム規模、既存スタック
  - **制約**: コスト上限、レイテンシ要件、コンプライアンス要件
  - **意思決定の範囲**: A と B の二択か、第三の選択肢にもオープンか

  これを欠くと助言が generic で役に立たない。**1 ターン遅くなってもこのステップは飛ばさない。**

## ワークフロー

1. **MCP からベストプラクティスを引く**
   - 質問に関連する Well-Architected pillar(s) を `mcp__aws__search_documentation` で検索 (Operational Excellence, Security, Reliability, Performance, Cost, Sustainability)
   - サービス特化の質問なら、そのサービスの "best practices" ページを検索 (主要サービスにはたいてい存在)
   - 関連 1〜3 ページを読む

2. **「推奨 + tradeoffs」の形で回答する。判定 (verdict) ではない**
   - 推奨アプローチを 1〜2 文で先に示す
   - 具体的な tradeoff を 2〜4 個リスト (コスト、複雑度、ロックイン、blast radius など)
   - 引いた AWS doc を markdown link で出典明示
   - 複数の妥当解があれば (例: ECS vs Lambda)、そう伝えて意思決定ルールを示す

3. **ユーザーが聞いていないリスクも flag する**
   - よくあるやつ: IAM 過剰権限、public S3、暗号化未設定、バックアップ retention 無し、single-AZ リソース、平文設定にシークレット
   - 2〜3 個までに抑える (drown させない)

## してはいけないこと

- ユーザーが明示要求しない限り `call_aws` で実リソース状態を読まない (「実際の VPC 見て」と言われたら別)。この skill は advisory であって investigative ではない。
- まだ GA か / ユーザーのリージョンで使えるか確認していないサービスを推奨しない。
- AWS docs 自体が複数の選択肢を示している場面で「唯一の正解」を断定しない — 選択肢を surface する。
- [[aws-docs]] と自動連結しない。別の intent。
