from uvicorn.workers import UvicornWorker

from quirck.core.config import ROOT_PATH


class QuirckWorker(UvicornWorker):
    CONFIG_KWARGS = {
        "root_path": ROOT_PATH,
        "forwarded_allow_ips": "*",
        "proxy_headers": True,
        "lifespan": "on",
        "log_config": {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s [%(levelname)s] %(message)s"
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "stream": "ext://sys.stdout"
                }
            },
            "loggers": {
                "uvicorn": {
                    "error": {
                        "propagate": True
                    }
                }
            },
            "root": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False
            }
        }
    }
