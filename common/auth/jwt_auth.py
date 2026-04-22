import os
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Callable

import jwt
from flask import request, jsonify, g

# 環境変数からシークレットキーを取得（本番では必ず設定すること）
_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "changeme-in-production")
_ALGORITHM = "HS256"


def create_token(user_id: str | int, expires_in: int = 3600) -> str:
    """JWTトークンを生成する。

    Args:
        user_id: ユーザーID
        expires_in: 有効期限（秒）、デフォルト1時間

    Returns:
        署名済みJWT文字列
    """
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    return jwt.encode(payload, _SECRET_KEY, algorithm=_ALGORITHM)


def require_auth(f: Callable) -> Callable:
    """Authorizationヘッダーを検証するFlaskデコレータ。

    有効なBearerトークンが存在する場合、g.user_id にユーザーIDをセットする。
    """
    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authorization header missing or invalid"}), 401

        token = auth_header[len("Bearer "):]

        try:
            payload = jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
            g.user_id = payload["sub"]
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        return f(*args, **kwargs)

    return decorated
