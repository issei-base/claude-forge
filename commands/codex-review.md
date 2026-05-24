---
description: Codex に現在の変更をレビューさせ、結果を要約する
argument-hint: "[base-branch | --uncommitted | --commit <sha>]"
---

# Codex Review

OpenAI Codex CLI を使って、現在の git の変更にセカンドオピニオンレビューをかけます。Claude 自身ではなく **Codex の出力をそのまま** ユーザーに見せるのが目的です。

## 実行手順

1. **対象を決める**（`$ARGUMENTS` があれば最優先）:
   - `$ARGUMENTS` が空の場合:
     - `git status --porcelain` を見て uncommitted な変更があれば → `codex review --uncommitted`
     - そうでなく現在ブランチが `main`/`master` 以外なら → `git remote show origin | grep 'HEAD branch'` などで base を特定し → `codex review --base <base>`
     - どちらにも該当しなければ「レビュー対象がありません」と伝えて終了
   - `$ARGUMENTS` がある場合: `codex review $ARGUMENTS` をそのまま実行

2. **Codex を起動**:
   - 上記コマンドを Bash で実行（`2>&1` で stderr もキャプチャ）
   - タイムアウトは長めに（最大 10 分）

3. **結果をユーザーに提示**:
   - Codex の出力を **そのまま表示**（要約しない）
   - 末尾に短く: 「Critical / High 指摘の件数」「Claude として同意するか・補足はあるか」だけ 2-3 行で添える
   - Claude 自身の追加レビューは求められない限り行わない

## 注意

- Codex は別エージェントなので、Claude のこの会話履歴は知らない。何を review しているかが文脈から不明確なら、プロンプト引数で観点を補ってあげる（例: `codex review "認証周りのリグレッションに注意して"`）
- Codex がエラーを返した場合（auth エラー、network エラー等）は、出力をそのままユーザーに見せて指示を仰ぐ
