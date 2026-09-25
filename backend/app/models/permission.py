from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Permission(Base):
    __tablename__ = "permissions"
    __table_args__ = (UniqueConstraint("user_id", "capability", name="uq_permission_user_capability"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    capability: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    mode: Mapped[str] = mapped_column(String(20), default="ask", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
