import logging
import random
from datetime import datetime, timedelta

import pytz
from aiogram import Bot
from sqlalchemy import and_, select

from config import settings
from shared.database import AsyncSessionFactory
from shared.models import Curator, Practice, Student, TomirisReminderSent
from shared.sheets import get_sheets

logger = logging.getLogger(__name__)
TZ = pytz.timezone(settings.timezone)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _students_in_stream(session, stream_name: str) -> list[int]:
    result = await session.execute(
        select(Student.telegram_id).where(Student.stream_name == stream_name)
    )
    return [r[0] for r in result.all()]


async def _students_in_group(session, stream_name: str, group_name: str) -> list[int]:
    result = await session.execute(
        select(Student.telegram_id).where(
            Student.stream_name == stream_name,
            Student.group_name == group_name,
        )
    )
    return [r[0] for r in result.all()]


async def _broadcast(bot: Bot, tg_ids: list[int], text: str) -> None:
    for tg_id in tg_ids:
        try:
            await bot.send_message(tg_id, text, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Send failed {tg_id}: {e}")


# ---------------------------------------------------------------------------
# Пн 12:00 — новые уроки + тест если есть
# ---------------------------------------------------------------------------

async def notify_new_lessons(bot: Bot) -> None:
    logger.info("Task: notify_new_lessons")
    sheets = get_sheets()
    async with AsyncSessionFactory() as session:
        for stream in sheets.get_streams():
            week = stream.current_week
            lessons = sheets.get_lessons(week)
            if not lessons:
                continue

            lessons_text = "\n".join(f"  №{l.lesson_number} — {l.title}" for l in lessons)
            deadline_str = stream.deadline_for_week(week).strftime("%d.%m.%Y")
            test = sheets.get_test(week)
            test_line = f"\n\n📊 <b>Контрольный тест этой недели:</b>\n  {test.title}" if test else ""

            text = (
                f"📚 <b>Неделя {week} началась!</b>\n\n"
                f"Новые уроки:\n{lessons_text}"
                f"{test_line}\n\n"
                f"📌 Дедлайн: <b>воскресенье {deadline_str} в 12:00</b> 🚀"
            )
            ids = await _students_in_stream(session, stream.name)
            await _broadcast(bot, ids, text)


# ---------------------------------------------------------------------------
# Вт 11:00 — мотивашка (цитата)
# ---------------------------------------------------------------------------

async def send_midweek_quote(bot: Bot) -> None:
    logger.info("Task: send_midweek_quote")
    sheets = get_sheets()
    async with AsyncSessionFactory() as session:
        for stream in sheets.get_streams():
            quotes = sheets.get_quotes(stream.current_week)
            if not quotes:
                continue
            q = random.choice(quotes)
            text = f"💡 <b>Мысль дня</b>\n\n«{q.text}»\n\n— <i>{q.author}</i>"
            ids = await _students_in_stream(session, stream.name)
            await _broadcast(bot, ids, text)


# ---------------------------------------------------------------------------
# Напоминания об уроках — разные тексты для ср/пт/сб
# ---------------------------------------------------------------------------

LESSON_REMINDERS = [
    # Среда 13:00
    (
        "📖 <b>Середина недели — самое время для уроков!</b>\n\n"
        "Не откладывай на потом — сядь и посмотри хотя бы один урок прямо сейчас. "
        "Дедлайн в воскресенье в 12:00 ⏰"
    ),
    # Пятница 16:00
    (
        "⚡️ <b>Пятница — последний шанс не тянуть до выходных!</b>\n\n"
        "Ты уже посмотрел все уроки этой недели? Если нет — самое время. "
        "Воскресенье наступит быстрее чем кажется 😅"
    ),
    # Суббота 17:00
    (
        "🔥 <b>Суббота! Завтра дедлайн.</b>\n\n"
        "Если ещё не смотрел уроки — бросай всё и смотри. "
        "Конспекты нужно сдать завтра до 12:00 💪"
    ),
]


async def remind_lessons_wed(bot: Bot) -> None:
    logger.info("Task: remind_lessons_wed")
    sheets = get_sheets()
    async with AsyncSessionFactory() as session:
        for stream in sheets.get_streams():
            ids = await _students_in_stream(session, stream.name)
            await _broadcast(bot, ids, LESSON_REMINDERS[0])


async def remind_lessons_fri(bot: Bot) -> None:
    logger.info("Task: remind_lessons_fri")
    sheets = get_sheets()
    async with AsyncSessionFactory() as session:
        for stream in sheets.get_streams():
            ids = await _students_in_stream(session, stream.name)
            await _broadcast(bot, ids, LESSON_REMINDERS[1])


async def remind_lessons_sat(bot: Bot) -> None:
    logger.info("Task: remind_lessons_sat")
    sheets = get_sheets()
    async with AsyncSessionFactory() as session:
        for stream in sheets.get_streams():
            ids = await _students_in_stream(session, stream.name)
            await _broadcast(bot, ids, LESSON_REMINDERS[2])


# ---------------------------------------------------------------------------
# Сб 18:00 — напоминание сдать конспекты/тест
# ---------------------------------------------------------------------------

async def remind_saturday(bot: Bot) -> None:
    logger.info("Task: remind_saturday")
    sheets = get_sheets()
    async with AsyncSessionFactory() as session:
        for stream in sheets.get_streams():
            week = stream.current_week
            test = sheets.get_test(week)
            deadline_str = stream.deadline_for_week(week).strftime("%d.%m в %H:%M")
            test_line = f"\n📊 {test.title}" if test else ""
            text = (
                f"⏰ <b>Напоминание!</b>\n\n"
                f"Завтра дедлайн в {deadline_str}:\n"
                f"📝 Конспекты недели {week}"
                f"{test_line}\n\n"
                f"Не откладывай! 😉"
            )
            ids = await _students_in_stream(session, stream.name)
            await _broadcast(bot, ids, text)


# ---------------------------------------------------------------------------
# Вс 11:00 — последнее напоминание
# ---------------------------------------------------------------------------

async def remind_sunday(bot: Bot) -> None:
    logger.info("Task: remind_sunday")
    sheets = get_sheets()
    async with AsyncSessionFactory() as session:
        for stream in sheets.get_streams():
            week = stream.current_week
            test = sheets.get_test(week)
            test_line = f"\n📊 {test.title}" if test else ""
            text = (
                f"🚨 <b>Остался 1 час!</b>\n\n"
                f"Дедлайн в 12:00:\n"
                f"📝 Конспекты недели {week}"
                f"{test_line}\n\n"
                f"Срочно сдавай! ⚡️"
            )
            ids = await _students_in_stream(session, stream.name)
            await _broadcast(bot, ids, text)


# ---------------------------------------------------------------------------
# Пн и Чт — интерактивки (индивидуально для каждого потока по флагу в Sheets)
#
# Структура листа Interactive в Google Sheets:
#   A: stream_name
#   B: week_number
#   C: sent (TRUE/FALSE — ты сам ставишь TRUE когда нужно отправить)
#
# Бот отправляет только если sent=TRUE и сбрасывает после отправки (ставит FALSE)
# ---------------------------------------------------------------------------

async def remind_interactive(bot: Bot) -> None:
    logger.info("Task: remind_interactive")
    sheets = get_sheets()

    async with AsyncSessionFactory() as session:
        rows = sheets._get_rows("Interactive")

        for row in rows:
            if len(row) < 2 or not row[0]:
                continue

            stream_name = row[0].strip()
            sent_flag = row[1].strip().upper()

            if sent_flag != "TRUE":
                continue

            text = (
                f"🎯 <b>Интерактивное задание!</b>\n\n"
                f"Не забудь выполнить интерактивное задание этой недели. "
                f"Это важная часть курса! 💪"
            )

            ids = await _students_in_stream(session, stream_name)
            await _broadcast(bot, ids, text)
            logger.info(f"Interactive sent to {stream_name}")

# ---------------------------------------------------------------------------
# Каждые 5 мин — напоминание о практике куратора за 1 час
# ---------------------------------------------------------------------------

async def remind_practices(bot: Bot) -> None:
    now = datetime.now(TZ)
    window_from = now + timedelta(minutes=55)
    window_to = now + timedelta(minutes=65)

    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(Practice).where(
                and_(
                    Practice.scheduled_at >= window_from,
                    Practice.scheduled_at <= window_to,
                    Practice.reminder_sent == False,
                )
            )
        )
        practices = result.scalars().all()

        for practice in practices:
            dt_str = practice.scheduled_at.astimezone(TZ).strftime("%H:%M")
            text = (
                f"🔔 <b>Через 1 час — практика с куратором!</b>\n\n"
                f"⏰ Начало в <b>{dt_str}</b> 🎯"
            )
            ids = await _students_in_group(session, practice.stream_name, practice.group_name)
            if ids:
                await _broadcast(bot, ids, text)
                practice.reminder_sent = True

        await session.commit()


# ---------------------------------------------------------------------------
# Каждые 5 мин — напоминания о практике Томирис (за день, за 4ч, за 1ч)
# ---------------------------------------------------------------------------

async def remind_tomiris_practice_scheduled(bot: Bot) -> None:
    sheets = get_sheets()
    now = datetime.now(TZ)

    windows = [
        (timedelta(hours=23, minutes=30), timedelta(hours=24, minutes=30), "day",  "завтра"),
        (timedelta(hours=3,  minutes=30), timedelta(hours=4,  minutes=30), "4h",   "через 4 часа"),
        (timedelta(minutes=30),           timedelta(hours=1,  minutes=30), "1h",   "через 1 час"),
    ]

    async with AsyncSessionFactory() as session:
        for p in sheets.get_tomiris_practices():
            for w_from, w_to, label, label_text in windows:
                if not (now + w_from <= p.scheduled_at <= now + w_to):
                    continue

                result = await session.execute(
                    select(TomirisReminderSent).where(
                        and_(
                            TomirisReminderSent.stream_name == p.stream_name,
                            TomirisReminderSent.scheduled_at == p.scheduled_at,
                            TomirisReminderSent.label == label,
                        )
                    )
                )
                if result.scalar_one_or_none():
                    continue

                dt_str = p.scheduled_at.astimezone(TZ).strftime("%d.%m.%Y в %H:%M")
                text = (
                    f"👑 <b>Практика с Томирис {label_text}!</b>\n\n"
                    f"🗓 <b>{dt_str}</b>\n\n"
                    f"Готовься! 💪"
                )

                if p.group_name:
                    ids = await _students_in_group(session, p.stream_name, p.group_name)
                else:
                    ids = await _students_in_stream(session, p.stream_name)

                await _broadcast(bot, ids, text)

                session.add(TomirisReminderSent(
                    stream_name=p.stream_name,
                    scheduled_at=p.scheduled_at,
                    label=label,
                ))

        await session.commit()


# ---------------------------------------------------------------------------
# Каждый день 18:00 — напоминание кураторам внести баллы
# ---------------------------------------------------------------------------

async def remind_curators_scores(bot: Bot) -> None:
    logger.info("Task: remind_curators_scores")
    async with AsyncSessionFactory() as session:
        result = await session.execute(select(Curator.telegram_id))
        ids = [r[0] for r in result.all()]
        text = (
            f"📝 <b>Напоминание!</b>\n\n"
            f"До 18:40 необходимо внести баллы учеников. ⏰"
        )
        await _broadcast(bot, ids, text)
