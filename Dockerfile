FROM python:3.11-slim

WORKDIR /app

# システムパッケージのインストール（MeCab追加）
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    mecab \
    libmecab-dev \
    mecab-ipadic-utf8 \
    curl \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

# NEologd辞書のインストール（オプション・高精度）
RUN cd /tmp && \
    curl -LO https://github.com/neologd/mecab-ipadic-neologd/archive/master.tar.gz && \
    tar -xzf master.tar.gz && \
    cd mecab-ipadic-neologd-master && \
    ./bin/install-mecab-ipadic-neologd -n -y || echo "NEologd installation failed, using standard dictionary"

# Pythonの依存関係をインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 非rootユーザーを作成
RUN groupadd -g 1000 appuser && \
    useradd -r -u 1000 -g appuser appuser

# ディレクトリ作成（権限付与）
RUN mkdir -p /app/data/database /app/logs && \
    chown -R appuser:appuser /app

# アプリケーションファイルをコピー
COPY --chown=appuser:appuser app/ ./app/

# 非rootユーザーに切り替え
USER appuser

# ポートを公開
EXPOSE 8000

# アプリケーション起動
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]