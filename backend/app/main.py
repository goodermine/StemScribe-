from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.health import router as health_router
from app.routes.jobs import router as jobs_router
from app.routes.preview import router as preview_router

app = FastAPI(title="StemScribe", description="Turn song stems into a sheet a musician can play from.")

# The Vite dev server runs on a different port, so the browser treats every
# call to this API as cross-origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(jobs_router)
app.include_router(preview_router)
