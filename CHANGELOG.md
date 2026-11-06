# Changelog

Все значимые изменения проекта фиксируются в этом файле.
Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/), версионирование — [SemVer](https://semver.org/lang/ru/).
Правила ведения описаны в [AGENTS.md](AGENTS.md).

## [Unreleased]

### Added
- В архитектуру добавлены интерфейс источников данных `GameSource` (Metacritic сейчас, Steam позже), SQLAlchemy и Pydantic; в схему БД — `games.source` и `sync_runs.batch_index`
- Каркас `backend/` (pyproject, `.env.example`, конфиг) и `frontend/`
- Источник данных Metacritic (`backend/app/sources/`): интерфейс `GameSource`, HTTP-клиент с паузами и повторами, парсеры списков и страницы игры, `MetacriticSource` с тестами на сохранённом HTML
- Цикл синхронизации `run_cycle` (`backend/app/services/sync.py`): выбор пачки по журналу запусков, пропуск обработанных сегодня, учёт сбоев отдельных игр, защита от параллельного запуска, тесты на заглушке источника
- Слой БД (`backend/app/db/`): модели SQLAlchemy, сессии, репозиторий (`save_game`, история метрик, журнал запусков) с тестами
- Описание задания (`TASK.md`) и первоначальная архитектура (`docs/ARCHITECTURE.md`)
- `AGENTS.md` с правилами для агентов, правилом «сначала архитектура, потом код» и правилами ведения CHANGELOG
- `docs/REQUIREMENTS.md` со структурированными требованиями
- Схема БД вынесена в `docs/DATABASE.md`: игры, жанры, платформы, история метрик, версии резюме, журнал запусков `sync_runs`
- В архитектуру добавлены структура проекта (backend/frontend) и результаты анализа HTML Metacritic: источники данных списков и страницы игры
- Пачка за запуск — ровно 20 игр, номер пачки за день хранится как `batch_index` в `sync_runs`
- В архитектуру добавлены стек (FastAPI, APScheduler), запуск по расписанию, выбор пачки игр и обнаружение изменений по хэшу
