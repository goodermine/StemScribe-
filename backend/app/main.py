from fastapi import FastAPI

from app.routes.health import router as health_router
from app.routes.jobs import router as jobs_router
from app.routes.preview import router as preview_router

app = FastAPI(title="suno-stems-to-notes")
app.include_router(health_router)
app.include_router(jobs_router)
app.include_router(preview_router)
