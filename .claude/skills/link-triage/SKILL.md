---
name: link-triage
description: "リンク/記事の URL **またはセミナー・勉強会で学んだメモ / 貼り付けテキスト**を、宛先を指定せず渡されたとき、すぐに cc-tune や playbook-sync を発火させず、まず（URL なら）本文を生テキストで読んでから『どの skill が有効か』を判定して理由つきで提案し、判断をユーザーに委ねるトリアージ skill。入力は URL でもメモでも受ける。判定の選択肢は 自分の CC 環境改善=cc-tune / チーム規範 repo 反映=playbook-sync / 中身を解説するだけ=explain-article / 図解 HTML 教材=doc-illustrate / どれも不要(素の Claude)。自分では診断・取り込み・書き込みをせず、承認後に選ばれた skill へ橋渡しするだけ。ユーザーが「このリンクどっちの skill がいい?」「読んでから判断して」「これ cc-tune? playbook-sync?」「宛先は任せる、まず読んで決めて」「このセミナーのメモ、どの skill で扱うのがいい?」などと、宛先を決めずにリンク/記事/メモを渡して skill の振り分けを求めたときに発動する。**振り分けを明示的に頼まれていなくても、宛先を指定せず素のリンク/メモを最小限の言葉(『この記事よんで』『これ読んで/見て』『ちょっと見て』『共有』など)で渡され、かつ内容が CC / AI / 開発ツール寄りなら、まず triage を通す**(『よんで』だけで explain-article や素の Claude に直行しない。Claude Code / AI コーディング系の URL は特に triage 対象)。最初から宛先が明確なら triage を挟まず直接その skill を使う:『うちに取り込める?/CC 環境よくできる?』→[[cc-tune]]、『プレイブックに入れて/ai-team-playbook に反映』→[[playbook-sync]]、**明示的に**『深掘りして解説して/噛み砕いて説明して』と解説を求められた時のみ→[[explain-article]]、『図解 HTML 教材にして』→[[doc-illustrate]]。"
allowed-tools: Read, Bash(python3:*), Bash(curl:*)
---

# link-triage

リンク/記事の URL **またはセミナー・勉強会のメモ / 貼り付けテキスト**を渡されたとき、**すぐに `cc-tune` や `playbook-sync` を発火させず、まず中身を読んでから「どの skill が有効か」を判定してユーザーに委ねる**トリアージ skill。自分では診断・取り込み・書き込みをせず、**判定と橋渡しだけ**を行う。

## いつ使うか / 使わないか

- **使う**: 宛先（自分の CC 環境 or チーム repo）を指定せず素のリンク or メモ/貼り付けテキストを渡された / 「どっちの skill がいい?」「読んでから判断して」「これ cc-tune? playbook-sync?」と振り分けを委ねられた。
  - **振り分けを明示的に頼まれなくても**、宛先未指定の素のリンク/メモを最小限の言葉（「この記事よんで」「これ読んで/見て」「ちょっと見て」「共有」）で渡され、内容が **CC / AI / 開発ツール寄り**（Claude Code 系 URL は特に）なら、まず triage を通す。「よんで」だけで explain-article や素の Claude に直行しない。
- **使わない（明示の宛先がある時は triage を挟まず直接その skill へ）**:
  - 「うちに取り込める? / CC 環境よくできる?」→ [[cc-tune]]
  - 「プレイブックに入れて / ai-team-playbook に反映」→ [[playbook-sync]]
  - **明示的に**「深掘りして解説して / 噛み砕いて説明して」→ [[explain-article]]（bare な「よんで」は triage 側）
  - 「図解 HTML 教材にして」→ [[doc-illustrate]]

## ワークフロー

### 1. 中身を取得する
- **URL** — 要約モデルを挟まず生テキストで取る（[[cc-tune]] / [[doc-illustrate]] と同じ原則）。claude-forge 原本の絶対パスで叩く（cwd 非依存）: `python3 ~/projects/claude-forge/.claude/skills/doc-illustrate/scripts/extract.py <URL>`。失敗したら `curl -sL -A "Mozilla/5.0" <URL>`。**WebFetch は最後の手段**。取れなければ推測せず**本文の貼り付けを頼む**。
- **メモ / 貼り付けテキスト**（セミナー・勉強会の学びなど） — 取得は不要。**渡されたテキストをそのまま材料にする**。判定に足りない所は推測で埋めず確認する。

### 2. 読んで要点を掴む
何の記事/メモか / 主張・手法の核 / 具体テクニック / 前提。**判定に足る分だけ**読む（深掘りは下流 skill の仕事）。

### 3. どの skill が有効かを判定する（順序つき手順・自分では実行しない）
1. **まず「内容が CC / AI の使い方・運用・設定・hook・チーム規範に関係するか」を見る。** 無関係なら「どの skill も不要（素の Claude で解説/要約で足りる）」を提案して終わる。
2. 関係するなら**宛先を判定する**:
   - **自分の CC 環境**（claude-forge の skill / agent・個人 `~/.claude` の設定・hook・statusLine 等）を良くできる → `cc-tune`
   - **チームの規範（あるべき論: ガードレール / 機密 / 可観測性 / MCP / レビュー）** に反映 → `playbook-sync`
   - **両方に効く**（例: ガードレール記事）→ 両方を提案し、順番を添える（まず `cc-tune` で自分の環境を診断 → 別途 `playbook-sync` でチーム規範に反映、等）
   - **中身を理解したいだけ** → `explain-article`。**公式 docs を図解教材にしたいだけ** → `doc-illustrate`
3. 各候補を **✅本命 / 🤔次点 / ❌不要** で理由つきに。記憶の skill 一覧に頼らず、迷えば `ls ~/projects/claude-forge/.claude/skills/` で現物を見る。

### 4. 提案して判断を委ねる（ここで必ず止まる）
チャットに短く出す（日本語）:
- **📄 解説**（短く・噛み砕く）
- **🧭 判定**（どの skill が有効か・理由。✅/🤔/❌）
- **▶️ 委ねる**（「この skill で進める? 別にする? 見送る?」で止まる）

**ユーザーが選ぶまで下流 skill を発火しない。**

### 5. 承認後、選ばれた skill に橋渡しする
ユーザーが選んだら、その skill（`cc-tune` / `playbook-sync` / `explain-article` / `doc-illustrate`）を発火させる。**link-triage 自身は診断・取り込み・書き込みを一切しない。**

## してはいけないこと

- **読まずに判定しない。** URL なら本文取得が先（取れなければ貼り付けを頼む）。メモも中身を読んでから判定する（推測で判定しない）。
- **自分で診断・取り込み・書き込みをやらない。** それは下流 skill の仕事。link-triage は判定と橋渡しだけ。
- **承認前に下流 skill を勝手に発火しない。** 必ず手順 4 で委ねて止まる。
- **明示の宛先がある依頼に割り込まない。** その時は triage を挟まず直接該当 skill（上記「使わない」参照）。
- **深掘り解説で終始しない。** 解説は判定の材料として短く。深い解説が目的なら [[explain-article]] に渡す。

## 関連

- 下流 skill: [[cc-tune]]（自分の CC 環境改善の診断）/ [[playbook-sync]]（チーム規範 repo の更新）/ [[explain-article]]（記事のチャット解説）/ [[doc-illustrate]]（公式 docs の図解 HTML 教材）。
- 取得・一次ソースの原則は [[doc-illustrate]] / [[cc-tune]] と同じ（生テキスト優先）。`extract.py` も [[doc-illustrate]] のものを流用。
- 役割の違い: link-triage は**宛先を決める前段の振り分け**、cc-tune / playbook-sync は**宛先が決まった後の実行**。
