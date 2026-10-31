import re
from datetime import datetime, timezone
from html import escape

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import Group, Student, StreamWeek
from student_bot.keyboards.inline import groups_keyboard, streams_keyboard

router = Router(name="registration")

WELCOME_TEXT = (
    "👋 Привет! Добро пожаловать в <b>TOM 2.0</b>.\n\n"
    "Выбери свой <b>поток</b>:"
)


def stream_sort_key(name: str):
    """
    Ключ сортировки по числу в названии: "Поток 9" -> 9, "Поток 10" -> 10.
    Так "Поток 9" идёт раньше "Поток 10" (обычная сортировка строк дала бы наоборот).
    Названия без числа уходят в конец.
    """
    match = re.search(r"\d+", name)
    if match:
        return (0, int(match.group()), name)
    return (1, 0, name)


async def get_active_streams(session) -> list[str]:
    """Потоки, у которых последний дедлайн ещё не прошёл."""
    result = await session.execute(
        select(StreamWeek.stream_name)
        .group_by(StreamWeek.stream_name)
        .having(func.max(StreamWeek.deadline) > datetime.now(timezone.utc))
    )
    names = [row[0] for row in result.all()]
    names.sort(key=stream_sort_key)
    return names


async def get_stream_groups(session, stream_name: str) -> list[Group]:
    """Группы потока в порядке id."""
    result = await session.execute(
        select(Group).where(Group.stream_name == stream_name).order_by(Group.id)
    )
    return list(result.scalars().all())


async def save_student(
    call: CallbackQuery, session, stream_name: str, group_name: str | None
) -> None:
    """Создаём или обновляем ученика. group_name всегда перезаписываем (старая группа обнуляется)."""
    student = await session.get(Student, call.from_user.id)
    if student is None:
        student = Student(telegram_id=call.from_user.id)
        session.add(student)

    student.username = call.from_user.username
    student.full_name = call.from_user.full_name
    student.stream_name = stream_name
    student.group_name = group_name
    # Коммит делает DbSessionMiddleware после обработчика


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    # Повторный /start просто показывает потоки снова — так можно сменить поток и группу
    streams = await get_active_streams(session)
    if not streams:
        await message.answer("😔 Пока нет активных потоков. Следи за анонсами!")
        return

    await message.answer(WELCOME_TEXT, reply_markup=streams_keyboard(streams))


@router.callback_query(F.data.startswith("stream:"))
async def on_stream_selected(call: CallbackQuery, session: AsyncSession) -> None:
    # Поток берём из callback_data, например "stream:Поток 9"
    stream_name = call.data.split(":", 1)[1]

    # Защита от старых кнопок с уже закончившимся потоком
    if stream_name not in await get_active_streams(session):
        await call.answer("Этот поток уже недоступен. Нажми /start", show_alert=True)
        return

    groups = await get_stream_groups(session, stream_name)

    # У потока нет групп — сразу сохраняем ученика без группы
    if not groups:
        await save_student(call, session, stream_name, None)
        await call.message.edit_text(
            f"🎉 Готово: <b>{escape(stream_name)}</b>\n\n"
            f"Жди уведомлений о новых уроках и практиках. Удачи! 🚀"
        )
        await call.answer("✅ Готово!")
        return

    # Группы есть — пока ничего не сохраняем, просим выбрать группу
    await call.message.edit_text(
        f"Поток: <b>{escape(stream_name)}</b>\n\nТеперь выбери свою <b>группу</b>:",
        reply_markup=groups_keyboard(groups),
    )
    await call.answer()


@router.callback_query(F.data == "back:streams")
async def on_back_to_streams(call: CallbackQuery, session: AsyncSession) -> None:
    # Кнопка "‹ Назад" — снова показываем список потоков
    streams = await get_active_streams(session)
    if not streams:
        await call.message.edit_text("😔 Пока нет активных потоков. Следи за анонсами!")
        await call.answer()
        return

    await call.message.edit_text(WELCOME_TEXT, reply_markup=streams_keyboard(streams))
    await call.answer()


@router.callback_query(F.data.startswith("group:"))
async def on_group_selected(call: CallbackQuery, session: AsyncSession) -> None:
    # В callback_data только id группы, например "group:5"
    group_id_text = call.data.split(":", 1)[1]
    if not group_id_text.isdigit():
        await call.answer("Что-то пошло не так. Нажми /start", show_alert=True)
        return

    group = await session.get(Group, int(group_id_text))
    if group is None:
        await call.answer("Эта группа уже недоступна. Нажми /start", show_alert=True)
        return

    # Поток группы тоже должен быть активным (защита от старых кнопок)
    if group.stream_name not in await get_active_streams(session):
        await call.answer("Этот поток уже недоступен. Нажми /start", show_alert=True)
        return

    # Поток берём из самой группы — так поток и группа точно совпадают
    await save_student(call, session, group.stream_name, group.group_name)

    await call.message.edit_text(
        f"🎉 Готово: <b>{escape(group.stream_name)}</b>, группа <b>{escape(group.group_name)}</b>\n\n"
        f"Жди уведомлений о новых уроках и практиках. Удачи! 🚀"
    )
    await call.answer("✅ Готово!")
