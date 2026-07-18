---
name: ship
description: 現在の作業を GitHub Pull Request にまで持っていく。必要ならフィーチャーブランチを切り、差分からコミットメッセージと PR タイトル/本文を生成し、push して `gh pr create` で PR を開く。ユーザーが「ship して」「PR出して」「PR作って」「送って」「プルリク」「ship it」「open a PR」「make a PR」「let's ship this」など、現在の変更を PR にしたい意図を示したときに発動する。push 直前に「Codex レビュー（`/codex:review`）をかけてから push するか」を 1 回だけ確認し（YES ならユーザーのコマンド実行を待つ）、PR 作成後は CI の収束ループ（merge はしない）まで自動で回す。自動・非対話で止まらず完走してほしいなら [[create-pr]]、既存 PR を直すなら [[fix-pr]] を使う（ship は自分で確認しながら新規 PR を出す対話フロー）。単にコミット / push だけで PR にしないなら発動しない。
allowed-tools: Read, Edit, Write, Glob, Grep, Skill, Agent, Bash(grep:*), Bash(git status:*), Bash(git remote:*), Bash(git ls-remote:*), Bash(git log:*), Bash(git branch:*), Bash(git diff:*), Bash(git rev-parse:*), Bash(git checkout:*), Bash(git add:*), Bash(git reset:*), Bash(git restore:*), Bash(git commit:*), Bash(git push:*), Bash(gh auth status:*), Bash(gh repo view:*), Bash(gh repo create:*), Bash(gh pr view:*), Bash(gh pr create:*), Bash(gh pr checks:*), Bash(gh run list:*), Bash(gh run view:*), Bash(sleep:*), Bash(timeout:*), Bash(prettier:*), Bash(npx prettier:*), Bash(eslint:*), Bash(npx eslint:*), Bash(ruff:*), Bash(golangci-lint:*), Bash(terraform fmt:*), Bash(terraform validate:*)
---

# ship

「変更を PR まで持っていく」end-to-end ワークフロー。各ステップに STOP 条件あり。違反したら自動回復せず必ずユーザーに見せる。

> **PR 系 skill の使い分け:** この `ship` は新規 PR を**対話的に**（commit/PR を自分で確認しながら）出す skill。push 直前に **Codex ローカルレビューの要否を 1 回確認**（§3.8・`_shared/pr-conventions.md` §4）し、PR 作成後は **CI の収束ループ**（§5.5・`_shared` §3/§5 共有・merge はしない）まで自動で回す。同じ流れを**非対話・委譲で**頭から回すなら [`create-pr`](../create-pr/SKILL.md)（implement-issue 等からの自動エンジン）、**既存 PR**（PR URL）を直すなら [`fix-pr`](../fix-pr/SKILL.md)。

## 🚫 絶対に守るルール

[`_shared/pr-conventions.md`](../_shared/pr-conventions.md) **§0 が唯一の定義**（main 直 push 禁止 / merge・ready 昇格しない / force push しない / `git add -A` 禁止 / Co-Authored-By なし / 日本語 commit・PR / secret を commit しない）。`git push origin main` / `git push origin master` を実行しそうになったら **必ず STOP** してユーザーに確認する（hard guard — `_shared` が無い環境でも括弧内の要点に従う）。

## 0. Preflight (全項目 pass 必須 — 1 つでも失敗したら STOP)

並列で実行:
- `gh auth status` — ログイン必須。未ログインなら `gh auth login` を案内して STOP。
- `git rev-parse --is-inside-work-tree` — true でなければ STOP。
- `git remote -v` — `origin` が github.com を指している必要あり。無ければユーザーに「`gh repo create` する？それとも中止？」と確認。
- `git ls-remote --heads origin` — **出力が空 = リモートにブランチが1本も無い新規 repo**。この場合 PR のベースが存在しないので **ブートストラップが必要**（§1 参照）。`gh repo view --json defaultBranchRef` も空を返すため、後続の default 判定が誤作動する点に注意。
- `git status --porcelain` または `git log @{u}..HEAD 2>/dev/null` — 未コミット変更 OR 未 push コミットのどちらかが存在しなければ「ship するものが無い」と伝えて STOP。
- **巨大 import の検知**: 最後のコミット以降の変更が大きい（多数ファイル）場合、PR が「今回の主目的」だけでなく**過去の未コミット作業を全部含む**ことをユーザーに事前に伝え、スコープを確認する。

## 1. Branch (hard guard)

```sh
current=$(git branch --show-current)
default=$(gh repo view --json defaultBranchRef -q .defaultBranchRef.name)
```

- **`current` が `default` と一致する場合** (= main や master にいる):
  - **絶対にこのブランチで commit/push してはいけない。**
  - `git diff` を見て kebab-case のブランチ名を 3〜6 語で生成。明らかな type prefix があれば付ける: `feat/`, `fix/`, `docs/`, `chore/`, `refactor/`。
  - `git checkout -b <name>` で新ブランチを切る。
- **それ以外**: 現在のブランチをそのまま使う。
- **既存ブランチを rename しない。**

- **`default` が空（= 新規 repo でリモートにブランチが無い）の場合**: PR のベースが存在しないので **ブートストラップ**する。
  1. 確定履歴（未コミット作業を含まない現在の HEAD）を base ブランチ（通常 `main`）として push する必要がある。**これは default branch への push なので必ずユーザーに明示確認**。さらに auto-mode / 権限分類器が `git push origin main` をブロックすることがある → その場合は**ユーザー自身に実行してもらう**（`! git push -u origin main`）。
  2. base が出来たら以降は通常フロー（フィーチャーブランチ → commit → push → PR）。
  - 名前が `main`/`master` のブランチに居る場合は、`default` が空でも **default 扱い**（このブランチで直接 commit/push しない）。

この後どのステップでも、push 先が default branch でないことを `git rev-parse --abbrev-ref HEAD` で再確認すること。

## 2. Stage

- `git status --porcelain` で変更内容を確認。
- 関連ファイルのみ **明示的なパス指定で** stage する。`git add -A` / `git add .` は **絶対禁止** (`.DS_Store`、ログ、IDE 設定ファイルなどを巻き込む)。
- 未 stage のリストに次のいずれかが見えたら **STOP してユーザーに確認**: `.env*`, `*.pem`, `*.key`, `credentials*`, `id_rsa*`, その他 token / secret らしきもの。
- **内容（値）スキャンも必須**（特に初回 push / 巨大 import 時）: stage 済み diff に実シークレット値が無いか確認する。`git diff --cached | grep -nIE 'GOCSPX-|sk-ant-|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|eyJ[A-Za-z0-9_-]{10,}\.|xox[baprs]-|sb_secret_'` 等の高シグナルパターンを検出。1 つでも当たれば **STOP してユーザーに確認**。ファイル名が無害でも、docs / config / サンプルに値が貼られていることがある。
- 無関係な変更が混在していたら、推測せずどれを含めるかユーザーに聞く。

## 3. Commit (未 push コミットのみで ship する場合はスキップ)

**staged diff から** メッセージを生成:
- **Subject**: **日本語**で簡潔に (50 字程度・体言止め or 「〜する」。例:「死参照を修正」「PR 規約を共有ドキュメントに集約」)。**英語にしない** (claude-forge 方針)。末尾の句点無し。
- **Body**: 任意。差分から自明でない *why* を**日本語**で 1〜3 文。trivial な変更ならスキップ。
- **ユーザーに見せて編集機会を与えるかは変更の性質で決める** (日本語 subject 等の規約は決定的なので毎回は聞かない):
  - **trivial / 単一ファイル / 自明な変更** (typo 修正・1 ファイルの小修正・意図が diff から自明) → メッセージを生成してそのまま commit (自走)。
  - **非自明・複数論点が混ざる commit** (複数ファイルにまたがる・狙いが diff から読み取りにくい・要約に複数の話題が同居する) → commit 前にメッセージを見せて編集機会を与える。
- HEREDOC で commit (フォーマット保持):
  ```sh
  git commit -m "$(cat <<'EOF'
  <subject>

  <body if any>
  EOF
  )"
  ```
- pre-commit hook が失敗したら: 根本原因を fix → 再 stage → **新しい commit** を作成。`--amend` や `--no-verify` は使わない。

## 3.5 セルフレビュー (push/PR の前に自分で diff を批判的に読み直す)

push は **外向きの publish**。その前に、これから出す diff を自分で読み直して粗を取る。**ここは安全領域なので完全自律でよい** (ユーザーに確認を挟まず自走する)。`_shared/pr-conventions.md §2` を流用し、**diff レベル**を確認する (PR 本文の点検はまだ本文が無いので **§5 の `gh pr create` 直前**で行う):

- **(a) secret 再確認**: `git diff <base>...HEAD` に実シークレット値が残っていないか (§2 の検出パターンを再走させてよい)。当たれば §2 の secret ルールに従い **STOP してユーザーに確認** (これは自走しない)。
- **(b) 無関係な変更の混入**: 今回の主目的と無関係な diff (別件の修正・デバッグ用の一時変更・整形だけの広域差分) が混ざっていないか。

**有限の自己検証ループ (最大 2 パス)**: (b) の混入が見つかったら直す。ただし §3.5 は **commit 後**なので `unstage` では HEAD から消えない — `git reset --soft HEAD~1` で直前 commit を解き、unrelated file を `git restore --staged` で外して、本来の変更だけで commit し直す (`--amend` は使わない)。**commit し直す時はメッセージも除外後の diff から生成し直す** (元のメッセージは混入分を含んだ要約なので流用しない)。**混入が消えるまで最大 2 パス自走**し、2 パスで収束しなければ残りの懸念を §6 報告に添える。(a) の secret hit だけは自走せず即 STOP。理想的には混入は §2 staging 時点で弾く。

> Codex レビューの要否確認は §3.8 が唯一のゲート。上の (a)(b) セルフレビューは従来どおり Claude が自走する（§3.8 の Codex ゲートはその置き換えではなく追加レイヤ）。

## 3.6 skill 変更なら skill-reviewer を必ず1回通す（実質変更なら skill-empirical-tester も・SKILL.md を触った時だけ）

**発火条件を厳密に判定する。** branch の diff が `.claude/skills/<name>/SKILL.md` を**追加/変更**していて、かつ `skill-reviewer` agent が使える時**のみ**このゲートに入る。それ以外（SKILL.md を触っていない・`_template` だけ・agent が無い repo）は**丸ごとスキップ**する。判定:

```sh
git diff <base>...HEAD --name-only | grep -E '\.claude/skills/[^_/][^/]*/SKILL\.md$'
```

- 1 行でもヒット → 変更した SKILL.md ごとに `skill-reviewer` agent（Agent tool）を回す。決定的 lint（Stop hook / CI）が見られない**発火設計・断定の書き方・順序つき手順・重複/粒度・方針整合**を見るのがこの agent の役割で、lint とは別レイヤ。
  - さらに**新規 skill の追加、または手順・成果物の挙動に関わる実質変更**のときは、静的な skill-reviewer に加えて `skill-empirical-tester` agent（Agent tool）も 1 回通す。代表タスクに当てて**発火後の成果物の質を実測**し、失敗パターンを SKILL.md へ還元するのがこの agent の役割（skill-reviewer が静的な作法、empirical-tester が実測、と別レイヤ）。**description だけの微修正・文言調整では回さない**（空振りコストを避ける）。この agent が repo に無ければスキップ。
- ヒット無し → スキップして §3.65 へ。
- `skill-reviewer` agent がこの repo に無い（skill だけ別 repo にコピーした等） → スキップして §3.65 へ。

**指摘の扱い**（ここは §3.5 と同じ安全領域なので基本は自走）:
- **確信度が高く明確な craft の欠陥**（name↔dir 以外の発火設計ミス・曖昧な禁止表現・重複記述）→ その場で SKILL.md を直し、直した分は再 stage して commit をやり直す（§3.5 の `git reset --soft HEAD~1` 手順に従う・`--amend` は使わない）。
- **設計判断が割れる指摘**（description の踏み込み具合・スコープの線引きなど、正解が一意でないもの）→ **自走で決めず STOP してユーザーに見せる**。
- 直しても直さなくてもよい軽微な提案 → §6 報告に列挙する。

> lint の指摘（E1–E6/W1–W3）はこのゲートの対象外。それは Stop hook / CI が別途担保する。ここは「lint が見られない判断レイヤ」だけを見る。

## 3.65 名鑑ゲート（skill / agent を新規追加・改名・削除した時だけ）

`/company`（社員名鑑 `company.ts`）と `/flows`（運行図 `flows.ts`）は**手書きの静的データ**で自動更新されない（`/toolkit` だけが inventory-uploader で自動）。反映漏れは dashboard の deploy を止める。**書き足したかを記憶に預けない**ため、push 前に機械で検算する。発火条件:

```sh
git diff <base>...HEAD --name-status | grep -E '^(A|D|R)' | grep -E '(plugins/[^/]+/(skills|agents)/|\.claude/(skills|agents)/)'
```

- ヒット無し（既存 skill の中身を直しただけ・skill を触っていない）→ スキップして §3.7 へ。
- dashboard repo（`~/projects/claude-forge-dashboard`）が無い → スキップして §3.7 へ。
- 1 行でもヒット → **2 本とも走らせる**（片方だけでは漏れる）:

  ```sh
  python3 ~/projects/claude-forge-dashboard/ops/roster_check.py   # 名鑑 ↔ ~/.claude の在庫
  python3 ~/projects/claude-forge-dashboard/ops/flows_check.py    # 名鑑 ↔ /flows のパネル
  ```

**扱い**（ここは正解が一意なので**自走してよい**。§3.6 のような判断の分岐は無い）:

- **どちらかが非ゼロ終了** → 未反映。`company.ts`（社員 1 人分）と `flows.ts`（`no` を揃えた運行図パネル 1 枚）を書き足し、**両方 OK になるまで**再実行してから push する。直した分は §3.5 の `git reset --soft HEAD~1` 手順で commit をやり直す（`--amend` は使わない）。
- **反映先の枠**: グローバルな skill / agent は `DEPARTMENTS`。プロジェクト repo の `.claude/skills` に置く project skill は `RESIDENT`（客先常駐）枠で、**`kind:` キーを持たせない**（`roster_check.py` は `~/.claude` 配下しか照合しないので、DEPARTMENTS に入れると drift 判定で deploy が止まる）。
- **dashboard を別セッションが編集中のことがある**。checks が落ちた原因が自分の差分でないなら、勝手に直さず §6 報告に回す。

> **`roster_check.py` だけでは足りない。** 2026-07-18 に weekly-plan を追加した際、`company.ts` は更新したが `flows.ts` のパネルが漏れた。roster_check は `flows.ts` を見ないので通ってしまい、片方だけでは気づけない。過去には banso が名鑑から数週間欠落した実例もある。

## 3.7 leak-auditor ゲート (漏洩リスクのある diff だけ・区切りで 1 回)

§2/§3.5 の grep は「値の形が既知の secret」しか拾えない。**絶対パス・第三者の個人情報・非公開 URL・生成物の混入**は形が無く grep では見えないので、該当しやすい diff のときだけ `leak-auditor` agent（Agent tool）を 1 回通す。発火条件を厳密に判定する:

```sh
git diff <base>...HEAD --name-only --diff-filter=A   # (1) 新規追加ファイル
git diff <base>...HEAD --name-only                   # (2) 対象パスの変更
```

- 次の**いずれか**に該当 → leak-auditor を 1 回回す（ship の区切りで 1 回・commit のたびではない）:
  1. 新規追加ファイルがある（初出のファイルは混入リスクが最も高い）
  2. 変更に設定・ドキュメント類が含まれる: `*.json` / `*.toml` / `*.yaml` / `*.yml` / `*.md` / `.claude/**` / `.env*` 類
  3. §2/§3.5 のスキャンで「secret ではなさそうだが判断に迷った」ものが残っている
- どれにも該当しない（既存コードファイルのみの小さな diff）→ スキップして §3.8 へ。
- `leak-auditor` agent が無い repo（skill だけコピーした等）→ スキップして §3.8 へ。

**検出の扱い**（§3.6 と同じ二分法）:
- **secret / 個人情報 / 非公開 URL の検出** → 自走せず **STOP してユーザーに見せる**（マスク付きで）。
- **絶対パス・生成物・`*.local.*` など機械的に直せるもの** → その場で直し、§3.5 の `git reset --soft HEAD~1` 手順で commit をやり直す（`--amend` は使わない）。
- 誤検知と判断したもの → 理由を §6 報告に 1 行残す（黙って捨てない）。

## 3.8 Codex 事前レビュー確認（push 直前・1 回だけ）

push の直前に「**Codex レビュー（codex プラグインの `/codex:review`）をかけてから push する?**」を**ユーザーに 1 回だけ**確認する（`_shared/pr-conventions.md` §4 が唯一の定義）。

- **YES** → ship はここで**一時停止**し、ユーザー自身に `/codex:review`（設計判断・仮定まで突かせたいなら `/codex:adversarial-review`）の実行を案内する（両コマンドは `disable-model-invocation` のユーザー起動専用 — Claude は `codex` CLI を直接叩いて代行しない）。レビュー結果を読み、妥当と判断した指摘を直した場合は §3.5 の `git reset --soft HEAD~1` 手順で commit を作り直してから §4 へ（どの指摘を直すかはユーザーに確認する — プラグイン側も自動修正を禁止している）。狙いは「PR の初版を Codex-clean にする」前倒し。
- **NO** → そのまま §4 へ。
- **聞かなくてよいケース**: ① ユーザーが事前に「codex は不要」「そのまま出して」と明示済み → NO 扱いで §4 へ ② ユーザーが事前に「Codex にも先に見せて」「ship 前に codex レビュー」等と明示済み → YES 扱いで即 `/codex:review` を案内 ③ この ship の区切りで既に `/codex:review` / `/codex:adversarial-review` を実行済み → 二重で聞かない・§4 へ。
- **commit のたびには聞かない。** 確認は ship 1 回の区切りで 1 回だけ（§3.6/§3.7 の agent ゲートと同じ粒度）。
- **PR 作成後に Codex GitHub review / `@codex review` は使わない**（2026-07 方針転換: トークン消費とレビュー到着待ちの削減。レビューは push 前のこのゲートに一本化）。

## 4. Push (default branch への push は absolute STOP)

```sh
# push する前に必ずチェック
branch=$(git rev-parse --abbrev-ref HEAD)
default=$(gh repo view --json defaultBranchRef -q .defaultBranchRef.name)
if [ "$branch" = "$default" ]; then
  echo "ERROR: default branch ($default) への push は禁止"; exit 1
fi
```

- 新ブランチ: `git push -u origin HEAD`
- 既存ブランチ (upstream あり): `git push`
- non-fast-forward で reject された場合: **STOP**。`--force` / `--force-with-lease` はユーザーの明示確認なしに使わない。

## 5. PR

- base branch 解決: `gh repo view --json defaultBranchRef -q .defaultBranchRef.name`
- このブランチの **全コミット** からコンテキストを集める:
  - `git log <base>..HEAD --pretty=format:'%s%n%n%b'`
  - `git diff <base>...HEAD --stat`
- **Title**: **日本語**で 70 文字以内 (英語にしない)。最新/主要 commit subject に揃えることが多い。複数 commit なら umbrella な要約を。
- **Body** はこの構造:
  ```
  ## Summary
  - <1〜3 個の bullet。何が変わって何のため>

  ## Test plan
  - [ ] <検証方法>
  ```
- **Assignee**: `--assignee @me` でユーザー自身を assignee に設定する (PR の所有者が UI で明確になる)。
- **本文セルフレビュー (create 直前・自走・最大 2 パス)**: 本文ドラフトを `gh pr create` する前に読み直す — **(c)** 本文が diff の逐一解説や `§1`「原則含めないもの」になっていないか、**(d)** Summary が「何が変わって何のため」を 1〜3 行で語れているか (diff を読まないと分からない説明になっていないか)。粗があれば本文を推敲して直す (収束まで最大 2 パス)。§3.5 から移したのは、本文が存在するのが create 直前だから。
- HEREDOC で create:
  ```sh
  gh pr create --base <base> --assignee @me --title "<title>" --body "$(cat <<'EOF'
  ## Summary
  - ...

  ## Test plan
  - [ ] ...
  EOF
  )"
  ```
- このブランチに既に PR がある (`gh pr view` で取得できる) なら **重複作成しない**。URL を見せて title/body を更新するか確認。
- **PR 作成後に `@codex review` をコメントしない・automatic review の有無確認もしない**（`_shared/pr-conventions.md` §4。レビューは §3.8 の push 前ゲートに一本化済み）。

## 5.5 収束ループ（PR 作成後・自動・CI 最大 3 サイクル）

PR を作ったら**そのまま収束ループに入る**（ユーザー確認は挟まない）。入る前に一声 —「収束ループに入る（CI 待ち→自動修正・最大 3 周・**merge も force push もしない**）。不要なら止めて」— と告げてから走る。**ここは安全領域（PR の状態を変えず・非破壊）なので自走でよい。**

ship が作る PR は ready（非 draft）。収束ループは **PR を merge しない・ready/draft 状態を変えない・force push しない**。これだけ守れば create-pr / fix-pr と同じループをそのまま使える。

**CI 自動修正ループ（最大 3 サイクル）** — 起動待ち・検出は [`_shared/pr-conventions.md`](../_shared/pr-conventions.md) §5、修正分類は §3 が唯一の定義（create-pr / fix-pr と同一）。
- 起動待ち（§5 要点）: push 直後は run 未登録のことがある。`gh pr checks <PR URL>` を 15 秒間隔で数回（~90 秒）見て、check が 1 つも現れなければ「CI なし」と判断して §6 へ。**15 秒 1 回の `no checks reported` を確定にしない**（後から起動する CI を取りこぼす）。
- 完了待ち: `gh pr checks <PR URL> --watch --interval 30`（全 check 完了で返る）。時間上限を付けるなら `timeout` / macOS は `gtimeout` でラップ（どちらも無ければ素の `--watch`）。FAIL なら `gh run list` → `gh run view <run-id> --log-failed` で失敗ログのファイル・行を取得し、§3 に従って根本修正（推測修正しない）→再 push。最大 3 サイクル。

## 6. 報告

- PR URL を **1 行で** 出力 (ターミナルで clickable になるように)。
- **§3.8 の Codex 事前レビュー**を実施したか（実施 / ユーザーが不要と回答 / 明示済みでスキップ）と、実施した場合の要点（直した指摘の件数と要旨・見送った指摘とその理由）を明記する。
- **収束ループの結果**を報告: CI の最終 PASS/FAIL（**最新 head の結果**・古い PASS を流用しない）・自動修正して push した内容。CI が無い repo なら「収束ループはスキップ」と明記する。
- Review コメントは **参考情報**。claude-forge では Branch Protection 無しの運用なので、ユーザーが内容を見て自分で merge ボタンを押す (他リポジトリで Branch Protection を有効化している場合は、その条件に従って判断)。
- **自動 merge / ready 昇格はしない**（収束ループでの修正 push は §5.5 の範囲内・force push はしない）。**merge は必ずユーザーが手動で行う方針**。ここで終了。

## やってはいけないこと

- 共通の禁止事項（force push / `gh pr merge` / `git add -A` / main 直 push / secret commit）は [`_shared/pr-conventions.md`](../_shared/pr-conventions.md) §0 が唯一の定義。
- 失敗した hook を `--amend` で「修正」する。新 commit を作る。
- `--no-verify` / `--no-gpg-sign` で hook / 署名をスキップ (ユーザー明示要求がない限り)。
