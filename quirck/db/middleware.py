from sqlalchemy.ext.asyncio import async_sessionmaker
from starlette.types import ASGIApp, Message, Receive, Send, Scope

from .engine import get_engine, create_tables


class DatabaseMiddleware:
    def __init__(self, app: ASGIApp, url: str, create_tables: bool) -> None:
        self.app = app
        self.engine = get_engine(url)
        self.create_tables = create_tables
        self.factory = async_sessionmaker(self.engine, expire_on_commit=False)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        match scope["type"]:
            case "lifespan":
                async def receive_processed() -> Message:
                    message = await receive()
                    match message["type"]:
                        case "lifespan.shutdown":
                            await self.engine.dispose()

                        case "lifespan.startup":
                            if self.create_tables:
                                await create_tables(self.engine)
                    
                    return message

                return await self.app(scope, receive_processed, send)
            case "http" | "websocket":
                async with self.factory() as session:
                    scope["db"] = session

                    async def commit_then_send(message: Message) -> None:
                        # We commit transaction before sending the headers to ensure user
                        # cannot send consequent request before transaction is committed.
                        if message["type"] == "http.response.start":
                            await session.commit()

                        return await send(message)

                    try:
                        await self.app(scope, receive, commit_then_send)
                    except:
                        await session.rollback()
                        raise
                return
            case _:
                # Should not happen, but just in case.
                return await self.app(scope, receive, send)


__all__ = ["DatabaseMiddleware"]
