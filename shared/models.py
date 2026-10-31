"""
Модели таблиц Supabase.
Таблицы создаются вручную в Supabase, здесь только описание для чтения/записи.
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger, Date, DateTime, Integer, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Student(Base):
    """Ученик бота. Привязан только к потоку."""
    __tablename__ = "students"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    stream_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class StreamWeek(Base):
    """Неделя потока с готовыми датами."""
    __tablename__ = "stream_weeks"
    __table_args__ = (UniqueConstraint("stream_name", "week_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stream_name: Mapped[str] = mapped_column(String)
    week_number: Mapped[int] = mapped_column(Integer)
    week_date: Mapped[date] = mapped_column(Date)
    announce_date: Mapped[date] = mapped_column(Date)
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CalendarEvent(Base):
    """Событие недели: 'interactive' или 'test'."""
    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stream_name: Mapped[str] = mapped_column(String)
    week_number: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)


class Lesson(Base):
    """Урок курса. Номер недели общий для всех потоков."""
    __tablename__ = "lessons"

    lesson_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    week_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String)


class Quote(Base):
    """Цитата. week_number = NULL значит подходит любой неделе."""
    __tablename__ = "quotes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    week_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    author: Mapped[str] = mapped_column(String)
    text: Mapped[str] = mapped_column(Text)


class TomirisPractice(Base):
    """Практика с Томирис для потока."""
    __tablename__ = "tomiris_practices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stream_name: Mapped[str] = mapped_column(String)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TomirisReminderSent(Base):
    """Какие напоминания о практике Томирис уже отправлены."""
    __tablename__ = "tomiris_reminders_sent"
    __table_args__ = (UniqueConstraint("stream_name", "scheduled_at", "label"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stream_name: Mapped[str] = mapped_column(String)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    label: Mapped[str] = mapped_column(String)
