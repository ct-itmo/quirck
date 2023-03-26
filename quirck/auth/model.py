from sqlalchemy import (
    BigInteger, Boolean, String,
    text
)
from sqlalchemy.orm import Mapped, mapped_column

from quirck.db.base import Base


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    group: Mapped[str | None] = mapped_column(String(8), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)


__all__ = ["User"]
