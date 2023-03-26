import enum
from typing import Any

from sqlalchemy import BigInteger, Enum, ForeignKey, String, Sequence
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quirck.auth.model import User
from quirck.db.base import Base


class DockerState(enum.Enum):
    IN_PROGRESS = 1
    READY = 2
    DISABLED = 3


class DockerMeta(Base):
    __tablename__ = "docker"

    ports = Sequence("docker_state_port_seq", start=31601)

    port: Mapped[int] = mapped_column(BigInteger, ports, primary_key=True, server_default=ports.next_value())
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )
    # loads package networking.$chapter.docker, null for disabled
    chapter: Mapped[str | None] = mapped_column(String(40), nullable=True)
    state: Mapped[DockerState] = mapped_column(Enum(DockerState), nullable=False)
    vpn: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    user = relationship("User", back_populates="docker_meta")

User.docker_meta = relationship("DockerMeta", back_populates="user", uselist=False)


__all__ = ["DockerState", "DockerMeta"]
