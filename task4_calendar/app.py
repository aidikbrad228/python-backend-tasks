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


def _nav_link(css_class: str, target) -> str:
    if target is None:
        return f'<a class="custom-btn {css_class}"></a>'
    year, month = target
    return (f'<a href="/?year={year}&amp;month={month}" '
            f'class="custom-btn {css_class}"></a>')


def render_page(year: int, month: int, today: date) -> str:
    weeks = build_weeks(year, month)
    is_current_month = (year, month) == (today.year, today.month)

    rows_html = []
    for week in weeks:
        cells = []
        for column, day in enumerate(week):
            if day is None:
                cells.append("<div></div>")
                continue
            classes = []
            if column >= 5:
                classes.append("fc-weekend")
            if is_current_month and day == today.day:
                classes.append("fc-today")
            class_attr = f' class="{" ".join(classes)}"' if classes else ""
            cells.append(f'<div{class_attr}><span class="fc-date">{day}</span></div>')
        rows_html.append('<div class="fc-row">' + "".join(cells) + "</div>")

    head_html = "".join(f"<div>{name}</div>" for name in WEEKDAY_NAMES)
    prev_link = _nav_link("custom-prev", shift_month(year, month, -1))
    next_link = _nav_link("custom-next", shift_month(year, month, +1))

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Календарь — {MONTH_NAMES[month]} {year}</title>
    <link rel="stylesheet" href="/calendar.css">
</head>
<body>
    <div class="custom-calendar-wrap">
        <div class="custom-inner">
            <div class="custom-header clearfix">
                <nav>
                    {prev_link}
                    {next_link}
                </nav>
                <h2 id="custom-month" class="custom-month">{MONTH_NAMES[month]}</h2>
                <h3 id="custom-year" class="custom-year">{year}</h3>
            </div>
            <div id="calendar" class="fc-calendar-container">
                <div class="fc-calendar {ROWS_CLASS[len(weeks)]}">
                    <div class="fc-head">{head_html}</div>
                    <div class="fc-body">
                        {"".join(rows_html)}
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""