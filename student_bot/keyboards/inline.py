from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def streams_keyboard(stream_names: list[str]) -> InlineKeyboardMarkup:
    """Кнопка на каждый поток, callback_data вида "stream:Поток 9"."""
    builder = InlineKeyboardBuilder()
    for name in stream_names:
        builder.button(text=name, callback_data=f"stream:{name}")
    builder.adjust(1)
    return builder.as_markup()
