---
name: gemini-multimodal
description: Gemini CLI を使って音声・動画・PDF・画像などマルチモーダルファイルを解析する skill。Claude 本体が処理できない音声・動画の文字起こし / 要約や、PDF・画像からの抽出を Gemini に委譲する。「この mp4 を要約して」「録音を文字起こしして」「動画の要点をタイムスタンプ付きで出して」「この音声ファイル何て言ってる?」「PDF から API 仕様を抽出して」「このスクショ解析して」「Gemini でこのファイル見て」などで発動する。音声・動画は Claude が扱えない本物の穴なので積極的に使う。Preflight で `which gemini` と API キー認証 (`GEMINI_API_KEY` + `selectedType: gemini-api-key`) を確認する — 無料 OAuth (Login with Google) は廃止済みで、この環境は API キー運用が正。無料枠は flash 系モデルのみ。単なるテキスト / コードの要約は Claude で足りるので使わない。AWS docs の確認は [[aws-docs]]、ドキュメントを図解 HTML 教材に変換したいだけなら [[doc-illustrate]] を使う。
allowed-tools: Read, Bash(which:*), Bash(gemini:*), Bash(printenv:*), Bash(cp:*)
---

# gemini-multimodal

マルチモーダルファイル (音声・動画・PDF・画像) の解析を **Gemini CLI** に委譲する。`gemini -p "<指示> @<path>"` でファイルを読ませ、文字起こし・要約・抽出などを行う。

## なぜ Gemini か (どこまで使うか)

- **音声・動画は Claude が処理できない本物の穴。** ここが主用途 —— `.mp3` / `.wav` の文字起こし、`.mp4` / `.mov` の要約・タイムスタンプ抽出は Gemini にしかできない。
- **PDF・画像は Claude 本体の `Read` でも読める。** 単発・少数なら `Read` の方が速く文脈も繋がる。**大量・バッチ処理や、ユーザーが明示的に Gemini を指定したとき**に Gemini を使う。迷ったら音声/動画＝Gemini、PDF/画像＝まず Read を検討。

## Preflight (毎回・順に確認)

### 1. CLI の存在

- `which gemini` が成功すること。失敗したら次を案内して STOP:
  ```sh
  npm install -g @google/gemini-cli
  ```

### 2. 認証 (重要 — 2026-06 に前提が変わった)

**無料の Login with Google (OAuth 個人枠) は廃止済み。** 旧構成で実行すると
`IneligibleTierError: This client is no longer supported` で弾かれる。この環境の正は
**API キー運用**。「API キーを外して OAuth に戻す」という旧案内は**しない**
(正常な設定を壊す行為になる)。

- 現行の正しい構成 (このマシンは設定済み):
  1. [AI Studio](https://aistudio.google.com/apikey) で無料 API キーを発行し、`GEMINI_API_KEY` を環境に置く
  2. `~/.gemini/settings.json` の `security.auth.selectedType` を `gemini-api-key` にする
     (キーがあっても `selectedType` が oauth のままだと OAuth を見にいって弾かれる)
- Preflight 確認は 2 つ: ① `printenv GEMINI_API_KEY` に値があること (**無ければ**上記 1→2 を案内して STOP)。② `~/.gemini/settings.json` の `security.auth.selectedType` が `gemini-api-key` であること (`oauth-personal` のままなら書き換えを案内して STOP)。実行時に `IneligibleTierError` が出たら②の確認漏れを疑う。
- **無料枠で使えるのは flash 系のみ** (`gemini-2.5-flash` 等)。pro 系は billing 必須で
  `Error when talking to Gemini API` になる。認証は正しいのにモデル起因のエラーが出たら
  `-m gemini-2.5-flash` を明示して再実行する。
- レート上限・課金の現行値は変わりうるので、必要になったら AI Studio の rate limits ページで
  確認する (記憶で数値を答えない)。

### 3. ファイルの存在と場所

- 渡されたパスのファイルが実在すること。無ければユーザーに確認。
- **gemini を実行する cwd のツリー内にあること。** gemini は workspace (実行ディレクトリ) 外のファイルを弾く (下記「実行」参照)。cwd 外なら workspace 内に `cp` してから渡す。

## 対応拡張子

| カテゴリ | 拡張子 |
|---|---|
| PDF | `.pdf` |
| 動画 | `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm` |
| 音声 | `.mp3`, `.wav`, `.m4a`, `.flac`, `.ogg` |
| 画像 | `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.svg` |

## 実行

**重要 — gemini はファイルアクセスを実行ディレクトリ (workspace) 配下に制限する。** cwd のツリー外 (例: `/tmp/...`) を `@` で渡すと `Path not in workspace` で弾かれる (gemini 0.46.0 で確認)。なので **対象ファイルのあるディレクトリ (またはその祖先) で gemini を実行**し、その中のパスで `@` 参照する。stderr も捕捉する (`2>&1`)。

```sh
# 対象ファイルのあるディレクトリへ移動してから実行する
cd "$(dirname /abs/path/to/audio.mp3)"

# 音声 → 文字起こし + 要約
gemini -p "Transcribe and summarize @audio.mp3" 2>&1

# 動画 → 要点 + タイムスタンプ
gemini -p "Summarize key concepts with timestamps @video.mp4" 2>&1

# PDF → 仕様抽出
gemini -p "Extract the API specs as a table @spec.pdf" 2>&1

# 画像 → 解析
gemini -p "Describe what this screenshot shows and any visible errors @shot.png" 2>&1
```

- workspace 外のファイルを解析したいときは、まず workspace 内 (cwd のツリー) に `cp` してから渡す。
- 先頭に出る `Warning: 256-color...` / `Ripgrep is not available` は無害なノイズ。`2>&1` で拾った上で報告からは省いてよい。
- 重い入力 (長い動画・大量バッチ) は時間がかかるのでタイムアウトを長めに取る。

## 報告

- **Gemini の出力をそのまま見せる。** 文字起こしは逐語、要約は要約として提示する。Claude による二次要約で潰さない。
- ユーザーの依頼に応じてプロンプトを調整する (「タイムスタンプ付きで」「英語で」「箇条書きで」等)。
- 大量バッチで無料枠の上限 (429 / quota エラー) に当たったら、その旨と AI Studio の rate limits ページを添えて報告する。

## スコープ外

- **テキスト / コードの要約・解析は Claude 本体でやる** (Gemini に投げない)。
- ドキュメント URL を図解 HTML 教材にしたいだけなら [[doc-illustrate]]、AWS の一次ソース確認は [[aws-docs]]。
- ファイルへの書き込みや編集はしない。この skill は解析 (読み取り) 専用。
