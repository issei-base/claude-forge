# PR / Issue 共通コンベンション (claude-forge)

`ship` / `create-pr` / `fix-pr` / `create-issue` / `plan-issue` / `implement-issue` /
`orchestrate` / `weekly-plan` が共有する方針。**方針変更はこの 1 ファイルで行い**、
各 SKILL.md はここを参照する（同じ内容を 8 つの SKILL.md にコピペしてドリフト
させない、が狙い）。`_` 始まりなので lint / install / 発火の対象外。

> **読み方**: 各 skill は参照元 SKILL.md からの相対パス
> `<その SKILL.md のディレクトリ>/../_shared/pr-conventions.md` を**字句的に畳まず
> そのまま** `Read` で開いて従う（`~/.claude/skills/<name>` の symlink 経由で届いて
> いても、`..` は symlink 解決後の実体側に効くのでこの形で必ず着地する。畳んだ
> `~/.claude/skills/_shared/` は存在しない）。マシン固有の絶対パスは書かない —
> `claude plugin install` で入れたユーザの環境には該当ディレクトリが無い。
> このファイルが読めないときは、各 SKILL.md 内に残した「fallback 要点」に従う。

## 0. 共通安全ルール（ship / create-pr / fix-pr 共通の hard guard）

§3〜§5 と同じく、ここを唯一の定義とし各 SKILL.md は参照 + fallback 要点だけ残す。

- **main / master / default branch へ直接 push しない。例外なし**（`git-push-guard.py` hook が harness 層でも deny する）。フィーチャーブランチを必ず作成・使用する。
- **`gh pr merge` を実行しない。** merge は人間が GitHub UI で内容を見て手動で行う。PR の ready / draft 状態も変えない。このルールは**セッション中の skill に対するもの**で、常設ループによる自動 merge（claude-forge-personal の `tools/loops/pr_watch.py` が安全ガードを通った PR だけを merge する）とは別扱い。skill から merge しないのは、対話の流れで merge されると人間が内容を見る機会がそのまま消えるため — ループ側は repo allowlist・ラベル・パス・CI 完了を条件にして、止める場所を 1 箇所に集めている。
- **`do-not-merge` ラベルが「自動 merge を止めてほしい」の唯一の signal。** ローカルレビューが未解消のまま PR を出す場合（implement-issue の 5回FAIL / fix-pr の 3回FAIL）は、このラベルを付けたうえで未解消点をコメントに残す。**コメントだけでは止まらない** — ループはコメントを読まない。人間がラベルを外せば merge される。**draft PR は signal に使わない**（2026-07-19 変更）: CI 側のレビューは `draft == false` を条件にしていることが多く、draft にすると一番怪しい PR が無検査のまま人手に渡る。repo にこのラベルが無ければ付与は skip し、コメントだけ残す（新規作成はしない）。
- **force push しない。** `--force` / `--force-with-lease` はユーザーの明示確認がある時だけ。
- **`git add -A` / `git add .` を使わない。** 変更ファイルを明示パス指定で stage する。
- **Co-Authored-By を付与しない。**
- **コミットメッセージ・PR タイトル / 本文は日本語で書く**（本文の bullet も日本語。英語 subject にしない）。
- **secret（`.env`・key file・token 等のパターン）を commit しない。**

## 1. 本文の簡潔さ（PR 本文・Issue 本文・計画コメント 共通）

レビュアー / 第三者が「diff や実作業を始める前に欲しい情報」だけに絞る。

**含めるもの:**
- 変更・タスクの意図（なぜ）が 1-3 行で伝わる Summary / 背景
- 何が変わるか / ゴールの簡潔な要約（diff で読み取れる詳細は書かない）
- 関連 Issue / PR / ドキュメントへのリンク。**その PR で完了する Issue は `Closes #<番号>` で書く**（merge 時に GitHub が Issue を自動 close する。複数あれば並記）。完了させない関連参照は `Related: #<番号>`。裸の `#<番号>` 参照だけでは close されないので、完了 PR で Closes を省略しない。**Issue が PR と別 repo のときは `Closes <owner>/<repo>#<番号>` の完全修飾で書く**（`#<番号>` だけだと PR 側 repo の同番号 Issue を指す）

**原則含めないもの（冗長化の主因。別ドキュメント・実作業時のプレイブックの領域）:**
- ロールバック手順・ロールバック判定基準
- 検証チェックリスト・テスト手順の詳細
- 進捗チェックリスト
- リスク・懸念表
- レビュー履歴（「N 回レビュー / 結果: PASS」等）
- 運用詳細（監視ダッシュボード URL・5xx 閾値・RTO 等）
- 自明な diff / コミットログの逐一解説

> 各 skill 固有の除外項目（Issue なら実装手順・コード変更箇所、計画コメントなら
> ロールバック RTO 等）は各 SKILL.md 側に上乗せで書く。
> 例外: レビュアーが diff だけでは気付けない非自明な前提・落とし穴があるときだけ
> `Notes` に要点を。書くことが無ければ見出しごと出さない。

## 2. 投稿前セルフチェック（`gh …` 実行の直前に必ず 1 パス）

LLM は「念のため」セクションを足しがちで、§1 を見ても混入する傾向があるため、
この最終バリアを必ず通す。

**推敲（簡潔さ）— 必ず 1 パス:**
- [ ] 第三者が見て納得できる最低限の情報量に絞れているか
- [ ] 冗長な前置き・重複説明・蛇足を削ったか（同じことを 2 回書いていないか）
- [ ] 一文で済む説明を箇条書きで膨らませていないか
- [ ]（更新時）追記だけで終わらせず、既存の冗長部も削ったか

**構造:**
- [ ] §1「原則含めないもの」＋ skill 固有の除外項目が混入していないか
- [ ] 空セクション（`<!-- -->` のみ・テンプレの未使用見出し）を見出しごと削除したか
- [ ] Changes / 変更内容セクションが diff の繰り返しになっていないか

混入・空セクションが見つかったらこの時点で削ってから投稿する。

## 3. CI 失敗の自動修正分類（`ship` / `create-pr` / `fix-pr` の自動修正ループ）

| 種別 | 自動修正方針 |
|------|--------------|
| Format/Lint | `terraform fmt` / `prettier --write` / `eslint --fix` / `ruff check --fix` / `golangci-lint run --fix` 等、リポジトリの設定に従い該当ツールを実行 |
| Typecheck/Build | ログのファイル・行を読み、根本修正する。無視コメント（`// @ts-ignore`, `# type: ignore` 等）で握りつぶさない |
| Test 失敗 | 失敗テストとプロダクト側を照合し、本来の仕様に沿って修正する。**テストを単に passing に書き換えるだけは禁止**（仕様か実装のどちらが正しいかを判断する） |
| Terraform validate | 構文・参照エラーを修正する。`terraform plan` の差分そのものはユーザ判断（自動で握りつぶさない） |
| 設定/env / 外部リソース未準備 / flaky / シークレット不足 | 自動修正対象外。サイクルを打ち切ってユーザに報告する |

## 4. Codex ローカル事前レビュー（openai codex プラグイン `/codex:review` — ユーザー起動専用）

**2026-07-10 方針転換**: PR 作成後に Codex GitHub review の指摘へ自律対応する応答ループ（旧 §4）は**廃止**した。理由: (1) automatic review + 応答ループ（最大 3 サイクル）のトークン消費が大きい (2) レビュー到着待ち polling（30 秒間隔 × 最大 ~5 分 × サイクル数）が PR 完了までの待ち時間を支配する。Codex GitHub automatic review 自体も全 repo で停止する方針（Codex settings 側の操作）。

**2026-07-11 追補**: 自作の `codex-secondopinion` skill を廃止し、openai 公式の codex プラグイン（`codex@openai-codex`）に一本化した。レビューが要るときは **push / PR 作成の前に** `/codex:review`（設計判断・仮定まで突かせたいなら `/codex:adversarial-review`）を 1 回かける（PR の初版を Codex-clean にする前倒し）。両コマンドは `disable-model-invocation: true` の**ユーザー起動専用** — Claude は自然言語で「codex にレビューして」と頼まれても `codex` CLI を直接叩かず、該当コマンドの実行を**案内する**（起動経路をプラグインのジョブ管理に一本化するため）。

- **`ship`（対話フロー）**: push 直前（ship §3.8）で「Codex レビュー（`/codex:review`）をかけてから push する?」を **1 回だけ**確認する。YES → ユーザー自身が `/codex:review` を実行するのを待ち、結果を読んでから続行（Claude は代行しない）。NO → そのまま push へ。**commit のたびには聞かない**（確認は ship 1 回の区切りで 1 回）。
- **`create-pr` / `fix-pr`（非対話フロー）**: Codex レビューを組み込まない（ユーザー起動専用コマンドは「ユーザ介入なしで完走」の契約と両立しない）。要るときはユーザーが skill 起動前に `/codex:review` を済ませるか、PR 作成後に自分で実行する。
- **PR 作成後に `@codex review` をコメントしない。** automatic review の有無確認・レビュー到着待ち polling もしない。
- 例外的に GitHub 側 automatic review を残した repo（Codex settings で手動有効化）でも、**応答ループは回さない** — 付いた指摘は人間が読み、対応するなら [[fix-pr]] に依頼する。

## 5. CI 起動待ち・検出（`ship` / `create-pr` / `fix-pr` の CI 自動修正ループの入口）

§3 が「CI が失敗したらどう直すか」を定義するのに対し、ここは「そもそも CI が有るか・起動したか」の判定を唯一化する（各 SKILL.md にコピペしてドリフトさせない）。

push 直後は CI run がまだ登録されていないことがある。**15 秒 1 回の `no checks reported` を「CI なし」と確定してはいけない** — 後から起動する CI を取りこぼし、§3 の自動修正ループごと空振りする。次の順で判定する:

1. **起動待ち** — `gh pr checks <PR URL>` を **15 秒間隔で最大 ~90 秒**見て、check が 1 つでも現れたら「CI あり」。~90 秒経っても 1 つも現れなければ「CI なし」と確定して各 skill の次ステップ（完了報告）へ進む。
2. **完了待ち** — CI ありなら `timeout 900 gh pr checks <PR URL> --watch --interval 30`（最大 15 分）で完走を待つ。exit 0 = 全 PASS → 次ステップへ。FAIL あり → §3 の分類で自動修正 → 再 push → 1 に戻る（**最大 3 サイクル**）。

```bash
# 起動待ち: check が現れるまで最大 ~90 秒。現れなければ「CI なし」で次ステップへ
for _ in $(seq 1 6); do
  gh pr checks <PR URL> 2>/dev/null | grep -q . && break
  sleep 15
done
gh pr checks <PR URL>   # 空 / `no checks reported` のままなら次ステップへ、あれば完了待ちへ
```

## 6. 対象リポジトリの特定・準備（plan-issue / implement-issue / fix-pr 共通）

Issue / PR の URL から `owner/repo` を特定したら、次の順でローカルを準備する（3 skill に
同じ手順をコピペしてドリフトさせない）。**worktree の探索・作成はここに含めない** —
fix-pr（PR ブランチの既存 worktree）と implement-issue（新規ブランチ）で意味が違うため、
各 SKILL.md 側に残す。

1. **カレント確認**: `pwd` + `git rev-parse --is-inside-work-tree 2>/dev/null && git remote -v`。
   カレントが対象リポジトリならそのまま使う。
2. **ローカル探索**: `ls ~/projects/<リポジトリ名> 2>/dev/null`。あればそれを使う。
3. **無ければ clone**: `gh repo clone <owner>/<repo> ~/projects/<リポジトリ名>`
4. **default branch を最新化**:
   ```bash
   cd <リポジトリパス>
   git fetch origin
   DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/origin/@@')
   git checkout $DEFAULT_BRANCH && git pull origin $DEFAULT_BRANCH
   ```

skill 固有の前段はそれぞれの SKILL.md 側に残す（implement-issue: Issue の repo が実装先とは
限らない判定 / fix-pr: `headRefName` の worktree 探索・作成 / plan-issue: 調査のみでブランチは切らない）。

## 7. ProjectV2 単一選択フィールドの更新（create-issue / implement-issue 共通）

Project board のフィールド更新（Status / Type 等の単一選択）はこの mutation が唯一の定義（各 SKILL.md はここを参照し、コピペで持ち帰らない）:

```sh
gh api graphql -f query='
  mutation($p:ID!,$i:ID!,$f:ID!,$o:String!){
    updateProjectV2ItemFieldValue(input:{projectId:$p,itemId:$i,fieldId:$f,value:{singleSelectOptionId:$o}}){ projectV2Item{ id } }
  }' -f p="<PROJECT_ID>" -f i="<ITEM_ID>" -f f="<FIELD_ID>" -f o="<OPT_ID>"
```

- **対象 Project が一意に決まらない場合**（issue が複数 Project にリンクされている等）: その issue を管理する Project（通常はリポジトリのロードマップ）を選ぶ。判断できなければ更新を skip し、報告に理由を添える（複数 board を意図せず書き換えない）。
- ID の取得方法は入口が違うため各 SKILL.md 側に置く（create-issue §3.5: project 番号既知 / implement-issue §1.5: issue URL から逆引き）。

## 8. Issue メタデータの完全性（create-issue / implement-issue 共通）

Issue のメタデータは「**作成時に埋める**（create-issue）・**着手時に補完する**（implement-issue）」の二段構えで完全に保つ。着手時ゲートがあるのは、Web/モバイルから手動作成された issue が skill を経由しないため。

**必須セット** — repo にその仕組みが実在する場合のみ対象（無いものは skip して報告に一言添える。体系を決め打ちせず `gh label list --limit 100` と `gh api repos/{owner}/{repo}/milestones` で実体系を読む）:

| 項目 | 内容 |
|---|---|
| 優先度ラベル | `P1/P2/P3` 等の優先度体系があれば 1 つ |
| 分野ラベル | `area: *` 等の prefix 体系があれば 1〜2 個 |
| Milestone | open な milestone があれば最も合う 1 つ |
| Project: Priority | 単一選択フィールドがあれば設定。**優先度ラベルと必ず同値**（1 回の判断で両方に書く。Status と違い変更頻度が低いため、作成時・着手時の同期で二重管理を許容する。**既存の両者が食い違っていたら Project フィールドを正としてラベル側を合わせる**） |
| Project: Type | 単一選択フィールドがあれば設定（分類基準は create-issue §3.5） |

**共通ルール:**

- **epic**（親 issue・子を束ねる container）は優先度・Type を空欄可（優先度は子で管理）。Status / Milestone / 分野ラベルは付ける。
- 分類の判断がつかない項目は**まとめて 1 問だけ**ユーザに聞く（項目ごとに聞かない）。ユーザ応答を待てない文脈では skip し、完了報告に未設定項目を列挙する。
- ユーザがラベル・milestone を明示指定した場合はそれを優先する（自動分類で上書きしない）。

## 9. Status の意味と「着手は Todo から」（weekly-plan / implement-issue / orchestrate / create-issue 共通）

Status は「いつやるか」の 1 軸で並べる。**優先度（P1/P2/P3）は"重要さ"、Status は"今週やるか"**で、別の軸として扱う（P1 でも今週の器に入らなければ Backlog に残す）。

| Status | 意味 | 誰が動かすか |
|---|---|---|
| `Backlog` | 起票済み。**今週やると決めていない** | create-issue（起票時の既定） |
| `Todo` | **今週着手すると人間が決めた分**。着手の唯一の入口 | weekly-plan（週初めの選定）・人間の手動 |
| `In Progress` | 着手済み〜merge 待ち | implement-issue §1.5 |
| `Waiting` | 外部の判断でブロック中（審査待ち・監修待ち等）。人間の merge 待ちは含めない | 人間・implement-issue（理由コメント必須） |
| `Done` / `Icebox` | 完了 / 見送り | merge の自動連鎖・人間 |

**Todo ゲート** — 着手系の skill は Backlog から直接 In Progress に上げない。Status が `Todo` 以外の issue に着手を指示されたら、**割り込みとして 1 回だけ確認してから**進める（拒否はしない — 急ぎの割り込みを塞ぐと運用が破綻するため）。ユーザ応答を待てない文脈（headless 実行等）では確認を省いて続行し、**完了報告に「Todo 外からの着手」と明記**する。

**この節が適用されない board**（下のいずれかなら Todo ゲートごと skip し、従来どおり In Progress に上げる）:

- Status に `Todo` 相当の選択肢が無い（`Todo` / `Ready` / `Selected for development` 等の表記ゆれは同一視する）
- issue が Project にリンクされていない・repo が Project 運用をしていない

**キューを 2 つ作らない** — 夜間自動着手のような「事前承認キュー」をラベルで持つ repo では、そのラベルと Status を **AND 条件**にする（ラベル単独では着手させない）。ラベルは「無人で回してよい」、Status は「今週やる」を表し、両方揃って初めて自動実行の対象になる。
