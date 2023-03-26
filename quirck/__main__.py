import uvicorn

from quirck.core import config
from quirck.web.worker import QuirckWorker


if __name__ == "__main__":
    uvicorn.run(
        "quirck.web.app:build_app",
        factory=True,
        port=config.PORT,
        **QuirckWorker.CONFIG_KWARGS,
        reload=config.DEBUG
    )
