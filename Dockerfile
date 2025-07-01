FROM python:3.11-slim

WORKDIR /app

# システムの依存関係をインストール
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Pythonの依存関係をインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# NLTKデータをダウンロード
RUN python -c "import nltk; nltk.download('punkt')"

# アプリケーションのコードをコピー
COPY . .

# ポート設定
EXPOSE 5001

# 環境変数
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5001

# アプリケーション実行
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "2", "app:app"]