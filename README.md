# Belarus Events Harvester

Запуск:
1) python -m venv .venv && source .venv/bin/activate
2) pip install -r requirements.txt
3) cp .env.example .env (при необходимости)
4) python -m src.runner --sources relax --limit 50 --out outputs/events.jsonl
# 1
