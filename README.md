# common-libs

Pythonプロジェクト向けの共通ライブラリ集です。JWT認証・構造化ログ・Stripe決済・メール送信の4モジュールを提供します。

## インストール

```bash
pip install git+https://github.com/yourorg/common-libs.git
```

特定バージョンを指定する場合:

```bash
pip install git+https://github.com/yourorg/common-libs.git@v0.1.0
```

## 使用例

### 認証 (`common.auth`)

#### JWT（既存機能）

```python
from common.auth import create_token, require_auth
from flask import Flask, g, jsonify

app = Flask(__name__)

# JWTトークンの生成（有効期限: 1時間）
token = create_token(user_id=42, expires_in=3600)

# 保護されたエンドポイントにデコレータを適用
@app.route("/profile")
@require_auth
def profile():
    return jsonify({"user_id": g.user_id})
```

#### メール認証（ユーザーモデル + パスワード）

各プロジェクトで `BaseUser` を継承してユーザーモデルを定義し、プロジェクト固有のカラムを追加できます。

```python
# models/user.py（各プロジェクト側）
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String
from common.auth import BaseUser

class User(BaseUser):
    __tablename__ = "users"
    nickname: Mapped[str | None] = mapped_column(String(64), nullable=True)
    plan: Mapped[str] = mapped_column(String(32), default="free")
```

```python
# DBセットアップ（各プロジェクト側）
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from common.auth import BaseUser, hash_password, verify_password, create_token

engine = create_engine("postgresql://user:pass@localhost/mydb")
BaseUser.metadata.create_all(engine)  # usersテーブルを作成

# ユーザー登録
with Session(engine) as session:
    user = User(email="user@example.com", password_hash=hash_password("secret"))
    session.add(user)
    session.commit()

# ログイン
with Session(engine) as session:
    user = session.query(User).filter_by(email="user@example.com").first()
    if user and verify_password("secret", user.password_hash):
        token = create_token(user.id)  # JWTを発行
```

#### Google認証

```python
# Flask側のコールバック実装例
from flask import Flask, redirect, request, jsonify, session
from sqlalchemy.orm import Session
from common.auth import GoogleOAuth, create_token

app = Flask(__name__)
google = GoogleOAuth()  # 環境変数 GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET を使用

REDIRECT_URI = "https://myapp.example.com/auth/google/callback"

@app.route("/auth/google")
def google_login():
    # Googleの認証ページにリダイレクト
    return redirect(google.get_auth_url(REDIRECT_URI))

@app.route("/auth/google/callback")
def google_callback():
    code = request.args.get("code")
    user_info = google.exchange_code(code, REDIRECT_URI)

    # DBでユーザーを検索、なければ新規作成
    with Session(engine) as db:
        user = db.query(User).filter_by(google_id=user_info.google_id).first()
        if not user:
            user = User(email=user_info.email, google_id=user_info.google_id)
            db.add(user)
            db.commit()
            db.refresh(user)

    token = create_token(user.id)
    return jsonify({"token": token})
```

環境変数 `JWT_SECRET_KEY` / `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` を設定してください。

---

### 構造化ログ (`common.logging`)

```python
from common.logging import StructuredLogger

logger = StructuredLogger(service="order-api")

logger.info("注文を受け付けました", order_id="ORD-001", amount=1500)
logger.warn("在庫が少なくなっています", sku="ABC-123", remaining=3)
logger.error("決済に失敗しました", order_id="ORD-002", reason="card_declined")
```

出力例（JSON形式）:

```json
{"timestamp": "2026-04-22T10:00:00+00:00", "level": "INFO", "service": "order-api", "message": "注文を受け付けました", "order_id": "ORD-001", "amount": 1500}
```

---

### Stripe決済 (`common.payment`)

```python
from common.payment import StripeClient

client = StripeClient()  # 環境変数 STRIPE_SECRET_KEY を使用

result = client.charge(
    amount=1000,           # ¥1,000（最小通貨単位）
    currency="jpy",
    payment_method_id="pm_card_visa",
)

if result.success:
    print(f"決済成功: {result.payment_intent_id}")
else:
    print(f"決済失敗: {result.error}")
```

環境変数 `STRIPE_SECRET_KEY` にStripeのシークレットキーを設定してください。

---

### メール送信 (`common.notify`)

```python
from common.notify import Mailer, MailConfig

config = MailConfig(
    host="smtp.example.com",
    port=587,
    user="no-reply@example.com",
    password="smtp-password",
    from_address="no-reply@example.com",
)

mailer = Mailer(config)

# テキストメール
mailer.send(
    to="user@example.com",
    subject="ご注文確認",
    body="ご注文ありがとうございます。",
)

# HTMLメール（複数宛先）
mailer.send(
    to=["a@example.com", "b@example.com"],
    subject="お知らせ",
    body="<h1>重要なお知らせ</h1><p>内容はこちら。</p>",
    html=True,
)
```

## 環境変数

| 変数名 | 説明 | デフォルト |
|---|---|---|
| `JWT_SECRET_KEY` | JWT署名用シークレットキー | `changeme-in-production` |
| `GOOGLE_CLIENT_ID` | Google OAuthクライアントID | （必須） |
| `GOOGLE_CLIENT_SECRET` | Google OAuthクライアントシークレット | （必須） |
| `STRIPE_SECRET_KEY` | Stripe APIシークレットキー | （空） |

本番環境では必ず `.env` ファイルまたはシークレットマネージャーで設定してください。

## 開発環境セットアップ

### 1. 仮想環境の作成

```bash
python -m venv .venv
```

### 2. 仮想環境の有効化

```bash
# Mac/Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### 3. 開発用インストール

```bash
pip install -e ".[dev]"
```

### 4. テスト実行

```bash
pytest
```
