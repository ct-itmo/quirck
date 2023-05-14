from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from wtforms.fields import IntegerField, SubmitField
from wtforms.validators import InputRequired, ValidationError

from quirck.auth.model import User
from quirck.core.form import QuirckForm

class ImpersonateForm(QuirckForm):
    user_id = IntegerField("ID пользователя", validators=[InputRequired()])
    submit = SubmitField("Войти")

    async def async_validate_user_id(self, field: IntegerField) -> None:
        session: AsyncSession = self._request.scope["db"]

        target_user = (await session.scalars(select(User).where(User.id == field.data))).one_or_none()
        
        if target_user is None:
            raise ValidationError("Пользователь не найден")

        if target_user.is_admin:
            raise ValidationError("Аккаунт принадлежит администратору")


__all__ = ["ImpersonateForm"]
