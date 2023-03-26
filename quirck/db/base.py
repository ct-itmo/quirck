from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    __mapper_args__ = {
        "eager_defaults": True
    }


__all__ = ["Base"]
