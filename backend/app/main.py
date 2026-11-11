import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.database import Base, SessionLocal, engine
from app.routers import auth, inventory, places, sets
from app.seed import seed

import app.models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    last_error = None
    for _ in range(30):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            last_error = None
            break
        except Exception as exc:
            last_error = exc
            time.sleep(1)
    if last_error is not None:
        raise RuntimeError("Database did not become ready") from last_error
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed(db)
    yield


app = FastAPI(title="Home Textile Inventory", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(inventory.router)
app.include_router(places.router)
app.include_router(sets.router)

static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def index():
    return FileResponse(static_dir / "index.html")


@app.get("/api/health")
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database is unavailable") from exc
    return {"status": "ok"}
