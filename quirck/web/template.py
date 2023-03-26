import typing

import jinja2

from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import Receive, Send, Scope

EXPOSED_SCOPE_FIELDS = ["user"]

template_env = jinja2.Environment(autoescape=True)


@jinja2.pass_context
def url_for(context: dict[str, typing.Any], name: str, **path_params: typing.Any) -> str:
    request: Request = context["request"]
    return request.url_for(name, **path_params)


def ru_ending_filter(num, one, two, five):
    if 11 <= num % 100 <= 19:
        return five
    if num % 10 == 1:
        return one
    if 2 <= num % 10 <= 4:
        return two
    return five


def jinja_getattr(obj, attr):
    result = getattr(obj, attr, None)
    if result is not None:
        return result

    try:
        return obj.__getitem__(attr)
    except KeyError:
        return None


def mapattr_filter(objects, *attributes):
    if len(attributes) == 0:
        return list(objects)

    return mapattr_filter(map(
        lambda obj: jinja_getattr(obj, attributes[0]),
        objects
    ), *attributes[1:])



template_env.globals["url_for"] = url_for
template_env.filters["ending"] = ru_ending_filter
template_env.filters["mapattr"] = mapattr_filter


class TemplateResponse(Response):
    media_type = "text/html"

    def __init__(
        self,
        request: Request,
        template_name: str,
        context: dict[str, typing.Any] = {},
        status_code: int = 200,
        headers: typing.Mapping[str, str] | None = None,
        media_type: str | None = None,
        background: BackgroundTask | None = None,
    ):
        if template_env.loader is None:
            from quirck.core.module import app
            template_env.loader = jinja2.FileSystemLoader(app.template_path)

        self.template = template_env.get_template(template_name)
        self.context = dict(
            **context,
            request=request
        )

        for field in EXPOSED_SCOPE_FIELDS:
            if field in request.scope:
                self.context[field] = request.scope[field]

        content = self.template.render(self.context)
        super().__init__(content, status_code, headers, media_type, background)
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await super().__call__(scope, receive, send)


__all__ = ["TemplateResponse"]
