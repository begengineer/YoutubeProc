# YouTube コメント分析 Web アプリケーション

櫻坂46の動画のコメント感情分析を自動で行い、月間ランキングや再生数推移を表示するWebアプリケーションです。5日に1回自動でデータが更新されます。

## 機能

- **自動コメント感情分析**: 櫻坂46の動画コメントを自動でポジティブ、ネガティブ、ニュートラルに分類
- **自動更新**: 5日に1回自動でデータを更新
- **月間ランキング**:
  - ネガティブコメントが多い動画 トップ10
  - ポジティブコメントが多い動画 トップ10
  - コメント数が多い動画 トップ20
- **再生数推移**: 月ごとの動画再生数、いいね数、コメント数の推移表示
- **データベース管理**: 分析済み動画の管理機能

## セットアップ

### 1. 必要な環境
- Python 3.8以上
- YouTube Data API v3 のAPIキー

### 2. YouTube API キーの取得
1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作成
2. YouTube Data API v3 を有効化
3. APIキーを作成

### 3. インストール

```bash
# 依存関係のインストール
pip install -r requirements.txt

# TextBlobの言語データをダウンロード
python -c "import nltk; nltk.download('punkt')"
```

### 4. 環境変数の設定

YouTube APIキーを環境変数に設定してください：

**Windows:**
```cmd
set YOUTUBE_API_KEY=あなたのAPIキー
```

**macOS/Linux:**
```bash
export YOUTUBE_API_KEY=あなたのAPIキー
```

### 5. 環境変数の設定

**本番環境では環境変数として設定:**
```bash
export YOUTUBE_API_KEY=あなたのYouTube_APIキー
export SECRET_KEY=your_secret_key_here
```

**開発環境では `.env` ファイルを作成:**
```
# YouTube API設定
YOUTUBE_API_KEY=あなたのYouTube_APIキー

# Flask設定
SECRET_KEY=your_secret_key_here
```

### 6. アプリケーションの起動

```bash
python3 app.py
```

**WSL環境での起動の場合:**
- コンソールに表示されるIPアドレスでアクセス（例：`http://172.18.12.158:5001`）
- または `http://localhost:5001` でアクセスできます

**通常の環境での起動の場合:**
- ブラウザで `http://localhost:5001` にアクセスしてください

**起動確認:**
起動に成功すると以下のようなメッセージが表示されます：
```
* Running on all addresses (0.0.0.0)
* Running on http://127.0.0.1:5001
* Running on http://172.18.12.158:5001
```

## 使用方法

1. **自動データ更新**:
   - アプリケーション起動時に自動でデータ分析が実行されます
   - 5日に1回自動でデータが更新されます
   - 最終更新日時がページ上部に表示されます

2. **ランキング表示**:
   - ページ読み込み時に自動で表示されます
   - 各種ランキングが自動更新されます

3. **グラフ表示**:
   - 月別コメント数推移グラフ
   - 月別再生数推移グラフ
   - ページ読み込み時に自動で表示されます

4. **データベース管理**:
   - 分析済み動画の一覧表示
   - 個別動画データの削除
   - データベース全体のクリア

## データ保存

分析結果は `youtube_analysis.db` SQLiteデータベースに保存されます。

## デプロイメント

### Herokuでのデプロイ

1. **Herokuアカウントの作成とCLIインストール**
2. **アプリケーションの作成**:
   ```bash
   heroku create your-app-name
   ```

3. **環境変数の設定**:
   ```bash
   heroku config:set YOUTUBE_API_KEY=your_youtube_api_key
   heroku config:set SECRET_KEY=your_secret_key
   ```

4. **デプロイ**:
   ```bash
   git add .
   git commit -m "Deploy to Heroku"
   git push heroku main
   ```

### Dockerでのデプロイ

1. **環境変数ファイルの作成** (`.env`):
   ```
   YOUTUBE_API_KEY=your_youtube_api_key
   SECRET_KEY=your_secret_key
   ```

2. **Docker Composeで起動**:
   ```bash
   docker-compose up -d
   ```

### 手動デプロイ

1. **依存関係のインストール**:
   ```bash
   pip install -r requirements.txt
   ```

2. **環境変数の設定**:
   ```bash
   export YOUTUBE_API_KEY=your_youtube_api_key
   export SECRET_KEY=your_secret_key
   ```

3. **アプリケーションの起動**:
   ```bash
   # Webサーバー
   gunicorn --bind 0.0.0.0:5001 app:app
   
   # バックグラウンドで5日間隔の自動更新スケジューラー
   python scheduler.py &
   ```

## 注意事項

- YouTube API には1日あたりのクォータ制限があります
- 大量のコメントがある動画の場合、分析に時間がかかることがあります
- **APIキーは環境変数として設定し、絶対に公開しないでください**
- `.env` ファイルは `.gitignore` に含まれており、Gitにコミットされません
- 本番環境では必ず環境変数を使用してください

## トラブルシューティング

### よくある問題

1. **"YouTube API key not found" エラー**
   - 環境変数 `YOUTUBE_API_KEY` が正しく設定されているか確認

2. **"Video not found" エラー**
   - YouTubeのURLが正しいか確認
   - 動画が公開設定になっているか確認

3. **コメント取得エラー**
   - 動画のコメントが無効化されている可能性があります
   - APIクォータが上限に達している可能性があります