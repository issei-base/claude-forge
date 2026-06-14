---
name: gemini-multimodal
description: Gemini CLI を使って音声・動画・PDF・画像などマルチモーダルファイルを解析する skill。Claude 本体が処理できない音声・動画の文字起こし / 要約や、PDF・画像からの抽出を Gemini に委譲する。「この mp4 を要約して」「録音を文字起こしして」「動画の要点をタイムスタンプ付きで出して」「この音声ファイル何て言ってる?」「PDF から API 仕様を抽出して」「このスクショ解析して」「Gemini でこのファイル見て」などで発動する。音声・動画は Claude が扱えない本物の穴なので積極的に使う。Preflight で `which gemini` を確認し、Login with Google・API キー不使用 (従量課金回避) を必ず案内する。単なるテキスト / コードの要約は Claude で足りるので使わない。AWS docs の確認は [[aws-docs]]、ドキュメントを図解 HTML 教材に変換したいだけなら [[doc-illustrate]] を使う。
allowed-tools: Read, Bash(which:*), Bash(gemini:*), Bash(printenv:*)
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
  gemini login   # ブラウザで "Login with Google"
  ```

### 2. 課金ガード (重要)

Gemini CLI は **認証方法で課金が変わる**。守るべきは 2 点:

- **Login with Google で認証する。** 個人 Google アカウントの無料枠 (60 req/分・1,000 req/日) でも無課金。Google AI Pro / Ultra サブスクならさらに上限が上がり、いずれもサブスク / 無料枠内なら**追加料金なし**。
- **`GEMINI_API_KEY` を使わない。** CLI は**サブスクよりも API キーの課金を優先する**ため、環境にキーがあると従量課金 (AI Studio・有料枠は請求先リンク + 最低 $10 前払い) に落ちる。
  - `printenv GEMINI_API_KEY` で確認する。**値が出たら**ユーザーに「このまま実行すると API 従量課金になる」と警告し、サブスク枠で回したいなら当該コマンドだけ環境変数を外して実行する:
    ```sh
    env -u GEMINI_API_KEY gemini -p "..." 2>&1
    ```
  - 出典 (公式・要点): [Gemini CLI authentication](https://github.com/google-gemini/gemini-cli/blob/main/docs/get-started/authentication.mdx) —「有料サブスクなら API キーは不要、外せばアカウントのサブスク枠で直接認証する」。

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
- 無料枠は 1,000 req/日。バッチで上限に当たりそうなら一言添える (サブスク枠内なら限界費用ゼロ)。

## スコープ外

- **テキスト / コードの要約・解析は Claude 本体でやる** (Gemini に投げない)。
- ドキュメント URL を図解 HTML 教材にしたいだけなら [[doc-illustrate]]、AWS の一次ソース確認は [[aws-docs]]。
- ファイルへの書き込みや編集はしない。この skill は解析 (読み取り) 専用。
