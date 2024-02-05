from markupsafe import Markup, escape
from starlette_wtf import StarletteForm
from wtforms import SubmitField, TextAreaField
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


__all__ = ["QuirckForm", "AceEditorField"]
