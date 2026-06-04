import asyncio
import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import settings
from shared.database import init_db
from scheduler.tasks import (
    notify_new_lessons,
    send_midweek_quote,
    remind_lessons_wed,
    remind_lessons_fri,
    remind_lessons_sat,
    remind_saturday,
    remind_sunday,
    remind_interactive,
    remind_practices,
    remind_tomiris_practice_scheduled,
    remind_curators_scores,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def build_scheduler(bot: Bot) -> AsyncIOScheduler:
    s = AsyncIOScheduler(timezone=settings.timezone)

    # Пн 12:00 — новые уроки + тест
    s.add_job(notify_new_lessons,    "cron", day_of_week="mon", hour=12, minute=0,  kwargs={"bot": bot}, id="new_lessons")
    # Пн 12:30 — интерактивка
    s.add_job(remind_interactive,    "cron", day_of_week="mon", hour=12, minute=30, kwargs={"bot": bot}, id="interactive_mon")
    # Вт 11:00 — мотивашка (цитата)
    s.add_job(send_midweek_quote,    "cron", day_of_week="tue", hour=11, minute=0,  kwargs={"bot": bot}, id="quote")
    # Ср 13:00 — напоминание уроки
    s.add_job(remind_lessons_wed,    "cron", day_of_week="wed", hour=13, minute=0,  kwargs={"bot": bot}, id="lessons_wed")
    # Чт 12:30 — интерактивка
    s.add_job(remind_interactive,    "cron", day_of_week="thu", hour=12, minute=30, kwargs={"bot": bot}, id="interactive_thu")
    # Пт 16:00 — напоминание уроки
    s.add_job(remind_lessons_fri,    "cron", day_of_week="fri", hour=16, minute=0,  kwargs={"bot": bot}, id="lessons_fri")
    # Сб 17:00 — напоминание уроки
    s.add_job(remind_lessons_sat,    "cron", day_of_week="sat", hour=17, minute=0,  kwargs={"bot": bot}, id="lessons_sat")
    # Сб 18:00 — напоминание конспекты/тест
    s.add_job(remind_saturday,       "cron", day_of_week="sat", hour=18, minute=0,  kwargs={"bot": bot}, id="remind_sat")
    # Вс 11:00 — последнее напоминание
    s.add_job(remind_sunday,         "cron", day_of_week="sun", hour=11, minute=0,  kwargs={"bot": bot}, id="remind_sun")
    # Каждый день 18:00 — кураторам внести баллы
   # s.add_job(remind_curators_scores,"cron", hour=18, minute=0,                     kwargs={"bot": bot}, id="curator_scores")
    # Каждые 5 мин — практики кураторов
    s.add_job(remind_practices,      "interval", minutes=5,                          kwargs={"bot": bot}, id="remind_practices")
    # Каждые 5 мин — практики Томирис
    s.add_job(remind_tomiris_practice_scheduled, "interval", minutes=5,              kwargs={"bot": bot}, id="tomiris_reminders")

    return s


async def main() -> None:
    await init_db()

    bot = Bot(
        token=settings.student_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    scheduler = build_scheduler(bot)
    scheduler.start()

    logger.info("⏰ Scheduler started:")
    for job in scheduler.get_jobs():
        logger.info(f"  {job.id} → {job.next_run_time}")

    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
