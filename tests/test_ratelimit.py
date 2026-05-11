import pytest
from unittest.mock import MagicMock
from flask import Flask, g, jsonify

from common.ratelimit import RateLimiter


def _make_mock_redis(count: int = 1):
    """指定したカウントを返す Redis パイプラインのモックを作る。"""
    pipeline = MagicMock()
    pipeline.execute.return_value = [None, None, count, None]
    client = MagicMock()
    client.pipeline.return_value = pipeline
    return client


def _make_limiter(mock_redis=None) -> RateLimiter:
    """_redis を直接差し込んだ RateLimiter を返す。"""
    limiter = RateLimiter.__new__(RateLimiter)
    limiter._redis = mock_redis
    return limiter


def _make_app(limiter: RateLimiter, limit_kwargs: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = True
    kwargs = limit_kwargs or {"requests": 10, "window": 60}

    @app.route("/search")
    @limiter.limit(**kwargs)
    def search():
        return jsonify({"result": "ok"})

    return app


class TestRateLimiterNoRedis:
    def test_no_redis_always_allows(self):
        """Redis が None のときはレート制限なしで通過する。"""
        limiter = _make_limiter(mock_redis=None)
        app = _make_app(limiter)

        with app.test_client() as c:
            for _ in range(20):
                resp = c.get("/search")
                assert resp.status_code == 200


class TestRateLimiterWithRedis:
    def test_under_limit_returns_200(self):
        mock_redis = _make_mock_redis(count=5)  # 5 リクエスト、制限は 10
        limiter = _make_limiter(mock_redis)
        app = _make_app(limiter, {"requests": 10, "window": 60})

        with app.test_client() as c:
            resp = c.get("/search")

        assert resp.status_code == 200

    def test_rate_limit_headers_set(self):
        mock_redis = _make_mock_redis(count=3)
        limiter = _make_limiter(mock_redis)
        app = _make_app(limiter, {"requests": 10, "window": 60})

        with app.test_client() as c:
            resp = c.get("/search")

        assert resp.headers.get("X-RateLimit-Limit") == "10"
        # remaining = max(0, 10 - 3) = 7
        assert resp.headers.get("X-RateLimit-Remaining") == "7"

    def test_over_limit_returns_429(self):
        mock_redis = _make_mock_redis(count=11)  # 制限 10 を超過
        limiter = _make_limiter(mock_redis)
        app = _make_app(limiter, {"requests": 10, "window": 60})

        with app.test_client() as c:
            resp = c.get("/search")

        assert resp.status_code == 429
        data = resp.get_json()
        assert data["error"] == "rate_limit_exceeded"
        assert data["retry_after"] == 60

    def test_remaining_never_goes_negative(self):
        mock_redis = _make_mock_redis(count=100)  # 大幅超過
        limiter = _make_limiter(mock_redis)
        app = _make_app(limiter, {"requests": 10, "window": 60})

        # 429 のレスポンスでもヘッダは付かない（制限前にチェックで早期リターン）
        with app.test_client() as c:
            resp = c.get("/search")
        assert resp.status_code == 429

    def test_redis_pipeline_called_correctly(self):
        mock_redis = _make_mock_redis(count=1)
        limiter = _make_limiter(mock_redis)
        app = _make_app(limiter, {"requests": 10, "window": 60})

        with app.test_client() as c:
            c.get("/search")

        mock_redis.pipeline.assert_called_once()
        pipeline = mock_redis.pipeline.return_value
        pipeline.execute.assert_called_once()


class TestRateLimiterByPlan:
    def test_by_plan_uses_plan_limit(self):
        """pro プランは by_plan で指定した上限を使う。"""
        mock_redis = _make_mock_redis(count=50)  # base=10 超、pro=100 以内
        limiter = _make_limiter(mock_redis)

        app = Flask(__name__)
        app.config["TESTING"] = True

        @app.before_request
        def set_plan():
            g.user_plan = "pro"
            g.user_id = "user_42"

        @app.route("/export")
        @limiter.limit(requests=10, window=60, by_plan={"pro": 100, "enterprise": 500})
        def export():
            return jsonify({"ok": True})

        with app.test_client() as c:
            resp = c.get("/export")

        assert resp.status_code == 200
        # ヘッダのリミットが pro の 100 になっている
        assert resp.headers.get("X-RateLimit-Limit") == "100"

    def test_by_plan_unknown_plan_uses_base(self):
        """定義外のプランは base_requests を使う。"""
        mock_redis = _make_mock_redis(count=5)
        limiter = _make_limiter(mock_redis)

        app = Flask(__name__)
        app.config["TESTING"] = True

        @app.before_request
        def set_plan():
            g.user_plan = "vip"   # by_plan に存在しない
            g.user_id = "user_1"

        @app.route("/api")
        @limiter.limit(requests=20, window=60, by_plan={"pro": 100})
        def api():
            return jsonify({"ok": True})

        with app.test_client() as c:
            resp = c.get("/api")

        assert resp.headers.get("X-RateLimit-Limit") == "20"


class TestRateLimiterInit:
    def test_no_redis_when_unreachable(self, monkeypatch):
        """接続できない Redis URL を渡したとき _redis は None になる。"""
        monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:19999/0")
        limiter = RateLimiter()
        # 接続失敗 → _redis は None → レート制限なし
        assert limiter._redis is None
