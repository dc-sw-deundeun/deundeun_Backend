from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.exceptions import register_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    # DB engine 초기화는 DB 확정 후 여기에 추가합니다.
    yield
    # 종료 시 cleanup 로직을 여기에 추가합니다.


app = FastAPI(
    title="deundeun API",
    version="0.1.0",
    lifespan=lifespan,
)

register_exception_handlers(app)


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}


from app.api.v1.router import api_router  # noqa: E402

app.include_router(api_router)
