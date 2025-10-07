# Belarus Events Harvester (minsk-vitebsk)

Сборщик карточек событий (Минск, Витебск) из официальных и тикетинговых источников. Выгрузка в JSONL.

Запуск:
1) python -m venv .venv && source .venv/bin/activate
2) pip install -r requirements.txt
3) cp .env.example .env (при необходимости)
4) python -m src.runner --sources relax,minsktourism,belarus.by,vitebsk.biz --limit 50 --no-geocode --out outputs/events.jsonl
