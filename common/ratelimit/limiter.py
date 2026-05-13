import hashlib
import os
import time
import uuid
from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import g, jsonify, make_response, request


class RateLimiter:
    """Redis ベースのレート制限。

    limiter = RateLimiter(redis_url="redis://localhost:6379/0")

    @app.route("/api/search")
    @require_auth
    @limiter.limit(requests=100, window=60)
    def search(): ...

    @app.route("/api/export")
    @require_auth
    @limiter.limit(requests=10, window=3600, by_plan={"pro": 100, "enterprise": 1000})
    def export(): ...
    """

    def __init__(self, redis_url: str | None = None) -> None:
        url = redis_url or os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        self._redis = self._connect(url)

    def _connect(self, url: str):
        try:
            import redis
            client = redis.from_url(url, decode_responses=True)
            client.ping()
            return client
        except Exception:
            return None  # Redis 未接続時はレート制限なし

    def _get_limit(self, base_requests: int, by_plan: dict[str, int] | None) -> int:
        if not by_plan:
            return base_requests
        plan = getattr(g, "user_plan", "free")
        return by_plan.get(plan, base_requests)

    def _check(self, key: str, limit: int, window: int) -> tuple[bool, int]:
        """スライディングウィンドウでリクエスト数をチェック。

        Returns:
            (allowed, remaining): 許可されたか、残りリクエスト数
        """
        if self._redis is None:
            return True, limit  # Redis なしはスキップ

        now = int(time.time())
        window_start = now - window
        # UUID を付与してメンバーを一意にする。
        # str(now) だけだと同一秒内の複数リクエストが同一メンバーとして上書きされ
        # カウントが抜け、レート制限が機能しなくなる。
        member = f"{now}:{uuid.uuid4().hex}"
        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zadd(key, {member: now})
        pipe.zcard(key)
        pipe.expire(key, window)
        _, _, count, _ = pipe.execute()

        allowed = count <= limit
        remaining = max(0, limit - count)
        return allowed, remaining

    def limit(
        self,
        requests: int,
        window: int = 60,
        by_plan: dict[str, int] | None = None,
    ) -> Callable:
        """レート制限デコレータ。

        Args:
            requests: ウィンドウ内の最大リクエスト数
            window:   ウィンドウ幅（秒）。デフォルト 60 秒
            by_plan:  プラン別リミット。{"pro": 200, "enterprise": 1000} 形式
        """
        def decorator(f: Callable) -> Callable:
            @wraps(f)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                raw_id = getattr(g, "user_id", None) or request.remote_addr or "unknown"
                # user_id にコロンや任意文字列が含まれても Redis キーが曖昧にならないようハッシュ化
                user_key = hashlib.sha256(str(raw_id).encode()).hexdigest()[:16]
                # f.__name__ だけだと別モジュールの同名関数とキーが衝突するため
                # __qualname__（クラス修飾付き名）と __module__ を組み合わせる
                func_key = f"{f.__module__}.{f.__qualname__}"
                key = f"ratelimit:{func_key}:{user_key}"
                effective_limit = self._get_limit(requests, by_plan)
                allowed, remaining = self._check(key, effective_limit, window)

                if not allowed:
                    return jsonify({
                        "error": "rate_limit_exceeded",
                        "message": "Too many requests. Please try again later.",
                        "retry_after": window,
                    }), 429

                response = f(*args, **kwargs)
                try:
                    resp = make_response(response)
                    resp.headers["X-RateLimit-Limit"] = str(effective_limit)
                    resp.headers["X-RateLimit-Remaining"] = str(remaining)
                    return resp
                except Exception:
                    return response

            return wrapper
        return decorator
