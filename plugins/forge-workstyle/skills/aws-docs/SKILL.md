---
name: aws-docs
description: 特定の AWS サービス / API / パラメータ / 上限 / 動作について、公式ドキュメントを引いて一次ソースから回答する。学習データの記憶ではなく primary source から答える。ユーザーが AWS サービスの動作・パラメータの意味・上限/クォータ・設定の正確な syntax を聞いてきたとき、または AWS に関する主張の真偽を確認したいときに発動する。「S3 の lifecycle rule の書き方」「Lambda の同時実行数上限って」「公式ドキュメントだと」「AWS の docs 見て」「is this still true about <AWS service>」などのフレーズ。具体的な API shape / 現行 limit / サービス挙動など、時間とともに変わりうる内容では記憶から答えずこの skill を使う。AWS を使うコードの実装依頼（「S3 にアップロードするコードを書いて」等）では発動しない — 仕様・上限・挙動の"確認"のときだけ。AWS が絡む採用可否の調査は [[spike]] を使う。
allowed-tools: mcp__aws__search_documentation, mcp__aws__read_documentation
---

# aws-docs

AWS の質問に学習データではなく一次ドキュメントから答える。`aws` MCP server が `search_documentation` と `read_documentation` を提供しているので、それを使う。

## Preflight

- `aws` MCP server が接続されている必要あり。利用可能な `mcp__aws__*` tool を確認。`search_documentation` と `read_documentation` が見えなければ「MCP server が有効化されていない (claude-forge README 参照)」と伝えて STOP。

## ワークフロー

1. **検索** — `mcp__aws__search_documentation`
   - まずユーザーの語をそのまま使う。AWS docs はキーワード sensitive。
   - 0 件なら同義語を試す (例: "concurrent executions" ↔ "concurrency limit")。クエリは最大 3 回まで。

2. **読む** — 関連性の高い 1〜3 件を `mcp__aws__read_documentation` で読む
   - blog や whitepaper より公式サービス doc ページを優先
   - 上限 / クォータなら Service Quotas ページを優先
   - API shape なら API Reference を優先
   - 用語の厳密さ・API/パラメータ名が要るときは **英語原典 (`/latest/...` の en ページ)** で確認する。`ja_jp` は機械翻訳で訳語がぶれることがある（数値・上限は言語非依存だが、概念名・パラメータ名は英語が正）。

3. **回答**:
   - 聞かれた具体的事実を答える。上限・パラメータ名・syntax は **verbatim で引用**
   - 出典 doc への markdown link を **必ず** 付ける (出典なしの AWS 主張は絶対 NG)
   - 自分の事前知識と docs が矛盾していたら明示する (「先ほどの説明は誤りでした — docs では X」)

## してはいけないこと

- 数字 / 上限 / クォータを paraphrase しない。AWS はこれらを変更する。verbatim 引用。
- docs で結論が出なかったら答えを作らない。「docs では確認できませんでした。最も近いページはこれ」と link で示す。
- ライブ API は叩かない。この skill は読み取り専用の docs lookup で、使うのは `mcp__aws__search_documentation` / `mcp__aws__read_documentation` のみ。WebSearch・記憶・検索 snippet で代替しない（一次ソース原則）。
