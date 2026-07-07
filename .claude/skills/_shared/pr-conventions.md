# PR / Issue 共通コンベンション (claude-forge)

`ship` / `create-pr` / `fix-pr` / `create-issue` / `plan-issue` / `implement-issue` が
共有する方針。**方針変更はこの 1 ファイルで行い**、各 SKILL.md はここを参照する
（同じ内容を 6 つの SKILL.md にコピペしてドリフトさせない、が狙い）。`_` 始まりなので
lint / install / 発火の対象外。

> **読み方**: 各 skill はこのファイルを `Read` で開いて従う。原本の絶対パスは
> `~/projects/claude-forge/.claude/skills/_shared/pr-conventions.md`
> （global symlink 運用でも cwd 非依存で読める）。別マシン等でこのファイルが
> 無いときは、各 SKILL.md 内に残した「fallback 要点」に従う。

## 1. 本文の簡潔さ（PR 本文・Issue 本文・計画コメント 共通）

レビュアー / 第三者が「diff や実作業を始める前に欲しい情報」だけに絞る。

**含めるもの:**
- 変更・タスクの意図（なぜ）が 1-3 行で伝わる Summary / 背景
- 何が変わるか / ゴールの簡潔な要約（diff で読み取れる詳細は書かない）
- 関連 Issue / PR / ドキュメントへのリンク

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

## 4. Codex レビュー応答ループ（`ship` / `create-pr` / `fix-pr` の Codex 応答ループ）

PR 作成 / push 後に Codex GitHub review が付けた指摘へ自律対応する有限ループ。
§3 が CI 失敗を共通化しているのと同じく、ここを唯一の定義とし、ship / create-pr / fix-pr が参照する。
**ループは PR の review 状態を変えない**（ready なら ready のまま・draft なら draft のまま）。**ready-for-review への昇格も merge も絶対にしない**（review / merge 判断は人間・Codex に委ねる claude-forge の役割分担を壊さない）。

### 手順（1 サイクル）

1. **取得（到着を待ってから）** — `@codex review` / automatic review は**非同期**。Step 6.5 / Phase 8.5 到達時点ではまだコメントが無いことがあるので、**最新 head コミットへの review summary か新規 inline コメントが現れるまで短く polling（30 秒間隔・最大 ~5 分）してから**取得する。timeout で何も現れなければ「今サイクルはレビューなし」としてループを抜ける（待たずに毎回 skip すると、CI が無い/速い PR でループが初回から空振りする）。

   ```bash
   # 到着待ち: 最新 head への Codex review summary が出るまで（最大 ~5 分）
   # 注意: 過去ラウンドの古い review も "Reviewed commit" を含むので、必ず現行 head sha で判定する
   #   （でないと既存 review がある PR / 2 周目で即 break し、今回依頼分の到着前に進んで空振りする）。
   head=$(git rev-parse --short HEAD)
   for _ in $(seq 1 10); do
     gh pr view <PR URL> --json reviews \
       --jq '.reviews[]|select(.author.login|test("codex";"i"))|.body' | grep -q "$head" && break
     sleep 30
   done
   # レビュー要約（review body）
   gh pr view <PR URL> --json reviews \
     --jq '.reviews[] | select(.author.login|test("codex";"i")) | .body'
   # inline review comments（行コメント。Codex の主要な指摘はここに付く・review 要約とは別 endpoint）
   # 注意: gh api が自動展開する placeholder は {owner}/{repo}/{branch} のみ。{number} は展開されない
   #   ので PR 番号は実値に解決してから渡す（そのままだと 404 で行コメントを取りこぼす）。
   PR=$(gh pr view <PR URL> --json number -q .number)
   gh api "repos/{owner}/{repo}/pulls/$PR/comments" \
     --jq '.[] | select(.user.login|test("codex";"i")) | "\(.path):\(.line // .original_line)\n\(.body)"'
   ```

   > **新規判定（収束の要）**: 対象は**最新 push したコミットへの review だけ**。Codex は review ごとに「Reviewed commit: `<sha>`」入りの summary を 1 つ出す。GitHub は前ラウンドの outdated 行コメントの `commit_id` を最新コミットへ張り替えるので、**`commit_id` だけで「新しい指摘」と判断しない**。summary の `Reviewed commit` が現行 head sha か、各コメントの `created_at` が今サイクルの `@codex review` 再依頼より後か、で新規だけを拾う。これを怠ると**対応済みの指摘を再処理して永遠に収束しない**。

2. **評価＋分類** — 各指摘がまず妥当かを評価し（記憶でなく diff と安全契約に照らす）、次の 2 種に分ける。

   | 種別 | 対応 |
   |------|------|
   | 自動修正可（lint / typo / 明白なバグ / 安全契約との不整合） | working tree を修正する |
   | 要人間判断（設計・仕様・トレードオフ） | 自動で触らない。要約してユーザーに引き継ぐ |

   同意できない指摘は **dispute** として PR にコメントで根拠を述べ、コードは直さない（黙って無視しない）。inline 行コメントを拾い損ねると主要指摘を 0 件扱いして早期終了するので、必ず `pulls/.../comments` も取得する。

3. **修正** — 自動修正可と判断したものだけ working tree を修正する。
4. **commit + push + CI 再確認** — 変更ファイルのみ `git add` し、コミット・push（Co-Authored-By は付けない・force push しない）。**push 後は最新 head の CI を待つ**（`gh pr checks <PR URL> --watch` 等）。Codex 修正が lint/test を壊していれば §3 の CI ループで直してから次へ。完了報告の CI 結果は**この最新 head のもの**にする（修正前の古い PASS を流用しない）。
5. **再依頼** — `@codex review` を再度コメントして次サイクルの review を依頼する。

   ```bash
   gh pr comment <PR URL> --body "@codex review"
   ```

### 収束 / 停止条件

次のいずれかで停止する（最大 3・CI ループと同数）。

- 新規の **critical / blocking が 0**（自動修正可の指摘が出なくなった）
- **最大 3 サイクル**到達
- 残りが **要人間判断のみ**

停止時、残った要人間判断の指摘は **要約してユーザーに引き継ぐ**（自動で触らない）。

### 禁止事項（§3 の CI ループ条項と同じ精神の安全ゲート）

- 指摘を黙らせるためのテスト書き換え・握りつぶしをしない（仕様 / 実装のどちらが正しいかを判断する）。
- **ループは PR の review 状態を変えない（ready なら ready・draft なら draft）・ready-for-review 昇格も merge も絶対にしない**。
- force push しない。`--force` / `--force-with-lease` はユーザの明示確認がある時だけ。
- 同意できない指摘を黙って無視しない（dispute としてコメントする）。

## 5. CI 起動待ち・検出（`ship` / `create-pr` / `fix-pr` の CI 自動修正ループの入口）

§3 が「CI が失敗したらどう直すか」を定義するのに対し、ここは「そもそも CI が有るか・起動したか」の判定を唯一化する（§4 の Codex ループと同じく、各 SKILL.md にコピペしてドリフトさせない）。

push 直後は CI run がまだ登録されていないことがある。**15 秒 1 回の `no checks reported` を「CI なし」と確定してはいけない** — 後から起動する CI を取りこぼし、§3 の自動修正ループごと空振りする。次の順で判定する:

1. **起動待ち** — `gh pr checks <PR URL>` を **15 秒間隔で最大 ~90 秒**見て、check が 1 つでも現れたら「CI あり」。~90 秒経っても 1 つも現れなければ「CI なし」と確定して §4（Codex 応答ループ）へ進む。
2. **完了待ち** — CI ありなら `timeout 900 gh pr checks <PR URL> --watch --interval 30`（最大 15 分）で完走を待つ。exit 0 = 全 PASS → §4 へ。FAIL あり → §3 の分類で自動修正 → 再 push → 1 に戻る（**最大 3 サイクル**・Codex ループと同数）。

```bash
# 起動待ち: check が現れるまで最大 ~90 秒。現れなければ「CI なし」で §4 へ
for _ in $(seq 1 6); do
  gh pr checks <PR URL> 2>/dev/null | grep -q . && break
  sleep 15
done
gh pr checks <PR URL>   # 空 / `no checks reported` のままなら §4 へ、あれば完了待ちへ
```
