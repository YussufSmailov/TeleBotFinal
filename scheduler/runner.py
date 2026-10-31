from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import settings
from scheduler.tasks import (
    announce_new_week,
    remind_interactive,
    send_quote,
    remind_lessons_wed,
    remind_lessons_fri,
    remind_lessons_sat,
    remind_saturday,
    remind_sunday,
    remind_tomiris_practices,
)


def build_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Все задачи по времени Asia/Almaty."""
    s = AsyncIOScheduler(timezone=settings.timezone)
    kw = {"bot": bot}

    # Каждый день 12:00 — «Неделя N началась» (если сегодня announce_date)
    s.add_job(announce_new_week, "cron", hour=12, minute=0, kwargs=kw, id="announce_week")
    # Пн и Чт 12:30 — интерактивка
    s.add_job(remind_interactive, "cron", day_of_week="mon,thu", hour=12, minute=30, kwargs=kw, id="interactive")
    # Вт 11:00 — цитата
    s.add_job(send_quote, "cron", day_of_week="tue", hour=11, minute=0, kwargs=kw, id="quote")
    # Ср 13:00, Пт 16:00, Сб 17:00 — смотреть уроки
    s.add_job(remind_lessons_wed, "cron", day_of_week="wed", hour=13, minute=0, kwargs=kw, id="lessons_wed")
    s.add_job(remind_lessons_fri, "cron", day_of_week="fri", hour=16, minute=0, kwargs=kw, id="lessons_fri")
    s.add_job(remind_lessons_sat, "cron", day_of_week="sat", hour=17, minute=0, kwargs=kw, id="lessons_sat")
    # Сб 18:00 — завтра дедлайн
    s.add_job(remind_saturday, "cron", day_of_week="sat", hour=18, minute=0, kwargs=kw, id="remind_sat")
    # Вс 11:00 — остался 1 час
    s.add_job(remind_sunday, "cron", day_of_week="sun", hour=11, minute=0, kwargs=kw, id="remind_sun")
    # Каждые 5 минут — практики Томирис
    s.add_job(remind_tomiris_practices, "interval", minutes=5, kwargs=kw, id="tomiris")

    return s
