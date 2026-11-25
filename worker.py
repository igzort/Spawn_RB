import asyncio
import time

from database import SessionLocal, Boss
from telegram_bot import send_tg_message

BOSSES_CACHE: dict[int, dict] = {}


def sync_cache_from_db():
    db = SessionLocal()
    try:
        bosses = db.query(Boss).all()
        BOSSES_CACHE.clear()
        for b in bosses:
            BOSSES_CACHE[b.id] = {
                "id": b.id,
                "name": b.name,
                "respawn_min": b.respawn_min,
                "respawn_max": b.respawn_max,
                "death_time": b.death_time,
                "status": b.status,
            }
        return bosses
    finally:
        db.close()


def set_boss_killed(boss_id: int, death_timestamp: float):
    db = SessionLocal()
    try:
        db.query(Boss).filter(Boss.id == boss_id).update(
            {"death_time": death_timestamp, "status": "waiting"}
        )
        db.commit()
    finally:
        db.close()
    sync_cache_from_db()


def check_timers_in_memory():
    now = time.time()
    for boss_id, boss in list(BOSSES_CACHE.items()):
        death_time = boss["death_time"]
        if death_time is None:
            continue
        if boss["status"] not in ("waiting", "window_open"):
            continue

        window_start = death_time + boss["respawn_min"] * 60
        window_end = death_time + boss["respawn_max"] * 60

        if boss["status"] == "waiting" and now >= window_start:
            new_status = "spawned" if now >= window_end else "window_open"
            db = SessionLocal()
            try:
                result = db.query(Boss).filter(
                    Boss.id == boss_id, Boss.status == "waiting"
                ).update({"status": new_status})
                db.commit()
            finally:
                db.close()
            if result == 1:
                if new_status == "spawned":
                    send_tg_message(f"🔴 <b>СТОИТ: {boss['name']}!</b>")
                else:
                    send_tg_message(f"🟡 <b>РЕСП ПОШЕЛ: {boss['name']}!</b>")
                sync_cache_from_db()

        elif boss["status"] == "window_open" and now >= window_end:
            db = SessionLocal()
            try:
                result = db.query(Boss).filter(
                    Boss.id == boss_id, Boss.status == "window_open"
                ).update({"status": "spawned"})
                db.commit()
            finally:
                db.close()
            if result == 1:
                send_tg_message(f"🔴 <b>СТОИТ: {boss['name']}!</b>")
                sync_cache_from_db()


async def run_worker_loop():
    sync_cache_from_db()
    while True:
        try:
            check_timers_in_memory()
        except Exception as e:
            print(e)
        await asyncio.sleep(15)