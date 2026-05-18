import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from common.auth.user_model import Base


class ApiKey(Base):
    """APIキーモデル。

    ApiKey は common.auth.user_model.Base と同じメタデータに属するため、
    Base.metadata.create_all(engine) で一括作成できる。

    使用例::

        from common.apikey import ApiKey, generate_api_key
        from common.auth.user_model import Base

        Base.metadata.create_all(engine)

        raw_key, api_key = generate_api_key(user_id="...", name="My App")
        db.session.add(api_key)
        db.session.commit()
        # raw_key をユーザーに一度だけ表示する
    """

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # 先頭12文字のみ保存（管理画面等での表示用）
    key_prefix: Mapped[str] = mapped_column(String(12), nullable=False)
    # SHA-256 ハッシュ値（生のキーはDBに保存しない）
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<ApiKey id={self.id} prefix={self.key_prefix} user_id={self.user_id}>"
