import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.limiter import limiter
from src.routers import auth_router, me_router, contact_router, builder_router, search_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # shutdown if needed


app = FastAPI(
    title="Search Engine API",
    description="Trust-weighted, AI-structured search for people by experience.",
    version="0.1.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(me_router)
app.include_router(contact_router)
app.include_router(builder_router)
app.include_router(search_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


