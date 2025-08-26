# app/__init__.py
from fastapi import FastAPI
from .config import setup_cors

# Router erst NACH dem App-Objekt importieren vermeidet Zirkularimporte
from .ui import router as ui_router
from .guests import router as guests_router
from .api import router as api_router


def create_app() -> FastAPI:
    app = FastAPI(title="Printer API")
    setup_cors(app)
    app.include_router(ui_router)
    app.include_router(guests_router)
    app.include_router(api_router)
    return app
