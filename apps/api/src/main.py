from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.core import get_settings, limiter
from src.routers import ROUTERS


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield


app = FastAPI(
    title="CONXA API",
    description="Trust-weighted, AI-structured search for people by experience.",
    version="0.1.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_api_root = Path(__file__).resolve().parents[1]  # apps/api/
_img_dir = _api_root / "img"
if _img_dir.exists():
    app.mount("/img", StaticFiles(directory=str(_img_dir)), name="img")

for router in ROUTERS:
    app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok"}


