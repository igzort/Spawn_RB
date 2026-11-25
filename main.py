import asyncio
import os
import sys
import threading
import time
import webbrowser
import secrets
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, HTTPException, Header, Body
from fastapi.responses import FileResponse


def get_base_path():
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


from config import DATABASE_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, SERVER_PASSWORD
from database import init_db, seed_initial_bosses, get_passwords, set_user_password
from worker import run_worker_loop, sync_cache_from_db, BOSSES_CACHE, set_boss_killed, reset_boss_timer


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_initial_bosses()
    asyncio.create_task(run_worker_loop())
    print("[SERVER] Воркер таймеров запущен!")
    yield


app = FastAPI(lifespan=lifespan)

_password_cache = {"user": None, "admin": None, "expires_at": 0.0}


def get_cached_passwords() -> tuple[str, str]:
    now = time.time()
    if (
        now < _password_cache["expires_at"]
        and _password_cache["user"] is not None
        and _password_cache["admin"] is not None
    ):
        return _password_cache["user"], _password_cache["admin"]
    user_pass, admin_pass = get_passwords()
    _password_cache["user"] = user_pass
    _password_cache["admin"] = admin_pass
    _password_cache["expires_at"] = now + 30
    return user_pass, admin_pass


def verify_password(x_server_password: str = Header(None)) -> str:
    if x_server_password is None:
        raise HTTPException(status_code=401, detail="Неверный пароль")
    user_pass, admin_pass = get_cached_passwords()
    if secrets.compare_digest(x_server_password, admin_pass):
        return "admin"
    if secrets.compare_digest(x_server_password, user_pass):
        return "user"
    # Сброс кэша при несовпадении: перечитаем пароли из БД и проверим ещё раз
    fresh_user, fresh_admin = get_passwords()
    if secrets.compare_digest(x_server_password, fresh_admin):
        _password_cache["user"] = fresh_user
        _password_cache["admin"] = fresh_admin
        _password_cache["expires_at"] = time.time() + 30
        return "admin"
    if secrets.compare_digest(x_server_password, fresh_user):
        _password_cache["user"] = fresh_user
        _password_cache["admin"] = fresh_admin
        _password_cache["expires_at"] = time.time() + 30
        return "user"
    raise HTTPException(status_code=401, detail="Неверный пароль")


@app.get("/")
async def root():
    return FileResponse(os.path.join(get_base_path(), "index.html"))


@app.get("/api/bosses")
async def get_bosses(_user: str = Depends(verify_password)):
    if not BOSSES_CACHE:
        sync_cache_from_db()
    bosses = sorted(BOSSES_CACHE.values(), key=lambda b: b["name"].lower())
    return bosses


@app.get("/api/me")
async def me(role: str = Depends(verify_password)):
    return {"role": role}


@app.post("/api/sync")
async def sync_bosses(_user: str = Depends(verify_password)):
    sync_cache_from_db()
    return sorted(BOSSES_CACHE.values(), key=lambda b: b["name"].lower())


@app.post("/api/bosses/{boss_id}/kill")
async def kill_boss(boss_id: int, request: Request, _user: str = Depends(verify_password)):
    body = await request.json()
    death_time = body.get("death_time") if body else None
    if death_time is None:
        death_time = time.time()
    set_boss_killed(boss_id, float(death_time))
    if not BOSSES_CACHE:
        sync_cache_from_db()
    bosses = sorted(BOSSES_CACHE.values(), key=lambda b: b["name"].lower())
    return bosses


@app.post("/api/bosses/{boss_id}/reset")
async def reset_boss(boss_id: int, _user: str = Depends(verify_password)):
    reset_boss_timer(boss_id)
    if not BOSSES_CACHE:
        sync_cache_from_db()
    bosses = sorted(BOSSES_CACHE.values(), key=lambda b: b["name"].lower())
    return bosses


@app.post("/api/change-password")
async def change_password(new_password: str = Body(...), role: str = Depends(verify_password)):
    if role != "admin":
        raise HTTPException(status_code=403, detail="Сменой пароля может только ПЛ")
    set_user_password(new_password)
    _password_cache["user"] = new_password
    _password_cache["expires_at"] = time.time() + 30
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    threading.Timer(2.0, lambda: webbrowser.open("http://localhost:8000")).start()
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")