# TickFeedDmr

Сервис приёма рыночных данных (крипта Binance, акции MOEX, курсы ЦБ РФ) с REST/SSE API, React-фронтендом и ИИ-аналитиком рынка. Django 6.0, Python 3.14, зависимости через `uv`.

## Общая схема

```mermaid
flowchart LR
    BIN[Binance WS] -->|1| BS[binance_stream] -->|2| RS[(Redis Streams)]
    RS -->|3| MC[market_data_consumer] -->|4| PG[(Postgres)]
    ISS[MOEX ISS] -->|5| CW[Celery worker]
    CBR[ЦБ РФ] -->|5| CW
    CW -->|6| PG
    CW -->|6| RS
    PG -->|7| API[Django API]
    RS -->|7. SSE| API
    API <-->|8| UI[React SPA]
    API <-->|9| AI[ИИ-чат + LLM]
```

**Что за чем:**

1. Binance присылает сделки по WebSocket, их принимает `binance_stream`.
2. `binance_stream` кладёт сделки в Redis Stream.
3. `market_data_consumer` читает стрим.
4. Консьюмер пишет сделки в Postgres.
5. Параллельно Celery worker по расписанию опрашивает MOEX и ЦБ.
6. Результат опроса пишется в Postgres, а свежие сделки акций ещё и в Redis Stream.
7. Django API отдаёт данные из Postgres, а живые сделки — из Redis Stream по SSE.
8. Фронтенд (React) ходит в API за данными и потоками.
9. ИИ-чат обращается через API к LLM и к данным.

Push-источники (Binance WebSocket) работают как долгоживущие management-команды, источники, которые нужно опрашивать по расписанию (MOEX, ЦБ), — как Celery-задачи.

## Как это выглядит

Скриншоты сняты на локальном стеке (`docker compose -f docker-compose.local.yml up -d`) в тёмной теме; тему можно переключить кнопками справа вверху (светлая / тёмная / системная).

### Крипта: живая лента сделок

![Крипта: график и лента сделок](docs/screenshots/crypto-live.jpg)

Страница «Крипта» показывает один инструмент (BTC, ETH, SOL, XRP — выбор в списке слева вверху).

- **Бейдж «в реальном времени»** (зелёный) — данные приходят в реальном времени (молния). Для источников с задержкой вместо него серый бейдж с часами и временем задержки; если данные отстали сильнее заявленного, бейдж меняет цвет, а в подсказке при наведении об этом сказано.
- **Бейдж «поток открыт»** — открыто SSE-соединение, сделки приходят по мере появления на бирже.
- **Лента сделок** под графиком: зелёная строка со стрелкой вверх — покупка, красная со стрелкой вниз — продажа; цвет всегда продублирован стрелкой. В строке время, цена и объём.
- **«24 часа»** — внутридневной график, который дорисовывается живыми сделками; **«История»** — дневные свечи с интервалами 1М / 6М / 1Г / Всё.

![Крипта: история цены](docs/screenshots/crypto-history.jpg)

### Акции: выбор бумаг и сравнение

Кнопка **«Сравнить»** переключает страницу в режим сравнения: выбранные бумаги показаны чипами с цветной точкой — тем же цветом рисуется её линия на графике, а кнопка **«Добавить»** открывает список с поиском по тикеру и названию (до шести бумаг сразу).

![Акции: сравнение ABIO, ABRD, AFLT, AIIQ, AKAI](docs/screenshots/stocks-compare.jpg)

- Переключатель **«%» / «₽»**: в процентах все бумаги стартуют от нуля и сравнимы между собой, в рублях показывается абсолютная цена.
- На правой шкале у каждой линии своя плашка с последним значением.
- Таблица под графиком: цена, изменение за день (зелёное — рост, красное — падение) и **свежесть**: MOEX опрашивается раз в минуту и отдаёт данные с задержкой ~15 минут, это видно в бейдже «задержка 15 мин».
- Красный бейдж «закрыт» означает, что торги сейчас не идут.

### Валюты ЦБ РФ

![Валюты: курсы ЦБ и динамика за 30 дней](docs/screenshots/fiat-rates.jpg)

ЦБ публикует курс раз в сутки, поэтому живого потока нет: таблица с курсом в рублях, датой вступления в силу и мини-графиком за 30 дней. Клик по строке открывает историю курса выбранной валюты под таблицей.

![Валюты: история курса USD](docs/screenshots/fiat-history.jpg)

### ИИ-аналитик

![ИИ-чат: вопрос про BTC](docs/screenshots/ai-chat.jpg)

Кнопка в правом нижнем углу открывает чат. Под заголовком показан остаток дневной квоты («осталось ~95% на сегодня»), в пустом чате есть примеры вопросов. Ассистент не читает график глазами, а вызывает инструменты над данными проекта (`list_assets`, `get_current`, `get_period_stats`, `get_indicators`, `find_big_moves`) и описывает результат: цену, SMA/RSI, диапазон, риски. Рекомендаций «купить/продать» он не даёт — в конце ответа всегда оговорка, что это не инвестиционная рекомендация. Подробнее: [docs/06-ai-chat.md](docs/06-ai-chat.md).

### Админка

![Админка Wagtail: крипто-активы](docs/screenshots/admin-crypto-assets.jpg)

Wagtail-админка (`http://localhost:8000/api/cms/admin/`) управляет составом инструментов: крипто-активы, акции, фиатные валюты, сделки по акциям и снапшоты. Флажок **«Активен»** включает инструмент: например, пара крипты попадает в Binance-стрим сразу после сохранения (без перезапуска), а на странице «Крипта» появляются только активные активы. Периодические задачи Celery (опрос MOEX и ЦБ) настраиваются в Django admin (`/api/admin/`).

## Документация

| Файл | О чём |
|---|---|
| [docs/01-architecture.md](docs/01-architecture.md) | сервисы, роли Redis, слои кода, маршруты |
| [docs/02-crypto-binance.md](docs/02-crypto-binance.md) | путь крипто-сделок: WebSocket → Redis Stream → Postgres |
| [docs/03-moex-cbr.md](docs/03-moex-cbr.md) | опрос MOEX и ЦБ через Celery |
| [docs/04-network.md](docs/04-network.md) | ретраи, таймауты, прокси, сертификаты |
| [docs/05-sse-live.md](docs/05-sse-live.md) | live-потоки SSE и выборка «latest N» |
| [docs/06-ai-chat.md](docs/06-ai-chat.md) | как ИИ-чат общается с пользователем и инструментами |
| [docs/07-ai-quota.md](docs/07-ai-quota.md) | токены и квота ИИ |

Документы описывают код на момент написания; при расхождении источник правды — код и `config/settings/base.py`.

## Быстрый старт

Основной сценарий — Docker. Достаточно Docker Compose, `just` не нужен: он лишь сокращает команды.

```
docker compose -f docker-compose.local.yml up --build -d     # собрать образы и поднять все сервисы
docker compose -f docker-compose.local.yml logs -f           # логи
docker compose -f docker-compose.local.yml down              # остановить
```

Остальные команды запускаются внутри контейнеров:

```
docker compose -f docker-compose.local.yml run --rm django python ./manage.py <args>   # manage.py
docker compose -f docker-compose.local.yml run --rm django pytest <args>               # тесты
docker compose -f docker-compose.local.yml run --rm -T django python ./manage.py dmr_export_schema config.api_router.schema --indent 2 --no-ensure-ascii > frontend/openapi.json.tmp && mv frontend/openapi.json.tmp frontend/openapi.json   # OpenAPI
```

Если установлен `just`, те же команды короче (он сам подставляет `-f docker-compose.local.yml`): `just up`, `just down`, `just logs`, `just build`, `just manage <args>`, `just pytest <args>`, `just schema`. Чтобы не писать `-f` каждый раз без `just`, можно выполнить `export COMPOSE_FILE=docker-compose.local.yml`.

- API: http://localhost:8000/api/, Swagger (только staff): `/api/docs/`
- Фронтенд: http://localhost:3000
- Суперпользователь: `docker compose -f docker-compose.local.yml run --rm django python ./manage.py createsuperuser`
- Расписание Celery хранится в БД: на чистой установке задач нет, периодические задачи добавляются вручную в Django admin.
- Секреты ИИ — в `.envs/.local/.ai` (шаблон `.ai.example`), включение — `AI_ENABLED=true`.

## Проверки

```
uv run ruff check .
uv run ruff format .
uv run mypy tickfeeddmr
docker compose -f docker-compose.local.yml run --rm django pytest   # локальный стек (или just pytest)
docker compose -f docker-compose.test.yml run --rm django pytest   # как в CI
```

Подробности по окружению и конвенциям проекта — в [CLAUDE.md](CLAUDE.md).

License: MIT
