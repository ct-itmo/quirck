import importlib

from quirck.core import config

app = importlib.import_module(config.APP_MODULE)

__all__ = ["app"]
