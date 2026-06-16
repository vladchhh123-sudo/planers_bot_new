#!/bin/bash
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

if [ ! -d ".venv" ]; then
  echo "[setup] Создаю виртуальное окружение..."
  python3 -m venv .venv || exit 1
fi

source .venv/bin/activate

python -m pip install --upgrade pip || exit 1
python -m pip install -r requirements.txt || exit 1

if [ -f ".env" ]; then
  set -a
  source .env
  set +a
fi

if [ -z "${BOT_TOKEN:-}" ]; then
  echo "[error] BOT_TOKEN не найден. Создай файл .env на основе .env.example"
  exit 1
fi

mkdir -p logs

echo "[info] Бот будет перезапускаться автоматически при любом падении."
while true; do
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] старт бота" | tee -a logs/bot.log
  python -m app.main 2>&1 | tee -a logs/bot.log
  exit_code=${PIPESTATUS[0]}
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] бот завершился с кодом ${exit_code}, перезапуск через 5 секунд" | tee -a logs/bot.log
  sleep 5
done
c