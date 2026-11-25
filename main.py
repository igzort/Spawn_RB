import asyncio
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi import Request

from database import init_db, seed_initial_bosses
from worker import run_worker_loop, sync_cache_from_db, BOSSES_CACHE, set_boss_killed


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_initial_bosses()
    asyncio.create_task(run_worker_loop())
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def root():
    return FileResponse("index.html")


@app.get("/api/bosses")
async def get_bosses():
    if not BOSSES_CACHE:
        sync_cache_from_db()
    bosses = sorted(BOSSES_CACHE.values(), key=lambda b: b["name"].lower())
    return bosses


@app.post("/api/sync")
async def sync_bosses():
    bosses = sync_cache_from_db()
    return sorted(bosses, key=lambda b: b["name"].lower())


@app.post("/api/bosses/{boss_id}/kill")
async def kill_boss(boss_id: int, request: Request):
    body = await request.json()
    death_time = body.get("death_time") if body else None
    if death_time is None:
        death_time = time.time()
    set_boss_killed(boss_id, float(death_time))
    if not BOSSES_CACHE:
        sync_cache_from_db()
    bosses = sorted(BOSSES_CACHE.values(), key=lambda b: b["name"].lower())
    return bosses


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)