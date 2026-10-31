from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import Student, StreamWeek
from student_bot.keyboards.inline import streams_keyboard

router = Router(name="registration")


async def get_active_streams(session):
    result = await session.execute(
        select(StreamWeek.stream_name)
        .group_by(StreamWeek.stream_name)
        .having(func.max(StreamWeek.deadline) > datetime.now(timezone.utc))
    )
    names = [row[0] for row in result.all()]

    # сортируем по числу: "Поток 9" -> 9
    names.sort(key=lambda name: int(name.split()[-1]))
    return names


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    # Повторный /start просто показывает потоки снова — так можно сменить поток
    streams = await get_active_streams(session)
    if not streams:
        await message.answer("😔 Пока нет активных потоков. Следи за анонсами!")
        return

    await message.answer(
        "👋 Привет! Добро пожаловать в <b>TOM 2.0</b>.\n\n"
        "Выбери свой <b>поток</b>:",
        reply_markup=streams_keyboard(streams),
    )


@router.callback_query(F.data.startswith("stream:"))
async def on_stream_selected(call: CallbackQuery, session: AsyncSession) -> None:
    # Поток берём из callback_data, например "stream:Поток 9"
    stream_name = call.data.split(":", 1)[1]

    # Защита от старых кнопок с уже закончившимся потоком
    if stream_name not in await get_active_streams(session):
        await call.answer("Этот поток уже недоступен. Нажми /start", show_alert=True)
        return

    student = await session.get(Student, call.from_user.id)
    if student is None:
        student = Student(telegram_id=call.from_user.id)
        session.add(student)

    student.username = call.from_user.username
    student.full_name = call.from_user.full_name
    student.stream_name = stream_name
    # Коммит делает DbSessionMiddleware после обработчика

    await call.message.edit_text(
        f"🎉 Готово! Твой поток: <b>{stream_name}</b>\n\n"
        f"Жди уведомлений о новых уроках и практиках. Удачи! 🚀"
    )
    await call.answer("✅ Готово!")
