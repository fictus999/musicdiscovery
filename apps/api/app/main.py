from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes import health, recommendations, search, songs


def create_app() -> FastAPI:
    app = FastAPI(title="Music Discovery API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(search.router)
    app.include_router(recommendations.router)
    app.include_router(songs.router)

    return app


app = create_app()
