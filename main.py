"""
main.py — единая точка входа для Railway.
Запускает бота учеников и планировщик рассылок в одном процессе.
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import settings
from scheduler.runner import build_scheduler
from student_bot.middlewares.db import DbSessionMiddleware
from student_bot.routers.registration import router as reg_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    bot = Bot(
        token=settings.student_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.update.middleware(DbSessionMiddleware())
    dp.include_router(reg_router)

    # Планировщик шлёт рассылки через того же бота
    scheduler = build_scheduler(bot)
    scheduler.start()
    logger.info("⏰ Scheduler started")

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("🚀 Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
