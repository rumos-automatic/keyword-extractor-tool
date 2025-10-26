# AI機能セットアップガイド

## Google Gemini APIを使用したキーワード抽出

### 1. Gemini API キーの取得

1. [Google AI Studio](https://makersuite.google.com/app/apikey)にアクセス
2. Googleアカウントでログイン
3. 「Create API Key」をクリック
4. APIキーをコピー

### 2. APIキーの設定

以下の3つの方法のいずれかでAPIキーを設定できます：

#### 方法1: config.jsonファイル（推奨）
1. `config_template.json`を`config.json`にコピー
2. `YOUR_GEMINI_API_KEY_HERE`を実際のAPIキーに置き換え

```json
{
  "gemini_api_key": "あなたのAPIキー"
}
```

#### 方法2: 環境変数
コマンドプロンプトで：
```bash
set GEMINI_API_KEY=あなたのAPIキー
```

#### 方法3: システム環境変数
1. システムのプロパティ → 環境変数
2. 新規作成：`GEMINI_API_KEY`
3. 値：あなたのAPIキー

### 3. 必要なパッケージのインストール

```bash
pip install google-generativeai
```

または

```bash
pip install -r requirements.txt
```

### 4. 使用方法

1. アプリケーションを起動
2. 「🤖 AIを使用してキーワード抽出」にチェック
3. APIキーが正しく設定されていれば「Gemini API有効」と表示
4. キーワード抽出を実行

### トラブルシューティング

- **「API未設定」と表示される場合**
  - APIキーが正しく設定されているか確認
  - config.jsonファイルが正しい場所にあるか確認

- **エラーが発生する場合**
  - インターネット接続を確認
  - APIキーが有効か確認
  - [使用量制限](https://ai.google.dev/pricing)を確認

### 注意事項

- 無料枠：1分間に60リクエストまで
- APIキーは他人と共有しないでください
- config.jsonファイルをGitにコミットしないよう注意

### AI機能のメリット

- より文脈を理解した的確なキーワード抽出
- 商品の特徴を自動で認識
- 日本語・英語両方に対応
- ブランド名の自動認識が向上