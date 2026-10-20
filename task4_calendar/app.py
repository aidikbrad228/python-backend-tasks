"""Календарь с возможностью перелистывания месяцев.

Только стандартная библиотека Python 3 — ничего устанавливать не нужно.

Запуск:
    python3 app.py            # http://127.0.0.1:8000
    python3 app.py 8080       # другой порт
"""
import calendar
import os
import sys
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MIN_YEAR, MAX_YEAR = 1, 9999

MONTH_NAMES = [
    "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]
WEEKDAY_NAMES = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

ROWS_CLASS = {4: "fc-four-rows", 5: "fc-five-rows", 6: "fc-six-rows"}


def build_weeks(year: int, month: int) -> list:
    """Сетка месяца: список недель по 7 ячеек (Пн..Вс).

    В ячейке либо номер дня, либо None (пустая ячейка в начале/конце
    месяца, чтобы сетка была ровной). Количество дней в месяце, включая
    февраль високосного года, определяет calendar.monthrange.
    """
    first_weekday, days_in_month = calendar.monthrange(year, month)
    cells = [None] * first_weekday + list(range(1, days_in_month + 1))
    cells += [None] * (-len(cells) % 7)
    return [cells[i:i + 7] for i in range(0, len(cells), 7)]


def shift_month(year: int, month: int, delta: int):
    """Сдвиг на delta месяцев; корректно переходит через декабрь/январь.

    Возвращает (год, месяц) или None, если вышли за поддерживаемые годы.
    """
    index = year * 12 + (month - 1) + delta
    new_year, new_month0 = divmod(index, 12)
    if not MIN_YEAR <= new_year <= MAX_YEAR:
        return None
    return new_year, new_month0 + 1


def parse_period(query: dict, today: date):
    """Берёт ?year=&month= из запроса. При любой ошибке — текущий месяц."""
    try:
        year = int(query["year"][0])
        month = int(query["month"][0])
    except (KeyError, IndexError, ValueError):
        return today.year, today.month
    if not (MIN_YEAR <= year <= MAX_YEAR and 1 <= month <= 12):
        return today.year, today.month
    return year, month