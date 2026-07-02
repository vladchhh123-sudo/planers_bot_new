from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    bot_token: str
    project_dir: Path
    assets_dir: Path
    data_dir: Path
    analytics_db_path: Path
    log_level: str
    admin_password: str | None

    @classmethod
    def load(cls) -> "Config":
        project_dir = Path(__file__).resolve().parent.parent
        env_path = project_dir / ".env"
        if env_path.exists():
            load_dotenv(env_path)
        else:
            load_dotenv()

        bot_token = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            raise RuntimeError("Не найден BOT_TOKEN. Добавь токен в .env или в переменные окружения.")

        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        assets_dir = project_dir / "assets"

        data_dir = Path(os.getenv("DATA_DIR", str(project_dir / "data"))).resolve()
        data_dir.mkdir(parents=True, exist_ok=True)

        analytics_db_path = Path(
            os.getenv("ANALYTICS_DB_PATH", str(data_dir / "analytics.sqlite3"))
        ).resolve()

        admin_password = os.getenv("ADMIN_PASSWORD") or None

        return cls(
            bot_token=bot_token,
            project_dir=project_dir,
            assets_dir=assets_dir,
            data_dir=data_dir,
            analytics_db_path=analytics_db_path,
            log_level=log_level,
            admin_password=admin_password,
        )
