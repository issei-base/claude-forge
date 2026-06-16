/skill-reflect

これは launchd からの **週次・無人実行** です。`skill-reflect` の「自律実行ルール」に従って動いてください。

## スコープ（コストを抑えるため必ず段階的に絞る）
- 対象 skill: claude-forge 由来の自スキル（`~/.claude/skills/*/SKILL.md`）。
- 対象セッションの絞り込み（この順で必ず行う。直近7日は 100 本超ありうるので全部 deep-scan しない）:
  1. **安価にフィルタ**: 直近 7 日（mtime -7）の `~/.claude/projects/*/*.jsonl` のうち、**claude-forge の skill を実際に呼んだ**ものだけに絞る（`<command-message>` タグ・`"name":"Skill"` ツール使用・skill 名の grep で判定。grep / jq で軽く行う）。
  2. その中から **新しい順に最大 20 セッション**だけを deep-scan 対象にする。溢れた分は件数だけ RESULT 末尾に記す（`(scanned 20/NN)`）。
  3. deep-scan はサブエージェントに分配して委譲し、メインのコンテキストに jsonl を丸読みしない。

## 厳守
- 確認・質問は一切しない。
- SKILL.md / triggers.json の **編集は適用しない**（提案のみ）。コミット・PR もしない。
- jsonl はサブエージェント（Explore / general-purpose）に委譲して読む。メインのコンテキストに丸読みしない。
- 改善案に leak（絶対パス・内部 hostname・credential・個人情報・非公開 URL）を混ぜない。プレースホルダにする。

## 出力（GitHub issue 起票）
- **high 確信度かつ価値が高い改善案がある時だけ**、**現在のリポジトリ（cwd）** に issue を **1 件**起票する（create-issue skill か `gh issue create`。cwd がこの repo なので owner/repo は自動で合う）。
  - タイトル: `skill-reflect: 週次の改善提案 (<YYYY-MM-DD>)`
  - 本文: `signal → 該当 skill → 改善案（SKILL.md の一手）→ 確信度` の表。各案は第三者が implement-issue で着手できる粒度で書く。
  - ラベルが付けられるなら `skill-reflect`（無ければ付けなくてよい）。
- 既に**未クローズの同等 issue** があれば重複起票しない（`gh issue list` で確認）。
- 改善案が無い／low 確信度のみなら issue は作らない。
- 最後に必ず 1 行だけ `RESULT: <issue URL もしくは none>` を出力して終了する。
