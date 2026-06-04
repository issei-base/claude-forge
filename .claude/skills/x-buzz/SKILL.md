---
name: x-buzz
description: >-
  Claude / Claude Code / AI コーディングに関する日本語の X(Twitter) 投稿を、インプレッション最大化を狙って生成・量産する。
  「Tips/ハマりどころ (C)」「逆張り・意見 (D)」「海外バズの型を翻訳・カスタム」の3軸で、記憶ではなく
  ユーザーの本物ネタ (Claude Code changelog・claude-forge の実物 skill・実務知見) から下書きを作り、
  バズる型 (フック・構成・文字数・スレ判断) に整え、reach を削る要因 (本文 URL・ハッシュタグ過多・丸コピ・重複) を
  機械チェックで潰してから、Typefully MCP に下書き/予約 push するか、ローカルの投稿キューに書き出す。
  ユーザーが「X投稿作って」「今日のポスト考えて」「Claude ネタでツイート」「バズる投稿」「ツイート量産」
  「X のネタ出して」「Typefully に下書き作って」「x-buzz」などと、X 向け投稿の生成・量産を求めたら積極的に発動する。
  毎日 cron で定期生成したいときは schedule skill と組み合わせる。雑談やただの感想、英語圏オンリー向け投稿は対象外。
---

# x-buzz — Claude ネタの X 投稿を量産する

インプ目的で X 投稿を半自動量産する skill。流れは
**仕込み → 型選び → 起草 → 機械検証 → 配信 → 記録** の一続き。
**生成 (型 + 本物ネタ) が主役、配信 (Typefully) は差し替え可能な last-mile**。

## 哲学 (ここを外すと逆効果)

1. **本数より質。** リサーチ上、自動・高頻度・同ジャンルの連投こそ X が最も throttle する
   (インプレゾンビ判定)。安全圏は 2〜3本/日、**10〜12本/日は「自然な投稿」の上限ギリ**。
   水増しは shadowban を招き、狙い (インプ) と逆に振れる。**良いネタが無ければ正直に本数を減らす**
   (不作の朝に無理に捻り出さない)。
2. **丸コピ厳禁。** 海外バズは **型 (フック・構成) だけ**借り、中身はユーザーの本物ネタで埋める。
   コピペ転載は reach 激減 + 通報リスク。あなたは claude-forge という本物の素材を持っているのが強み。
3. **記憶で書かない。** changelog の内容・数値・skill の挙動は一次ソースから (claude-forge の正確さ方針)。

## 1. 仕込み (記憶で書かない)

ネタの井戸を先に汲む。最低 1〜2 ソースから具体を拾ってから書く:

- **Claude Code changelog / 公式**: 最新の変更点を一次ソースから拾う:
  ```bash
  curl -sL https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md | head -60
  ```
- **claude-forge の実物 skill**: この repo の `.claude/skills/*/SKILL.md` 自体がネタの宝庫
  (doc-illustrate の図解、ship の hard guard、SRE 系の自動化など「作った話」)。
- **実務知見**: ユーザーの指導・AWS・運用で得た非自明な学び。必要なら本人に一言確認。
- **海外バズの型**: WebSearch で直近の英語圏バズ投稿/解析を拾い、**型として**参考にする
  (中身はコピーしない)。フック例は [references/post-patterns.md](references/post-patterns.md)。
- (任意) `interest-profile` があれば読み、ユーザーの関心に寄せる。

## 2. 型を選ぶ

[references/post-patterns.md](references/post-patterns.md) の **フック・バンク**から、今日のネタに合う型を選ぶ。
ユーザー指定の軸 (既定は C+D+翻訳カスタムのミックス) に沿って:

- **C (Tips/ハマりどころ)** → 「誰も言わない gotcha」「数字付きリスト」「Before/After」「Y で X を作った」
- **D (逆張り・意見)** → 「逆張り/神話崩し」「Unpopular opinion」「Hard truth」「あるある自虐 (【悲報】系)」「一人称の意見エッセイ」
- **翻訳カスタム** → 海外で当たった型を JP 向けに再構成 (共感 + 結論先出し)
- **引用RT (quote-tweet)** → 話題のツイートを引用して take を一言乗せる (型 F)。ネタ元は URL 指定か、フォロー中で話題のツイート。配信は §5 の quote_post_url。

1 投稿 = 1 つの型。詰め込まない。

## 3. 起草

各投稿を書くときの規律 (詳細と例は post-patterns.md):

- **長さの予算 (初稿から守る)**: 日本語は 1 文字 ≈ 2 カウント (上限 280 = **~140字**)。
  単発は **~100〜130字を目安**に書き、超えそうなら詰め込まず**スレに割る**。
  初稿から余白を残すと、後段の検証で文字数超過の往復 (trim のやり直し) が減る。
- **フックは最初の 2 行を ~100 字以内・自己完結**。モバイルで「もっと見る」前に刺す。
- **声・文体 (最重要・ユーザー指定)**: ① **バッククォートを使わない** — X では装飾されず ` がそのまま出て不自然。コマンド/パス/フラグは地の文でそのまま書く (claude mcp add、.claude/skills/、--scope user、cp -R)。② **丁寧語 (です/ます) を避け plain/casual 体**で書く (だ・なる・した・ない)。③ **Tips bot 然とさせない** — 本音・実感・ちょっとした感情を一言入れて「人が書いた」声にする (例:「地味にハマった」「これ地味にデカい」「何も信じられない」)。手本トーンは [references/post-patterns.md](references/post-patterns.md) §5。
- **日本語は共感 + PREP (結論先出し)**。jargon を絞り、フォロワー外にも届く言葉に。
- **改行で 1 行 1 アイデア**。
- **単発 vs スレ**: ホットテイク/即 gotcha は単発、ワークフロー/before-after/リストは 3〜5 ツイートのスレ
  (スレは空行4連続で区切る = Typefully の threadify 規則)。
- **メディア提案**: インプ目的の最適は「テキスト先行 + 実物スクショ/GIF」。ターミナル出力・diff・
  CLAUDE.md・doc-illustrate の図解など **証拠ショット**を一言添える (添付は基本ユーザーが用意)。
- **リンクは本文に入れない** (~30-50% reach 減)。URL は「最初の返信に貼る」と注記する。
- **ハッシュタグは 0〜1**。3+ は spam 判定。

スケルトン (A〜E) を雛形に使ってよい。**`[ ]` を本物ネタで具体的に埋める**。

## 4. 機械検証 (目検に任せない)

起草した候補を JSON 配列にして検証スクリプトにかける。reach を削る要因と過去投稿との重複を機械的に弾く:

```bash
# 候補を JSON 配列で渡す (string 配列 か [{id?,text}] のどちらでも)
python3 .claude/skills/x-buzz/scripts/validate_post.py candidates.json
```

チェック項目: **weighted 文字数超過 (日本語 ~140字)・ハッシュタグ過多・本文内 URL・
エンゲージ乞食フレーズ・過去投稿との完全/類似重複** (`data/x_buzz_posted.jsonl` と照合)。
`issues` が出た候補は**直してから配信**する。スレは空行4連続で分割し各ツイートを個別検証。

## 5. 配信

Typefully MCP があるか確認 (tool 一覧に typefully 系があるか)。接続済み・公式 v2 API。
アカウント (social_set_id) は **`get_me` / `list_social_sets` で自分の値を取得**して使う (ハードコードしない)。詳細は [references/typefully.md](references/typefully.md)。

**呼び出しの形 (v2・実測)**: `create_draft(social_set_id, requestBody={platforms:{x:{enabled:true, posts:[{text:"..."}]}}})`。
- **下書き = publish_at を省略**。スレは `posts` を複数要素にする (配列の各 {text} が 1 ツイート。threadify ではなく自前で分割)。
- **既存下書きの差し替え**は `edit_draft(social_set_id, draft_id, requestBody={...})`。
- **引用RT**は post に `quote_post_url:"https://x.com/.../status/..."` を付ける (上に乗せる take は `text`)。型 F 参照。

- **Phase 1 (手動承認・今ここ)**: publish_at を**付けず下書きだけ** → ユーザーが Typefully で確認して自分で Schedule。
- **Phase 2 (自動)**: `publish_at:"next-free-slot"` か ISO 日時 (timezone 必須) を付けて予約。
- **Typefully 未導入なら fallback**: 候補を **`data/x_buzz_queue/<YYYY-MM-DD>.md`** に
  「コピペで投稿できる形」(本文・スレ区切り・メディア提案・返信用/引用元 URL を併記) で書き出し、手動投稿。

公開アカへの外向き発信なので、**Phase 1 は必ず人間の承認を挟む**。自動公開に切り替えるのは
ユーザーが「自動でいい」と明示してから (引用RT も同じ)。

## 6. 記録 (dedup)

**実際に配信/予約したものだけ**をログに記録し、翌回ダブらせない:

```bash
python3 .claude/skills/x-buzz/scripts/validate_post.py --mark candidates.json
```

提示しただけ/不採用の候補は記録しない。ログ `data/x_buzz_posted.jsonl` は gitignore 済み。

## 定期運用 (cron)

この skill は「1 回分の生成ロジック」。定期化は `schedule` skill / cron で
`/x-buzz` を 1 日数回叩く形にする (「毎日 朝/昼/夜 に x-buzz 回して」)。
**ただし哲学 1 に従い、1 回あたりの本数は欲張らない**。cron でも validate の `--mark` まで回し、
重複を防ぐ。

## 出力フォーマット (対話時)

候補をユーザーに見せるときは、採否を判断しやすく:

```
🧵 x-buzz — <YYYY-MM-DD> / 軸: C+D+翻訳

1. [C・gotcha] <フック1行>
   <本文プレビュー>
   📎 提案メディア: <スクショ/GIF 案> ｜ 🔗 返信に: <URL があれば>
   ✅ 検証: 132字 / ハッシュタグ0 / 重複なし

2. [D・逆張り] ...

▶ どれ出す?  [1,3を Typefully 下書き] [全部キューに書き出し] [作り直し]
```

検証で issues があれば候補ごとに ⚠️ で明示し、勝手に通さない。

## メモ

- **エンゲージ重みは directional**。「返信 13.5×」等は 2023 由来で 2026 は重み非公開。確定値として書かない
  (post-patterns.md の警告参照)。
- **正直さ > 体裁**。良いネタが無い日は「今日は質の高いネタが薄いので N 本だけ」と正直に。
- **生成物はコミットしない**: `data/x_buzz_posted.jsonl` / `data/x_buzz_queue/` は gitignore 済み
  (個人の投稿内容を public repo に出さない)。
- skill を直す/PR にするときは [ship](../ship/SKILL.md) (main 直 push 禁止・merge は手動)。
