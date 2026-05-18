from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable

from flask import g, jsonify, request
from sqlalchemy import select

from common.apikey.model import ApiKey

_PREFIX = "sk_"


def generate_api_key(user_id: str, name: str) -> tuple[str, ApiKey]:
    """APIキーを生成してモデルインスタンスを返す。

    生のキー文字列はこの呼び出し時のみ取得可能（DB には保存されない）。

    Args:
        user_id: キーを所有するユーザーの ID
        name: キーの用途を示す名前（管理画面等での表示用）

    Returns:
        (raw_key, ApiKey): 生のキー文字列と DB に保存するモデルインスタンス

    使用例::

        raw_key, api_key = generate_api_key(current_user.id, "My App")
        db.session.add(api_key)
        db.session.commit()
        # raw_key をユーザーに一度だけ表示する
    """
    raw = _PREFIX + secrets.token_hex(32)
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    record = ApiKey(
        user_id=user_id,
        name=name,
        key_prefix=raw[:12],
        key_hash=key_hash,
    )
    return raw, record


def require_api_key(session_factory: Callable[[], Any]) -> Callable:
    """APIキー認証デコレータファクトリ。

    X-Api-Key ヘッダーを検証し、有効なキーであれば g.api_key_user_id にユーザー ID をセットする。
    last_used_at を自動更新する。

    Args:
        session_factory: SQLAlchemy セッションを返す callable

    Returns:
        Flask ルートに適用するデコレータ

    使用例::

        from common.apikey import require_api_key

        check_key = require_api_key(lambda: db.session)

        @app.get("/api/data")
        @check_key
        def get_data():
            user_id = g.api_key_user_id
            ...
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated(*args: Any, **kwargs: Any) -> Any:
            raw = request.headers.get("X-Api-Key", "")
            if not raw:
                return jsonify({"error": "X-Api-Key header missing"}), 401

            key_hash = hashlib.sha256(raw.encode()).hexdigest()
            session = session_factory()

            record = session.execute(
                select(ApiKey).where(
                    ApiKey.key_hash == key_hash,
                    ApiKey.is_active.is_(True),
                )
            ).scalar_one_or_none()

            if record is None:
                return jsonify({"error": "Invalid or inactive API key"}), 401

            record.last_used_at = datetime.now(timezone.utc)
            session.commit()

            g.api_key_user_id = record.user_id
            return f(*args, **kwargs)

        return decorated

    return decorator
