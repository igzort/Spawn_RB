from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from config import DATABASE_URL, SERVER_PASSWORD
from bosses_data import LU4_BOSSES

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Boss(Base):
    __tablename__ = "bosses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    respawn_min = Column(Float, nullable=False)
    respawn_max = Column(Float, nullable=False)
    death_time = Column(Float, nullable=True)
    status = Column(String, default="idle")


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True, index=True)
    value = Column(String, nullable=False)


def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        setting = db.query(Setting).filter(Setting.key == "server_password").first()
        if not setting:
            db.add(Setting(key="server_password", value="lu4password"))
        setting = db.query(Setting).filter(Setting.key == "admin_password").first()
        if not setting:
            db.add(Setting(key="admin_password", value="fortheemperor"))
        db.commit()
    finally:
        db.close()


def seed_initial_bosses():
    db = SessionLocal()
    try:
        for name, base, var in LU4_BOSSES:
            r_min = (base - var) * 60
            r_max = (base + var) * 60
            base_name = name.split(",")[0].strip() if "," in name else name

            # Если запись с новым именем уже существует — просто обновляем время респавна
            boss = db.query(Boss).filter(Boss.name == name).first()
            if boss:
                boss.respawn_min = r_min
                boss.respawn_max = r_max
                continue

            # Иначе ищем запись по базовому имени и переименовываем её, сохраняя death_time и status
            boss = db.query(Boss).filter(Boss.name == base_name).first()
            if boss:
                boss.name = name
                boss.respawn_min = r_min
                boss.respawn_max = r_max
            else:
                db.add(Boss(name=name, respawn_min=r_min, respawn_max=r_max))

        tester = db.query(Boss).filter(Boss.name == "TESTER_RB").first()
        if not tester:
            db.add(Boss(name="TESTER_RB", respawn_min=10 / 60, respawn_max=20 / 60))
        db.commit()
    finally:
        db.close()


def get_passwords() -> tuple[str, str]:
    db = SessionLocal()
    try:
        user_setting = db.query(Setting).filter(Setting.key == "server_password").first()
        admin_setting = db.query(Setting).filter(Setting.key == "admin_password").first()
        return (
            user_setting.value if user_setting else "lu4password",
            admin_setting.value if admin_setting else "fortheemperor",
        )
    finally:
        db.close()


def set_user_password(new_pass: str):
    db = SessionLocal()
    try:
        setting = db.query(Setting).filter(Setting.key == "server_password").first()
        if setting:
            setting.value = new_pass
        else:
            db.add(Setting(key="server_password", value=new_pass))
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    seed_initial_bosses()
    print("DB initialized successfully!")