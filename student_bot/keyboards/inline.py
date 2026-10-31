from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from shared.models import Group


def streams_keyboard(stream_names: list[str]) -> InlineKeyboardMarkup:
    """Кнопка на каждый поток, callback_data вида "stream:Поток 9"."""
    builder = InlineKeyboardBuilder()
    for name in stream_names:
        builder.button(text=name, callback_data=f"stream:{name}")
    builder.adjust(1)
    return builder.as_markup()


def groups_keyboard(groups: list[Group]) -> InlineKeyboardMarkup:
    """
    Кнопка на каждую группу + "‹ Назад".
    В callback_data кладём только id группы ("group:5"),
    потому что Telegram разрешает максимум 64 байта, а кириллица занимает по 2 байта.
    """
    builder = InlineKeyboardBuilder()
    for group in groups:
        builder.button(text=group.group_name, callback_data=f"group:{group.id}")
    builder.button(text="‹ Назад", callback_data="back:streams")
    builder.adjust(1)
    return builder.as_markup()
