---
name: codex-review
description: OpenAI Codex CLI を使って、現在の git 差分にセカンドオピニオンのコードレビューをかける。ユーザーが「codex にレビューしてもらって」「セカンドオピニオン」「他のモデルにも見せて」「ship する前にチェックして」「codex review」「second opinion」など、別モデルによる独立レビューを求める意図を示したときに発動する。「codex に adversarial レビュー」「codex で厳しめに穴を探して」「セカンドオピニオンを批判的に」など、**別モデルによる独立レビューの意図と併せて**設計判断・セキュリティ・エッジケースを敵対的に突くことを求めたときは adversarial モードで実行する。PR を出す前や、大きめの refactor 後に特に有効。単に「これレビューして」「厳しめに見て」「批判的にレビュー」だけ（Codex を明示しない）なら通常の Claude レビューで対応し、この skill は発動しない。
allowed-tools: Read, Edit, Write, Bash(which:*), Bash(codex review:*), Bash(git rev-parse:*), Bash(git status:*), Bash(gh repo view:*)
---

# codex-review

現在の git 差分を OpenAI Codex CLI に渡して独立レビューを取る。Codex は別の学習を持つ別エージェントなので、価値は **「意見の食い違いシグナル」** にある。Claude による合成・要約ではない。

**段階性 + 有限自律**で動く。**Phase 1 Review**（codex 実行 → verbatim 表示）→ **Phase 2 Triage**（指摘を accept / dispute / defer に分類）までが既定。ユーザーが修正を望んだときだけ **Phase 3 Address**（accept 分のみドラフト修正 → 再レビュー・最大 2 周）に入る。**既定は review-only**：この skill は commit / push / PR をしない。指摘の自動適用もしない。

## モード

ユーザーの言い回しから 2 モードを選ぶ。Preflight・対象判定・報告は共通で、`codex review` に渡すプロンプトだけが違う。

- **通常レビュー** (既定) — バグ・リグレッション・明らかな問題を拾う。「codex にレビュー」「セカンドオピニオン」など。
- **adversarial レビュー** — **この skill が既に選ばれている前提**（= 別モデルによる独立レビューを求められている文脈）で、「欠陥が必ずある」前提に立ち設計判断・セキュリティ・エッジケースを敵対的に突く。「codex に adversarial で」「codex で厳しめに穴を探して」「セカンドオピニオンを批判的に」など。OpenAI 公式プラグイン `codex-plugin-cc` の `/codex:adversarial-review` 相当を、プラグインを入れずに `codex review` のプロンプト指定で再現する。

Codex を明示しない単なる「厳しめにレビュー」「批判的に見て」はそもそもこの skill を発動させない（素の Claude レビューに任せる）。adversarial か迷う弱い言い回しのときは通常モードで実行し、報告の coda で「adversarial で再実行する?」と一声添える。

## Phase 1 — Review（codex 実行 → verbatim 表示）

現状どおり `codex review` を実行し、出力を**そのまま**見せるフェーズ。Preflight・実行・報告をここに保持する。

### Preflight

- `which codex` が成功すること。失敗したら `npm i -g @openai/codex` を案内して STOP。
- `git rev-parse --is-inside-work-tree` が true。
- レビュー対象が存在すること:
  - `git status --porcelain` に変更あり → `codex review --uncommitted`
  - feature branch にいる場合 → `gh repo view --json defaultBranchRef -q .defaultBranchRef.name` で default branch を取り、`codex review --base <default>` (フォールバック: `main` → `master`)
  - どちらも無ければ「レビュー対象が無い」と伝えて STOP

### 実行

stderr もキャプチャして実行:
```sh
codex review --uncommitted 2>&1
# または
codex review --base main 2>&1
```

ユーザーが観点を指定している場合 (例:「認証周りに注意して」) はプロンプトとして渡す。

> **重要 (codex 0.137.0 で検証)**: scope フラグ (`--uncommitted` / `--base` / `--commit`) と PROMPT は**併用できない** (`error: the argument '--uncommitted' cannot be used with '[PROMPT]'` で即エラー)。プロンプトを渡すときは scope フラグを付けず `codex review "プロンプト"` とする。この場合 codex は working tree (staged + unstaged + untracked) を既定の対象にする。

```sh
codex review "認証周りのリグレッションに注意して" 2>&1
```

> feature branch で base 差分にプロンプトを効かせる手段はこの版には無い。base 比較が要るなら**プロンプト無し**の `codex review --base <default>`、観点を効かせたいなら working tree 対象の `codex review "プロンプト"` のどちらかを選ぶ。

**adversarial モード**では、敵対的な観点を明示したプロンプトを (scope フラグ無しで) 渡す:
```sh
codex review "この差分を批判的にレビューせよ。欠陥が必ずあるという前提で、最も痛い失敗モードを探すこと。観点: (1) 設計判断の妥当性とトレードオフの検討漏れ (2) セキュリティ — 認証・認可・データ損失・レースコンディション・入力検証 (3) エッジケース・境界値・エラーパスの考慮漏れ (4) 既存挙動を壊す後方互換性リスク。表面的な lint 指摘より設計・前提の穴を優先せよ。" 2>&1
```
ユーザーが追加の観点を指定していれば、上記プロンプトの末尾に足す。

タイムアウトは長めに (5 分以上)。大きな差分だと時間がかかる (adversarial は通常より長くなりやすい)。

### 報告（verbatim）

- **Codex の出力をそのまま (verbatim) 見せる。** 要約・言い換え・「改善」はしない。Claude との意見の食い違いを含めて、ユーザーは Codex が実際に何と言ったかを見たい。
- verbatim ブロックの後に短い coda (最大 2〜4 行):
  - Codex が severity をタグ付けしていればその集計 (例: "high 3 / med 5 / low 2")
  - 最初に見るべき指摘を強調
- Codex の提案を自動適用しない。何に対応するかはユーザーが決める。
- verbatim を見せたら **Phase 2 Triage** に進む。

## Phase 2 — Triage（accept / dispute / defer に分類）

Phase 1 の verbatim を壊さずに、その**後ろで** Codex の各指摘を構造化する。これが従来 coda にあった「同意しない指摘」を表に展開したもの。各指摘を 1 行ずつ次の 3 区分に分類して提示する:

| 区分 | 意味 |
|---|---|
| **accept** | 同意。直すべき指摘。 |
| **dispute** | 不同意。`file:line` と**理由**を必ず添える（なぜ誤検出 / 的外れか）。 |
| **defer** | 保留。今は直さない（スコープ外・別 PR・要相談 等）。 |

- 表の列は **指摘 / severity / 区分 / 一言コメント**。Codex が severity を付けていなければ Claude が見立てを置く。
- これは Claude の判断であり Phase 1 の verbatim を上書きしない。「Codex が言ったこと」と「Claude の分類」は別物として並べる。
- 既定はここで止める。最後に **「accept 分を直す?（Phase 3 に入る）」と一声**添えて、ユーザーの GO を待つ。明示の修正意図が無ければ Phase 3 に入らない。

## Phase 3 — Address（任意・accept 分のドラフト修正と再レビュー）

**ユーザーが修正を望んだときだけ**入る。Phase 2 の **accept 分のみ** working tree にドラフト修正を当て、`codex review` を更新後の diff に再実行して収束を確認する。dispute / defer には手を付けない。

ループ（最大 2 周）:

1. accept の指摘を working tree に修正する（commit はしない・working tree のみ）。
2. 更新後の diff に `codex review` を再実行する（Phase 1 と同じ実行形。verbatim で見せる）。
3. 再レビュー結果を Phase 2 と同じく分類し直す。
4. **収束/停止判定**（下記）に当たれば停止。当たらなければもう 1 周（**最大 2 周まで**）。

### 収束 / 停止基準（いずれかで停止）

- **新規の high severity な accept 指摘が 0**（accept 扱いの high が再レビューで消えた）。
- **2 周に到達**した。
- 残りが **dispute / defer のみ**（accept がもう無い）。

停止時、まだ残っている指摘は **「未解決」として列挙**する（severity と区分つき）。握りつぶさない。

### Phase 3 の安全ゲート（維持）

- **commit / push / PR は人間 GO。この skill は commit しない。** working tree にドラフトを置くだけ。出した先は [[ship]] / `create-pr` で人間が判断する。
- `codex apply` / `codex exec` はスコープ外のまま使わない。
- **指摘を黙らせるためのテスト書き換え・握りつぶしは禁止。** 失敗を隠す修正はしない。直せないものは「未解決」に回す。

## エラー時

- 認証エラー (`Not logged in`): `codex login` を案内して STOP
- ネットワーク / タイムアウト: エラーをそのまま見せて再試行するか確認
- レートリミット: エラーを見せて待機を提案

## スコープ外

- `codex apply` や `codex exec` はここでは使わない。修正は Phase 3 で Claude が working tree にドラフトを当てるだけで、codex には実行させない。
- **commit / push / PR / merge はしない。** Phase 3 でも working tree に置くまで。出すのは人間 GO のもとで [[ship]] / `create-pr`。
- [[ship]] skill と自動連結しない。ユーザーが「codex review してから ship」と言ったら別ステップで順に実行 (途中で Codex の出力を読めるように)。
