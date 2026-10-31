# TOM 2.0 — телеграм-бот учеников

Один процесс (`main.py`): бот учеников + планировщик рассылок (APScheduler).
Все данные лежат в Supabase (PostgreSQL). Часовой пояс — Asia/Almaty.

## Структура проекта

```
main.py                         — точка входа: бот + планировщик
config.py                       — переменные окружения
shared/database.py              — подключение к БД
shared/models.py                — модели таблиц
student_bot/routers/registration.py — /start и выбор потока
student_bot/keyboards/inline.py — кнопки потоков
student_bot/middlewares/db.py   — сессия БД для каждого апдейта
scheduler/runner.py             — расписание задач
scheduler/tasks.py              — сами рассылки
```

## Локальный запуск

```bash
pip install -r requirements.txt
python main.py
```

## Переменные окружения

```
STUDENT_BOT_TOKEN=токен_бота_учеников
DATABASE_URL=postgresql+asyncpg://...supabase...
TIMEZONE=Asia/Almaty
```

Локально их можно положить в `.env` (он в `.gitignore`, не коммитить).
На Railway — в Variables. Start Command: `python main.py`.

## Таблицы в Supabase

Бот таблицы не создаёт — они создаются и заполняются вручную.
Названия потоков везде в формате `Поток 9`.

| Таблица | Колонки | Что лежит |
|---------|---------|-----------|
| `students` | telegram_id, username, full_name, stream_name, registered_at | Ученики, заполняет бот при выборе потока |
| `stream_weeks` | id, stream_name, week_number, week_date, announce_date, deadline | Недели каждого потока с готовыми датами. Уникально по (stream_name, week_number) |
| `calendar_events` | id, stream_name, week_number, event_type, title | События недели: `interactive` или `test` |
| `lessons` | lesson_number, week_number, title | Уроки по неделям (общие для всех потоков) |
| `quotes` | id, week_number, author, text | Цитаты. week_number = NULL — подходит любой неделе |
| `tomiris_practices` | id, stream_name, scheduled_at | Практики с Томирис |
| `tomiris_reminders_sent` | id, stream_name, scheduled_at, label | Какие напоминания о практиках уже отправлены (`day`, `4h`, `1h`) |

**Текущая неделя потока** — строка в `stream_weeks`, где
`announce_date <= сегодня <= дата deadline`. Если такой нет (поток не начался,
каникулы, обучение закончилось) — потоку ничего не шлётся.

При `/start` показываются только потоки, у которых последний `deadline` ещё в будущем.

## Расписание рассылок (Asia/Almaty)

| Время | Что |
|-------|-----|
| Каждый день 12:00 | «Неделя N началась» + уроки + дедлайн (+ тест). Потокам с `announce_date` = сегодня |
| Пн, Чт 12:30 | Интерактивка, если есть событие `interactive` (+ тест в том же сообщении) |
| Вт 11:00 | Цитата недели, иначе общая |
| Ср 13:00, Пт 16:00, Сб 17:00 | Напоминания смотреть уроки |
| Сб 18:00 | Завтра дедлайн (+ тест) |
| Вс 11:00 | Остался 1 час (+ тест) |
| Каждые 5 мин | Практики Томирис: за сутки, за 4 часа, за 1 час |

## Как добавить практику Томирис

Добавь строку в `tomiris_practices` (время указывай с часовым поясом):

```sql
insert into tomiris_practices (stream_name, scheduled_at)
values ('Поток 9', '2026-11-12 19:00:00+05');
```

Бот сам напомнит ученикам этого потока за сутки, за 4 часа и за 1 час.
