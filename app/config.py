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
    log_level: str

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
        return cls(
            bot_token=bot_token,
            project_dir=project_dir,
            assets_dir=assets_dir,
            log_level=log_level,
        )
