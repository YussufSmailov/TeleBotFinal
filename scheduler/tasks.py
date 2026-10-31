"""
Задачи планировщика. Все данные берутся только из БД (Supabase).
"""

import asyncio
import logging
import random
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot
from sqlalchemy import select

from config import settings
from shared.database import AsyncSessionFactory
from shared.models import (
    CalendarEvent,
    Lesson,
    Quote,
    StreamWeek,
    Student,
    TomirisPractice,
    TomirisReminderSent,
)

logger = logging.getLogger(__name__)
TZ = ZoneInfo(settings.timezone)


# ---------------------------------------------------------------------------
# Помощники
# ---------------------------------------------------------------------------

def today_almaty() -> date:
    """Сегодняшняя дата по Алматы."""
    return datetime.now(TZ).date()


async def get_stream_students(session, stream_name: str) -> list[int]:
    """telegram_id всех учеников потока."""
    result = await session.execute(
        select(Student.telegram_id).where(Student.stream_name == stream_name)
    )
    return [row[0] for row in result.all()]


async def get_practice_students(session, practice: TomirisPractice) -> list[int]:
    """
    telegram_id учеников, которым нужна эта практика.
    group_names пустое (NULL) — весь поток, включая тех, кто группу не выбрал.
    Иначе — только ученики потока из перечисленных групп.
    """
    if not practice.group_names:
        return await get_stream_students(session, practice.stream_name)

    result = await session.execute(
        select(Student.telegram_id).where(
            Student.stream_name == practice.stream_name,
            Student.group_name.in_(practice.group_names),
        )
    )
    return [row[0] for row in result.all()]


async def broadcast(bot: Bot, tg_ids: list[int], text: str) -> None:
    """Шлём текст каждому ученику, ошибки по одному не ломают рассылку."""
    for tg_id in tg_ids:
        try:
            await bot.send_message(tg_id, text)
        except Exception as e:
            logger.warning(f"Не удалось отправить {tg_id}: {e}")
        await asyncio.sleep(0.05)


async def send_to_stream(bot: Bot, session, stream_name: str, text: str) -> None:
    """Рассылка всем ученикам одного потока."""
    ids = await get_stream_students(session, stream_name)
    await broadcast(bot, ids, text)
    logger.info(f"Отправлено {len(ids)} ученикам потока «{stream_name}»")


async def get_current_weeks(session) -> list[StreamWeek]:
    """
    Текущая неделя каждого потока: announce_date <= сегодня <= дата дедлайна.
    Если у потока такой недели нет — его в списке не будет.
    """
    today = today_almaty()
    result = await session.execute(
        select(StreamWeek)
        .where(StreamWeek.announce_date <= today)
        .order_by(StreamWeek.stream_name, StreamWeek.week_number)
    )
    current = {}
    for week in result.scalars().all():
        deadline_day = week.deadline.astimezone(TZ).date()
        # Берём самую раннюю подходящую неделю потока
        if today <= deadline_day and week.stream_name not in current:
            current[week.stream_name] = week
    return list(current.values())


async def get_events(session, week: StreamWeek, event_type: str) -> list[CalendarEvent]:
    """События недели нужного типа ('interactive' или 'test')."""
    result = await session.execute(
        select(CalendarEvent).where(
            CalendarEvent.stream_name == week.stream_name,
            CalendarEvent.week_number == week.week_number,
            CalendarEvent.event_type == event_type,
        )
    )
    return list(result.scalars().all())


async def test_line(session, week: StreamWeek) -> str:
    """Строка про контрольный тест или пустая строка."""
    tests = await get_events(session, week, "test")
    if not tests:
        return ""
    titles = ", ".join(t.title for t in tests)
    return f"\n📊 Контрольный тест: <b>{titles}</b>"


def deadline_text(week: StreamWeek) -> str:
    """Например: «воскресенье 09.11 в 12:00»."""
    d = week.deadline.astimezone(TZ)
    return f"воскресенье {d:%d.%m} в {d:%H:%M}"


# ---------------------------------------------------------------------------
# Каждый день 12:00 — «Неделя N началась»
# ---------------------------------------------------------------------------

async def announce_new_week(bot: Bot) -> None:
    logger.info("Task: announce_new_week")
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(StreamWeek).where(StreamWeek.announce_date == today_almaty())
        )
        for week in result.scalars().all():
            lessons = await session.execute(
                select(Lesson)
                .where(Lesson.week_number == week.week_number)
                .order_by(Lesson.lesson_number)
            )
            lessons_text = "\n".join(
                f"  №{l.lesson_number} — {l.title}" for l in lessons.scalars().all()
            )
            text = (
                f"📚 <b>Неделя {week.week_number} началась!</b>\n\n"
                f"Уроки этой недели:\n{lessons_text}"
                f"{await test_line(session, week)}\n\n"
                f"📌 Дедлайн: <b>{deadline_text(week)}</b> 🚀"
            )
            await send_to_stream(bot, session, week.stream_name, text)


# ---------------------------------------------------------------------------
# Пн и Чт 12:30 — интерактивка
# ---------------------------------------------------------------------------

async def remind_interactive(bot: Bot) -> None:
    logger.info("Task: remind_interactive")
    async with AsyncSessionFactory() as session:
        for week in await get_current_weeks(session):
            interactives = await get_events(session, week, "interactive")
            if not interactives:
                continue
            titles = ", ".join(i.title for i in interactives)
            # Если на этой неделе ещё и тест — пишем про него в том же сообщении
            text = (
                f"🎯 <b>Интерактивное задание!</b>\n\n"
                f"На этой неделе: <b>{titles}</b>"
                f"{await test_line(session, week)}\n\n"
                f"Не забудь выполнить до дедлайна ({deadline_text(week)}) 💪"
            )
            await send_to_stream(bot, session, week.stream_name, text)


# ---------------------------------------------------------------------------
# Вт 11:00 — цитата
# ---------------------------------------------------------------------------

async def pick_quote(session, week_number: int) -> Quote | None:
    """Цитата для недели, иначе любая общая (week_number NULL), иначе None."""
    for condition in (Quote.week_number == week_number, Quote.week_number.is_(None)):
        result = await session.execute(select(Quote).where(condition))
        quotes = result.scalars().all()
        if quotes:
            return random.choice(quotes)
    return None


async def send_quote(bot: Bot) -> None:
    logger.info("Task: send_quote")
    async with AsyncSessionFactory() as session:
        for week in await get_current_weeks(session):
            quote = await pick_quote(session, week.week_number)
            if quote is None:
                continue
            text = f"💡 <b>Мысль дня</b>\n\n«{quote.text}»\n\n— <i>{quote.author}</i>"
            await send_to_stream(bot, session, week.stream_name, text)


# ---------------------------------------------------------------------------
# Ср 13:00, Пт 16:00, Сб 17:00 — напоминания смотреть уроки
# ---------------------------------------------------------------------------

LESSON_REMINDERS = {
    "wed": (
        "📖 <b>Середина недели — самое время для уроков!</b>\n\n"
        "Не откладывай на потом — сядь и посмотри хотя бы один урок прямо сейчас. "
        "Дедлайн в воскресенье в 12:00 ⏰"
    ),
    "fri": (
        "⚡️ <b>Пятница — последний шанс не тянуть до выходных!</b>\n\n"
        "Ты уже посмотрел все уроки этой недели? Если нет — самое время. "
        "Воскресенье наступит быстрее чем кажется 😅"
    ),
    "sat": (
        "🔥 <b>Суббота! Завтра дедлайн.</b>\n\n"
        "Если ещё не смотрел уроки — бросай всё и смотри. "
        "Конспекты нужно сдать завтра до 12:00 💪"
    ),
}


async def remind_lessons(bot: Bot, day: str) -> None:
    logger.info(f"Task: remind_lessons ({day})")
    async with AsyncSessionFactory() as session:
        for week in await get_current_weeks(session):
            await send_to_stream(bot, session, week.stream_name, LESSON_REMINDERS[day])


async def remind_lessons_wed(bot: Bot) -> None:
    await remind_lessons(bot, "wed")


async def remind_lessons_fri(bot: Bot) -> None:
    await remind_lessons(bot, "fri")


async def remind_lessons_sat(bot: Bot) -> None:
    await remind_lessons(bot, "sat")


# ---------------------------------------------------------------------------
# Сб 18:00 — завтра дедлайн
# ---------------------------------------------------------------------------

async def remind_saturday(bot: Bot) -> None:
    logger.info("Task: remind_saturday")
    async with AsyncSessionFactory() as session:
        for week in await get_current_weeks(session):
            text = (
                f"⏰ <b>Завтра дедлайн!</b>\n\n"
                f"Срок: <b>{deadline_text(week)}</b>\n"
                f"📝 Конспекты недели {week.week_number}"
                f"{await test_line(session, week)}\n\n"
                f"Не откладывай! 😉"
            )
            await send_to_stream(bot, session, week.stream_name, text)


# ---------------------------------------------------------------------------
# Вс 11:00 — остался 1 час
# ---------------------------------------------------------------------------

async def remind_sunday(bot: Bot) -> None:
    logger.info("Task: remind_sunday")
    async with AsyncSessionFactory() as session:
        for week in await get_current_weeks(session):
            d = week.deadline.astimezone(TZ)
            text = (
                f"🚨 <b>Остался 1 час!</b>\n\n"
                f"Дедлайн в {d:%H:%M}:\n"
                f"📝 Конспекты недели {week.week_number}"
                f"{await test_line(session, week)}\n\n"
                f"Срочно сдавай! ⚡️"
            )
            await send_to_stream(bot, session, week.stream_name, text)


# ---------------------------------------------------------------------------
# Каждые 5 минут — практики Томирис (за сутки, за 4 часа, за 1 час)
# ---------------------------------------------------------------------------

# (от, до, метка, текст) — окно «сколько осталось до практики»
TOMIRIS_WINDOWS = [
    (timedelta(hours=23, minutes=30), timedelta(hours=24, minutes=30), "day", "завтра"),
    (timedelta(hours=3, minutes=30), timedelta(hours=4, minutes=30), "4h", "через 4 часа"),
    (timedelta(minutes=30), timedelta(hours=1, minutes=30), "1h", "через 1 час"),
]


async def already_sent(session, practice: TomirisPractice, label: str) -> bool:
    """Было ли уже такое напоминание."""
    result = await session.execute(
        select(TomirisReminderSent.id).where(
            TomirisReminderSent.stream_name == practice.stream_name,
            TomirisReminderSent.scheduled_at == practice.scheduled_at,
            TomirisReminderSent.label == label,
        )
    )
    return result.first() is not None


async def remind_tomiris_practices(bot: Bot) -> None:
    now = datetime.now(TZ)
    async with AsyncSessionFactory() as session:
        # Берём только практики в ближайшие ~сутки
        result = await session.execute(
            select(TomirisPractice).where(
                TomirisPractice.scheduled_at >= now + timedelta(minutes=30),
                TomirisPractice.scheduled_at <= now + timedelta(hours=24, minutes=30),
            )
        )
        for practice in result.scalars().all():
            time_left = practice.scheduled_at - now
            for w_from, w_to, label, label_text in TOMIRIS_WINDOWS:
                if not (w_from <= time_left <= w_to):
                    continue
                if await already_sent(session, practice, label):
                    continue

                dt = practice.scheduled_at.astimezone(TZ)
                text = (
                    f"👑 <b>Практика с Томирис {label_text}!</b>\n\n"
                    f"🗓 <b>{dt:%d.%m.%Y в %H:%M}</b>\n\n"
                    f"Готовься! 💪"
                )
                ids = await get_practice_students(session, practice)
                await broadcast(bot, ids, text)
                logger.info(
                    f"Томирис ({label}): отправлено {len(ids)} ученикам потока "
                    f"«{practice.stream_name}», группы: {practice.group_names or 'все'}"
                )

                # Сразу записываем, чтобы не отправить повторно
                session.add(TomirisReminderSent(
                    stream_name=practice.stream_name,
                    scheduled_at=practice.scheduled_at,
                    label=label,
                ))
                await session.commit()
