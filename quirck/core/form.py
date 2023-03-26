import re

from markupsafe import Markup, escape
from starlette_wtf import StarletteForm
from wtforms import StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired
from wtforms.widgets import TextArea


class QuirckForm(StarletteForm):
    submit = SubmitField("Отправить")

    class Meta:
        locales = ["ru_RU", "ru"]


class AceEditorWidget(TextArea):
    def __call__(self, field, **kwargs):
        textarea_markup = super().__call__(field, **kwargs)
        kwargs.setdefault('id', field.id)
        return Markup(
            f"""<div id="{kwargs['id']}_ace" class="ace">{escape(field._value())}</div>"""
        ) + textarea_markup


class AceEditorField(TextAreaField):
    widget = AceEditorWidget()


class BaseTaskForm(QuirckForm):
    async def check(self) -> bool:
        raise NotImplementedError(f"{self.__class__.__name__} does not implement check()")

    @classmethod
    def make_task(cls, slug: str, **kwargs) -> type["BaseTaskForm"]:
        return type(slug, (cls, ), kwargs)


class RegexpForm(BaseTaskForm):
    value = StringField(label="", validators=[DataRequired()])
    answer: re.Pattern

    async def check(self) -> bool:
        return self.answer.fullmatch(self.value.data.strip()) is not None


__all__ = ["QuirckForm", "BaseTaskForm", "RegexpForm", "AceEditorField"]
