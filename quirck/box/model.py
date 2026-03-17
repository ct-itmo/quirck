from datetime import datetime
import enum
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Sequence,
    text,
)
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

    port: Mapped[int] = mapped_column(
        BigInteger, ports, primary_key=True, server_default=ports.next_value()
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    chapter: Mapped[str | None] = mapped_column(String(40), nullable=True)
    state: Mapped[DockerState] = mapped_column(Enum(DockerState), nullable=False)
    vpn: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    user = relationship("User", back_populates="docker_meta")
    client_stats = relationship("DockerClientStats", back_populates="docker_meta")


class DockerClientStats(Base):
    __tablename__ = "docker_client_stats"
    __table_args__ = (
        Index("docker_client_stats_client", "docker_id", "client_ip", "connected_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    docker_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("docker.port", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    client_ip: Mapped[str] = mapped_column(String(64), nullable=False)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    bytes_recv: Mapped[int] = mapped_column(BigInteger, nullable=False)
    bytes_sent: Mapped[int] = mapped_column(BigInteger, nullable=False)

    docker_meta = relationship("DockerMeta", back_populates="client_stats")


User.docker_meta = relationship("DockerMeta", back_populates="user", uselist=False)


__all__ = ["DockerState", "DockerMeta", "DockerClientStats"]
