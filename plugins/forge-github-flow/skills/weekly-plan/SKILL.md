---
name: weekly-plan
argument-hint: "[owner/repo | project番号]"
allowed-tools: Read, Glob, Grep, Bash(gh issue list:*), Bash(gh issue view:*), Bash(gh issue edit:*), Bash(gh label list:*), Bash(gh project:*), Bash(gh api:*), Bash(gh search issues:*), Bash(date:*), Bash(ls:*)
description: "週の初めに GitHub Project の open issue を走査し、今週着手する分を選んで Status を `Todo` に上げる週次プランニング skill。前週 Todo の積み残しを先に棚卸ししてから、Milestone・優先度・ブロック状況で候補を並べ、今週の器に入る分だけを提案して承認後に一括反映する（夜間ループに回せるものは nightly ラベルも同時に付ける）。着手の入口である `Todo` を埋めるのがこの skill の役割で、実装はしない。以下の場合に使用: (1) 「今週の計画を立てて」「今週やる issue を選んで」「週次プランニング」「週初めのトリアージして」と依頼された場合 (2) 「Todo に積んで」「今週の分を Todo に入れて」と board の Todo 補充を求められた場合 (3) 「/weekly-plan」と呼び出された場合 (4) Todo が空で着手できないときに補充を求められた場合。選んだ issue の実装は行わない — 単発の着手は [[implement-issue]]、複数の並列実装は [[orchestrate]]、新しい issue の起票は [[create-issue]]。特定 issue の実装計画を作るだけなら [[plan-issue]]。"
---

# Weekly Plan

週の初めに「今週やる分」を選び、Project board の `Todo` を満たす。**issue は作らない・実装もしない** — 既存の open issue を今週の器に割り当てるだけの skill。

> **`_shared/` の読み方:** `_shared/pr-conventions.md` は**この SKILL.md と同階層**の `_shared/` にある。パスを字句的に畳まず `<この SKILL.md のディレクトリ>/../_shared/pr-conventions.md` の形のまま Read する（symlink 経由で届いていても `..` は実体側に解決される）。畳んだパスを組み立て直して Read しない。

Status の意味と Todo ゲートの定義は [`_shared/pr-conventions.md`](../_shared/pr-conventions.md) **§9** が正本。ここには手順だけを置く。

## Usage

```
/weekly-plan [owner/repo | project番号]
```

引数なしならカレント repo の Project を対象にする。

## ワークフロー全体像

**この一覧をレスポンスにコピーし、各 Phase を完了するたびにチェックを入れて進める:**

```
- [ ] Phase 1: 対象 Project の特定
- [ ] Phase 2: 前週の棚卸し（Todo / In Progress の積み残し）
- [ ] Phase 3: 今週の器を決める
- [ ] Phase 4: 候補の抽出とランク付け
- [ ] Phase 5: 提案（唯一の停止点）
- [ ] Phase 6: 反映（Status=Todo・nightly ラベル）
- [ ] Phase 7: 報告
```

## 最重要ルール

**承認前に board へ書き込まない。** Phase 6 まで `gh issue edit` も `updateProjectV2ItemFieldValue` も撃たない。Todo の中身は週の意思決定そのもので、勝手に動かすと「自分で決めた今週」が壊れる。

**器を先に決めてから候補を並べる。** 候補を全部見てから件数を決めると必ず入れすぎる。Phase 3 → Phase 4 の順を守る。

## Phase 1: 対象 Project の特定

1. 引数が `owner/repo` ならその repo、project 番号ならその Project。引数なしならカレント repo（`git remote -v`）
2. Project とフィールド定義を取得する:

```bash
gh api graphql -f query='
  query($owner:String!,$num:Int!){ user(login:$owner){ projectV2(number:$num){ id title
    fields(first:30){ nodes{ ... on ProjectV2SingleSelectField { id name options{ id name } } } } } } }' \
  -f owner="<owner>" -F num=<project番号>
```

repo から Project 番号が分からなければ `gh project list --owner <owner>` で引く。組織 Project なら `user(login:)` を `organization(login:)` に読み替える。

**中止条件** — 次のいずれかなら Phase 2 以降に進まず、理由を伝えて終了する:

- Project が見つからない / Status フィールドが無い
- Status に `Todo` 相当の選択肢が無い（`Todo` / `Ready` / `Selected for development` 等は同一視する）。この skill は Todo を満たすためのものなので、器が無ければ成立しない。**選択肢の新規作成は提案に留め、勝手に追加しない**

## Phase 2: 前週の棚卸し

**新しく積む前に、前の週から残っているものを数える。** これを飛ばすと Todo が第二の Backlog になる。

```bash
gh api graphql -f query='
  query($id:ID!){ node(id:$id){ ... on ProjectV2 { items(first:100){ nodes{ id
    fieldValueByName(name:"Status"){ ... on ProjectV2ItemFieldSingleSelectValue { name } }
    content{ ... on Issue { number title url state updatedAt labels(first:10){ nodes{ name } }
      milestone{ title } } } } } } } }' -f id="<PROJECT_ID>"
```

`Todo` と `In Progress` の item を仕分けて提示する:

| 状態 | 扱い |
|---|---|
| `Todo` のまま着手されなかった | 今週も続けるか、`Backlog` に戻すかを Phase 5 で選ばせる。**2 週続けて残ったものは「戻す」を推奨にする**（器に対して重すぎるか、やる気がないかのどちらかで、置き続けても動かない） |
| `In Progress` のまま merge されていない | 今週の器を先に食う。件数として数え、Phase 3 の残枠から引く |
| `Todo` で close 済み | board の取りこぼし。`Done` への修正を提案する |

## Phase 3: 今週の器を決める

**候補を見る前に**、今週入れられる件数を決める。

- ユーザが稼働・件数を明示していればそれに従う
- 明示が無ければ **5 件**を既定とし、Phase 2 で数えた「`In Progress` の積み残し」を引いた数を今週の新規枠にする
- 枠が 0 以下なら新規は積まず、Phase 5 では棚卸しの結果だけを提示する（「まず今動いているものを終わらせる」と伝える）

器は目安ではなく上限として扱う。「あと 1 件くらい入りそう」で足さない。

## Phase 4: 候補の抽出とランク付け

`Backlog` の open issue を取得し、以下を**除外**する:

- `Waiting`（外部ブロック中）/ `Icebox`（見送り）/ `Done`
- **epic**（親 issue）— 器を消費するのは子。親は子が全部終われば閉じる
- 本文・コメントに未解決の依存が書かれているもの（「#N のマージ後」等）で、その依存がまだ open のもの
- ユーザ自身の判断・外部回答を待っている状態が本文から読み取れるもの（`Waiting` に落とすことを提案する）

残りを次の順で並べる:

1. **Milestone の近さ** — 直近の open milestone に属するものが先。milestone 無しは後ろ
2. **優先度ラベル** — `P1` → `P2` → `P3`
3. **前週から持ち越された Todo** — 同順位なら継続を優先する（着手済みの文脈が残っているため）

各候補に **nightly 適性**を判定する。条件は [create-issue](../create-issue/SKILL.md) **§3.1** の 4 条件が正本（ここには再掲しない）。repo に `nightly` ラベルが無ければ判定ごと skip する。

## Phase 5: 提案（唯一の停止点）

棚卸しと候補を 1 つの表で提示する。**器と選定理由を必ず添える**（なぜこれが入り、あれが落ちたかが見えないと承認の意味がない）:

```
## 今週のプラン — <owner/repo> (<週の開始日> 週)

**器**: 新規 <N> 件（既定 5 − In Progress 残 <M> 件）

### 前週からの持ち越し
| # | タイトル | 状態 | 提案 |
|---|---|---|---|
| 123 | ... | Todo (2 週目) | Backlog に戻す |

### 今週の Todo 候補
| # | タイトル | P | Milestone | nightly | 理由 |
|---|---|---|---|---|---|
| 456 | ... | P1 | 審査提出 | ○ | 直近 milestone・完了条件がテストで判定可 |

### 今週は見送り（次点）
| # | タイトル | 見送り理由 |
|---|---|---|
| 789 | ... | 器の外（次週の先頭候補） |
```

`AskUserQuestion` で 1 問だけ確認する: 「このプランで Todo を更新してよいか」（選択肢: 承認 (Recommended) / 入れ替えたい issue がある / 件数を変えたい）。

修正指示が来たら**変更点だけ**を再提示して再確認する。承認が出るまで Phase 6 に進まない。

### 無人実行（headless）の場合

プロンプトに「無人実行なので承認ステップを省略してよい」と明示されている場合に限り、この Phase を飛ばして Phase 6 に進む（launchd の月曜朝起動がこれ。2026-07-19 の issei 裁定）。**プロンプトでの明示が無ければ承認を待つ** — 承認を省くかどうかを自分で判断しない。

省略した場合も Phase 4 の表は Phase 7 の報告に必ず含める。承認を飛ばした分、後から「なぜこれが入ったか」を追えることが唯一の担保になる。

## Phase 6: 反映

承認された内容だけを書き込む。順序は「戻す → 入れる」（先に枠を空ける）:

1. `Backlog` に戻すもの: [`_shared/pr-conventions.md`](../_shared/pr-conventions.md) **§7** の共通 mutation で Status を更新
2. `Todo` に上げるもの: 同じ mutation で Status を `Todo` に更新
3. nightly 適性ありと承認されたもの: `gh issue edit <URL> --add-label nightly`
4. Phase 2 で見つかった board の取りこぼし（close 済みなのに `Todo` 等）: `Done` に修正

**Project に載っていない issue を候補にした場合**は `gh project item-add` で追加してから Status を設定する。

書き込みが FORBIDDEN で失敗したら token スコープ不足なので、`gh auth refresh -s project` を案内して該当分を skip する（他の書き込みは続行する）。

## Phase 7: 報告

- Todo に入れた件数・戻した件数・nightly を付けた件数
- 今週の Todo 一覧（番号・タイトル・nightly の有無）
- 次の一手の案内: 手で着手するなら [[implement-issue]]、まとめてやるなら [[orchestrate]]
- 書き込みを skip した項目があれば理由とともに列挙する

## エラーハンドリング

| 事象 | 対応 |
|---|---|
| Project に Status も Todo も無い | Phase 1 の中止条件。選択肢の追加を提案して終了（勝手に作らない） |
| `Backlog` に候補が 1 件も無い | 「今週積むものが無い」と報告し、起票が要るなら [[create-issue]] を案内する |
| open issue が 100 件を超える | `items(first:100)` の後続ページを `pageInfo` で辿る。取り切れない場合は取得できた範囲を明示して提案する |
| 週の途中で呼ばれた | 「週初め」を前提にせず、Phase 2 の棚卸しはそのまま行い、器は残り日数で按分する（残り 2 日なら既定 5 件 → 2 件） |
