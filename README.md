# fastapi-sqlite-odai
  
## 挙動確認  
  
```
docker-compose up --build
# localhost:8000
```

# ローカル開発環境でのZoom Webhookテスト

このドキュメントではローカル環境でZoom Webhookイベントをテストする方法について説明します。

## 概要

従来はZoom WebhookのテストのためにDev環境にデプロイする必要がありましたが、以下の技術を使用してローカル環境でテストできるようになりました：

- **ngrok**: ローカルサーバーを外部に公開してWebhookを受信
- **ElasticMQ**: SQS互換のローカルSQSサーバー
- **MongoDB**: Dev環境と共有（既存のまま）

## 前提条件

- Java (ElasticMQ用)
- Node.js (v18以上)
- AWS CLI (ElasticMQとの通信用)
- ngrokアカウントとAuth Token

## セットアップ手順

### 1. ngrok Auth Tokenの設定

1. [ngrok.com](https://ngrok.com) でアカウントを作成
2. ダッシュボードで「Your Authtoken」をコピー
3. `.env.local.private` ファイルに追加：

```bash
# 既存の設定に加えて以下を追加

# ローカル開発モードを有効化
LOCAL_DEV_MODE=true

# ElasticMQ設定
ELASTICMQ_ENDPOINT=http://localhost:9324

# ngrok設定（Webhookテスト用）
NGROK_AUTH_TOKEN=your_actual_ngrok_auth_token_here
```

### 2. ローカル開発環境の起動

```bash
# 依存関係のインストール
npm ci

# ローカル開発環境の起動（ElasticMQ + ngrok + アプリケーション）
npm run start:local-dev
```

### 3. Zoom Webhookの設定

1. ngrokのWebhook URLを確認：
   - アプリケーション起動時にコンソールに表示される
   - または `http://localhost:4040` でngrok管理UIを確認
   - または `http://localhost:3000/ngrok/webhook-url` でAPI経由で確認

2. Zoom App MarketplaceでWebhook URLを設定：
   - URL: `https://your-ngrok-subdomain.ngrok.io/webhook/zoom`
   - イベント: `meeting.ended`, `recording.completed`, `recording.transcript_completed`

**注意**: ngrokのURLは毎回起動時に動的に生成されるため、ngrokを再起動するたびにZoomの設定を更新する必要があります。

## 使用方法

### アプリケーションの起動

```bash
# ローカル開発環境でアプリケーションを起動（ElasticMQ + ngrok + アプリケーション）
npm run start:local-dev
```

### Webhookのテスト

```bash
# テスト用のWebhookイベントを送信
npm run test:webhook
```

### 管理UI

- **ElasticMQ管理UI**: http://localhost:9325
- **ngrok管理UI**: http://localhost:4040
- **ngrok Webhook URL確認**: http://localhost:3000/ngrok/webhook-url

### 環境の停止

```bash
# ローカル開発環境を停止（ElasticMQ + ngrok + アプリケーション）
npm run stop:local-dev
```

## アーキテクチャ

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Zoom API      │    │     ngrok       │    │  Local App      │
│                 │───▶│                 │───▶│                 │
│  Webhook Events │    │  Public Tunnel  │    │  Port 3000      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
                                                       ▼
                                              ┌─────────────────┐
                                              │   ElasticMQ     │
                                              │   (Port 9324)   │
                                              │   SQS Queues    │
                                              └─────────────────┘
                                                       │
                                                       ▼
                                              ┌─────────────────┐
                                              │   MongoDB       │
                                              │   (Dev Shared)  │
                                              └─────────────────┘
```

## トラブルシューティング

### ElasticMQに接続できない

```bash
# ElasticMQが起動しているか確認
curl http://localhost:9324/

# ElasticMQのログを確認
tail -f elasticmq/elasticmq.log
```

### ngrokが起動しない

```bash
# ngrokのログを確認
tail -f ngrok.log

# ngrok Auth Tokenが正しく設定されているか確認
echo $NGROK_AUTH_TOKEN

# .env.local.private でNGROK_AUTH_TOKENが設定されているか確認
grep NGROK_AUTH_TOKEN .env.local.private
```

### Webhookが受信されない

1. ngrokのURLが正しく設定されているか確認
2. Zoom App MarketplaceのWebhook設定を確認
3. アプリケーションのログでエラーを確認

### SQSメッセージが処理されない

1. ElasticMQ管理UIでメッセージを確認
2. アプリケーションのSQS Subscriberが起動しているか確認
3. 環境変数 `LOCAL_DEV_MODE=true` が設定されているか確認

## 注意事項

- **MongoDB**: Dev環境と共有しているため、テストデータの取り扱いに注意
- **アクセストークン更新**: ローカル環境では無効化されている（Dynamic Moduleで制御）
- **複数人での開発**: 各開発者が異なるngrok URLを使用する必要がある
- **セキュリティ**: ローカル環境は外部に公開されるため、機密データの取り扱いに注意

## 開発フロー

1. ローカル環境でWebhookロジックを開発・テスト
2. 動作確認後、Dev環境にデプロイ
3. 本番環境へのデプロイ

これにより、Dev環境へのデプロイ頻度を大幅に削減し、開発効率を向上させることができます。
