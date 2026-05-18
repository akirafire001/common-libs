from __future__ import annotations

from typing import Any, Callable, Type

from flask import Flask
from flask_login import LoginManager, UserMixin

from common.auth.user_model import BaseUser


class FlaskLoginUser(BaseUser, UserMixin):
    """BaseUser + Flask-Login UserMixin の統合抽象モデル。

    使用例::

        from common.flask_login import FlaskLoginUser

        class User(FlaskLoginUser):
            __tablename__ = "users"
            nickname: Mapped[str] = mapped_column(String(64), nullable=True)
    """

    __abstract__ = True

    def get_id(self) -> str:
        return str(self.id)


def init_login_manager(
    app: Flask,
    user_class: Type[FlaskLoginUser],
    db_session_factory: Callable[[], Any],
    login_view: str = "auth.login",
) -> LoginManager:
    """Flask-Login の LoginManager を初期化してアプリに登録する。

    Args:
        app: Flask アプリケーション
        user_class: FlaskLoginUser を継承したユーザーモデル
        db_session_factory: SQLAlchemy セッションを返す callable (例: lambda: db.session)
        login_view: 未認証時のリダイレクト先エンドポイント名

    Returns:
        設定済みの LoginManager インスタンス

    使用例::

        from common.flask_login import FlaskLoginUser, init_login_manager

        class User(FlaskLoginUser):
            __tablename__ = "users"

        login_manager = init_login_manager(app, User, lambda: db.session)
    """
    lm = LoginManager()
    lm.login_view = login_view
    lm.init_app(app)

    @lm.user_loader
    def load_user(user_id: str) -> FlaskLoginUser | None:
        session = db_session_factory()
        return session.get(user_class, user_id)

    return lm
