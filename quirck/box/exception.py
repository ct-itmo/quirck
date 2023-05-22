from starlette.exceptions import HTTPException


class DockerConflict(HTTPException):
    def __init__(self):
        super().__init__(409, f"Сейчас происходит операция с другим заданием: запустить проверку или задание невозможно")


__all__ = ["DockerConflict"]
