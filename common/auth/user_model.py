import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class BaseUser(Base):
    """メール認証・Google認証に対応したユーザーの基底モデル。

    各プロジェクトでこのクラスを継承し、プロジェクト固有のカラムを追加する。

    使用例::

        from common.auth import BaseUser

        class User(BaseUser):
            __tablename__ = "users"
            nickname: Mapped[str] = mapped_column(String(64), nullable=True)
    """

    __abstract__ = True

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)

    # Google認証用。メール認証のみのユーザーはNULL
    google_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)

    # メール認証用。Google認証のみのユーザーはNULL
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"
