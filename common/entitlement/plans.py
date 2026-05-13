from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import g, jsonify


PLAN_LEVELS: dict[str, int] = {
    "free": 0,
    "starter": 1,
    "pro": 2,
    "enterprise": 3,
}


def _get_user_plan() -> str:
    """現在のリクエストユーザーのプランを取得する。

    デフォルト実装は g.user_plan を参照する。
    アプリ側で before_request フックなどでセットしておく。
    カスタム実装が必要な場合は set_plan_loader() で差し替え可能。
    """
    return getattr(g, "user_plan", "free")


_plan_loader: Callable[[], str] = _get_user_plan


def set_plan_loader(loader: Callable[[], str]) -> None:
    """プラン取得関数を差し替える。

    例: DB からプランを取得したい場合
        from common.entitlement.plans import set_plan_loader

        def my_loader():
            user = db.session.get(User, g.user_id)
            return user.plan if user else "free"

        set_plan_loader(my_loader)
    """
    global _plan_loader
    _plan_loader = loader


def require_plan(minimum_plan: str) -> Callable:
    """指定プラン以上のユーザーのみアクセスを許可するデコレータ。

    @app.route("/api/export")
    @require_auth              # まず認証
    @require_plan("pro")       # 次にプランチェック
    def export():
        ...

    プランが不足している場合は 403 を返す。
    存在しないプラン名を渡すと ValueError を送出する（デコレート時に早期検出）。
    """
    if minimum_plan not in PLAN_LEVELS:
        raise ValueError(
            f"Unknown plan: '{minimum_plan}'. Valid plans: {list(PLAN_LEVELS)}"
        )
    required_level = PLAN_LEVELS[minimum_plan]

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_plan = _plan_loader()
            current_level = PLAN_LEVELS.get(current_plan, 0)
            if current_level < required_level:
                return jsonify({
                    "error": "plan_required",
                    "message": f"This feature requires the '{minimum_plan}' plan or higher.",
                    "required_plan": minimum_plan,
                    "current_plan": current_plan,
                }), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator


def has_plan(minimum_plan: str) -> bool:
    """現在のユーザーが指定プラン以上かどうかを返す（非デコレータ版）。

    テンプレートや条件分岐で使う場合:
        if has_plan("pro"):
            ...

    存在しないプラン名を渡すと ValueError を送出する。
    PLAN_LEVELS.get(..., 0) のデフォルトに頼ると、タイポのプラン名が
    required_level=0 になり全ユーザーに True を返すため明示的に検証する。
    """
    if minimum_plan not in PLAN_LEVELS:
        raise ValueError(
            f"Unknown plan: '{minimum_plan}'. Valid plans: {list(PLAN_LEVELS)}"
        )
    required_level = PLAN_LEVELS[minimum_plan]
    current_level = PLAN_LEVELS.get(_plan_loader(), 0)
    return current_level >= required_level
