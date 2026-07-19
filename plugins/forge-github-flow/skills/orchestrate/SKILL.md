---
name: orchestrate
argument-hint: "[issue-ref... | 起票依頼]"
description: "複数の GitHub issue をまとめて並列実装するオーケストレーション skill（現場監督）。各 issue の計画とテストケース一覧を先に作らせ、★テストレビューゲート（唯一の停止点）でユーザの承認を得てから、worktree 隔離の implement-issue フローを並列（上限 3 レーン）で完走させ、全 PR の CI 収束まで監視して（赤は fix-pr を 1 回だけ）運行ボード形式で報告する。merge はこの skill では行わない。repo はレーンごとに解決するので別 repo の issue を混ぜてよい。以下で発動: (1) 複数の issue 参照とともに「まとめて着手して」「並列でやって」「並行で進めて」「全部やって」と依頼された場合 (2) 「issue を作って着手まで一気に」のように起票〜実装の一気通貫を求められた場合（内部で create-issue に委譲してから並列実装） (3) 「/orchestrate」と呼び出された場合。単発 issue の「着手して」では発動しない — それは [[implement-issue]]。起票だけなら [[create-issue]]、計画だけなら [[plan-issue]]、要所で相談しながら進めるなら [[banso]]。"
allowed-tools: Read, Write, Glob, Grep, Skill, Agent, AskUserQuestion, Bash(git:*), Bash(gh issue view:*), Bash(gh pr view:*), Bash(gh pr checks:*), Bash(gh repo clone:*), Bash(sleep:*), Bash(jq:*), Bash(tr:*), Bash(ls:*)
---

# orchestrate（まとめて着手 — 並列実装の現場監督）

複数 issue を「計画 → テストレビュー → 並列実装 → CI 収束」まで一括で運行する。**このスキルが止まる人間ゲートは テストレビュー（Phase 3・唯一の停止点）だけ。** merge はこのスキルの外で、人間か、allowlist repo では常設ループの安全ガードが判断する（下の「最重要ルール」2 を参照）。

> **`_shared/` の読み方:** `_shared/pr-conventions.md` は**この SKILL.md と同階層**の `_shared/` にある。パスを字句的に畳まず `<この SKILL.md のディレクトリ>/../_shared/pr-conventions.md` の形のまま Read する（symlink 経由で届いていても `..` は実体側に解決される）。畳んだパスを組み立て直して Read しない。

## Usage

```
/orchestrate <issue-ref...>
```

issue-ref は URL / `owner/repo#12` / カレント repo の `#12` を混在してよい。

## ワークフロー全体像

**この一覧をレスポンスにコピーし、Phase 完了ごとにチェックを入れて進める:**

```
- [ ] Phase 0: 入力判定（単発→implement-issue へ委譲 / 起票から→create-issue へ委譲）
- [ ] Phase 1: issue 取得・repo 解決・衝突分析 → レーン編成
- [ ] Phase 2: 計画 fan-out（実装しない）
- [ ] Phase 3: ★テストレビューゲート（ここで必ず停止）
- [ ] Phase 4: 実装 fan-out（並列上限 3・worktree 隔離）
- [ ] Phase 5: CI 収束監視（赤 → fix-pr を 1 回だけ）
- [ ] Phase 6: 完了報告（運行ボード）
```

## 最重要ルール

1. **停止するのは Phase 3 のみ。** それ以外はユーザ介入なしで完走する
2. **merge しない。** `gh pr merge` を実行しない（merge は人間か、allowlist repo では常設ループの安全ガードが判断する — [`_shared/pr-conventions.md`](../_shared/pr-conventions.md) §0）
3. **1 レーンの失敗で全体を止めない。** 失敗レーンは「要対応」として報告し、他レーンは完走させる
4. **オーケストレータ自身はコードを書かない。** ファイルの作成・編集はサブエージェント側の worktree のみ（オーケストレータが行う git 操作は Phase 4 冒頭の worktree 作成まで）。**Write を使うのは Phase 6 の運行ログ `~/.claude/loop-runs/run-*.json` の保存のみ** — それ以外のパスには Write しない

## Phase 0: 入力判定

- issue 参照が **2 件以上** → Phase 1 へ
- **1 件のみ** → このスキルは使わず、Skill tool で `implement-issue` に委譲して終了する
- **0 件**で「作って着手まで」の依頼 → Skill tool で `create-issue` を呼ぶ（親子分割の判断は create-issue 側の規則に従う）。親子分割されたら**子 issue** 群をレーン候補にして Phase 1 へ。**分割されず単一 issue だった場合は implement-issue に委譲して終了する**（既存 issue 参照 1 件のときと同じ扱い）

## Phase 1: issue 取得・レーン編成

1. 各 issue を取得する: `gh issue view <ref> --json title,body,labels,milestone,comments`。対応方針コメント（plan-issue の計画・完了条件）があれば最優先で採用する
2. **repo 解決はレーンごと**に行う: URL の repo → 本文の指定 → カレント repo の順（implement-issue Phase 2 と同じ基準）。ローカルは [`_shared/pr-conventions.md`](../_shared/pr-conventions.md) **§6** の手順で用意する（`~/projects/<repo>` 探索 → 無ければ clone → default branch 最新化）
3. **レーン編成**: issue ごとに 1 レーンが基本で、同じ repo の issue も並列レーンにしてよい（同一 repo の git 準備が競合する問題は、Phase 4 冒頭で worktree 作成をオーケストレータが**直列**で済ませることで塞ぐ）。ただし**変更領域が明らかに重なる issue（同じファイル群を触る）は 1 レーンに直列で束ねる** — issue 本文・計画コメントから変更領域を推定し、対象 repo を grep して裏取りする。判断がつかない場合は束ねる（安全側）
4. 並列は**最大 3 レーン**。4 本目以降はキューに置き、レーンが空くたびに投入する
5. **Todo ゲートは Phase 3 にまとめる**: 各 issue の Project Status を implement-issue §1.5 のクエリで引き、`Todo` 以外のものを控えておく（ここでは確認しない — レーンごとに聞くと停止点が増えるため）。判定基準と skip 条件は [`_shared/pr-conventions.md`](../_shared/pr-conventions.md) **§9**
6. レーン編成表（レーン番号 / issue / repo / Status / 並列・直列とその理由）を提示する。**ここでは停止しない**

## Phase 2: 計画 fan-out（実装しない）

レーンごとに Agent tool（`model: "opus"`）で計画専任エージェントを**並列**起動する。プロンプトに含めるもの:

- 対象 repo のローカルパスと issue 全文（計画コメント含む）
- 指示: 「コードベースを調査し、implement-issue の Phase 3〜5 相当の計画だけを作って返せ。返すもの: ①要件サマリー ②判断事項 ③**テストケース一覧**（自然言語・正常系/境界/エラー系に分類・issue の完了条件を全て網羅・1 行 1 ケース）④変更ファイル一覧 ⑤実装順序。**ファイルの作成・変更・worktree 作成は禁止**」

全レーンの計画が揃ってから Phase 3 へ。計画エージェントが失敗したレーンは、ゲートの提示で「計画失敗」と明示する（処遇は Phase 3 の 1 問に含めて聞く — 別途の停止は作らない）。

## Phase 3: ★テストレビューゲート（唯一の停止点）

1. レーンごとに「判断事項」と「テストケース一覧」を見出し付きで**全文**提示する（要約で省略しない — ここで見えないケースはレビューされていないのと同じ）。計画に失敗したレーンがあれば「計画失敗」と明示する
2. Phase 1-5 で控えた **Todo 外のレーン**があれば、この提示に併記する（「レーン2 (#123) は Status が Backlog — 今週の Todo 外です」）。停止点を増やさないため、専用の確認は出さない
3. `AskUserQuestion` で 1 問だけ確認する: 「この判断とテストケースで並列実装に入ってよいか」（選択肢: 承認 (Recommended) / 修正したいレーンがある / 失敗・保留レーンを除外して承認）。**Todo 外のレーンがある場合は選択肢に「Todo 外のレーンを除外して承認」を足す**（承認＝割り込みの了承として扱い、Phase 4 では改めて確認しない）
3. 修正指示が来たら該当レーンの計画・テストケースに反映し、**変更点だけ**を再提示して再確認する。承認が出るまで Phase 4 に進まない
4. 承認済みテストケース一覧が以降の**正**になる。Phase 4 のエージェントによる削除は許さない（追加は可・ただし報告必須）。遵守の検証は Phase 5 で行う（自己申告任せにしない）

## Phase 4: 実装 fan-out

**fan-out 前の準備（オーケストレータが直列で行う）:**

1. implement-issue の SKILL.md の**実体パスを解決**する: まず自分（この SKILL.md）と同じディレクトリ階層の `../implement-issue/SKILL.md` を確認し、無ければ Glob（`**/skills/implement-issue/SKILL.md`）で探す。固定パス（`~/.claude/...`）を直接書かない — 配布形態（project スコープ / plugin install / global symlink）によって置き場所が違う
2. **レーンごとの worktree を 1 本ずつ順に作成する**: repo ごとに default branch を最新化してから、implement-issue Phase 4 と同じ命名規則（`feat/yyyymmdd-<issue番号>-<機能名>` 等）でブランチを切り、`<repo>/../worktrees/<ブランチ名>` に `git worktree add` する。**同一 repo への git 操作を並列にしないための直列化はここだけで済ませる**（以降のレーンは隔離された worktree 内で完全並列にできる）

レーンごとに Agent tool（`model: "opus"`）を並列起動する（直列に束ねた issue はレーン内で順に処理させる）。プロンプトに含めるもの:

- 「`<解決済みの実体パス>` を読み、その手順に**完全に従って** <issue URL> を実装し、PR 作成・issue コメントまで完走せよ。**ただし Phase 4（Git 準備）は完了済み** — worktree `<パス>`（ブランチ `<名>`）で作業し、共有クローン側のディレクトリには触るな」
- 「Phase 5 のテストケース一覧は次の**承認済みリスト**をそのまま使う（削除禁止・追加は可で報告）: <一覧>」
- 「ユーザへの質問はできない。曖昧さは保守的判断で進め、Deviations として記録して完了報告に含めよ」
- 「完了時に返すもの: PR URL / red→green の結果（先に落とした件数 → 通した件数）/ レビュー回数と結果 / Deviations / worktree パス」

実装エージェントが失敗（エラー・途中終了）したレーンは「要対応」として記録し、他レーンは続行する。キューに issue が残っていれば、空いた枠に次を投入する。

> `doc-impl-reviewer` agent が無い環境では implement-issue 側が Phase 7 をスキップする（既存挙動に従う）。

## Phase 5: CI 収束監視・テスト遵守の検証

1. **テスト遵守の検証**: 各レーンの完了報告を Phase 3 の承認ケース一覧と突き合わせる — ①全承認ケースに対応するテストが実装されているか ②「先に落とした件数」が承認ケース数に見合うか。**回帰固定テストとして理由つきで報告されたケースには red を求めない**（実装の有無だけ確認する）。理由なき不足はテストケース削除の疑いとして、そのレーンを「要対応」に回す（緑でも merge 待ちにしない）
2. 全レーンの PR について checks の完了を待つ（[`_shared/pr-conventions.md`](../_shared/pr-conventions.md) **§5 の完了待ちループ**をそのまま使う。**`timeout` / `gtimeout` は使わない** — macOS に標準では入っておらず、待たずに素通りする）。§5 の待ちを使い切っても pending が残るレーン、`GH_ERROR`（CI 状態が取れない）になったレーンは「要対応」にする
3. **赤になった PR**: Skill tool で `fix-pr` を呼び、PR URL とともに「落ちている CI を直す」依頼を渡す。**fix-pr の呼び出しはレーンにつき 1 回まで**。fix-pr 後の赤判定は fix-pr 自身の完了報告の CI 検証結果を根拠にする（このスキルから再ポーリングしない）。それでも赤なら打ち切り、原因の見立てと次の一手を添えて「要対応」にする
4. 全レーンが「CI 緑」または「要対応」になったら Phase 6 へ

## Phase 6: 完了報告（運行ボード）

```markdown
## 運行報告 — <日時>

発火: <入力プロンプトの要約>

| レーン | issue | repo | PR | テスト (red→green) | レビュー | CI | 状態 |
|---|---|---|---|---|---|---|---|
| 1 | #497 | tsumugu | #512 | 7→7/7 | 1回PASS | 緑 | merge 待ち |

- **merge 待ち: N 本** — このスキルは merge しない。**allowlist repo では常設ループが CI 緑・安全ガード通過を条件に merge しうる**ので、「あなたが見るまで待つ」とは書かない
- 要対応: <あれば、レーン・原因の見立て・次の一手。無ければ「なし」>
- Deviations: <レーン別。無ければ「なし」>
```

報告前に各 PR を `gh pr view <PR URL> --json state,url,title` で検算する（サブエージェントの自己申告を鵜呑みにしない）。Project board の Status・issue の close は implement-issue と merge 時の自動連鎖に任せる（このスキルからは動かさない）。

**運行ログの保存**: チャットの報告と同じ内容を JSON で `~/.claude/loop-runs/run-<yyyymmdd-HHMM>.json` に保存する（dashboard の /loop 運行ボードが読む）。スキーマ:

```json
{
  "runId": "run-20260715-1745", "firedPrompt": "...", "startedAt": "...", "finishedAt": "...",
  "lanes": [{
    "issue": 485, "repo": "tsumugu", "title": "...", "pr": 520, "prUrl": "...",
    "tests": { "approved": 21, "red": 21, "green": 27, "regressionNote": "無ければ null" },
    "review": "2回でPASS", "ci": "green", "state": "merge_wait | needs_attention",
    "deviations": ["..."]
  }]
}
```

## エラーハンドリング

| 状況 | 対応 |
|------|------|
| issue 参照が 1 件だけ | implement-issue に委譲して終了 |
| 計画エージェント失敗 | ゲートで報告し「再試行 / 除外」をユーザ選択 |
| 実装エージェント失敗 | そのレーンを要対応にして他は続行 |
| fix-pr 1 回で CI が直らない | 打ち切り。見立てを添えて人間へ |
| 対象 repo が解決できない | そのレーンを要対応にして他は続行（見立てを運行ボードに記載。停止しない） |
| gh 未認証・スコープ不足 | implement-issue / create-pr 側の案内規則に従う |
