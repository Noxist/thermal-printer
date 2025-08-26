from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .mqtt_client import mqtt_start, mqtt_stop
from .routes.api import router as api_router
from .routes.ui import router as ui_router
from .routes.guests import router as guests_router

def create_app() -> FastAPI:
    app = FastAPI(title="Printer API")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.include_router(api_router)
    app.include_router(ui_router)
    app.include_router(guests_router)

    @app.on_event("startup")
    async def _startup(): mqtt_start()

    @app.on_event("shutdown")
    async def _shutdown(): mqtt_stop()
    return app
