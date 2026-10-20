import re
import threading
import unittest
import urllib.error
import urllib.request
from datetime import date

import app


class WeeksTest(unittest.TestCase):
    def days(self, year, month):
        return [d for week in app.build_weeks(year, month) for d in week if d]

    def test_leap_february(self):
        self.assertEqual(len(self.days(2024, 2)), 29)
        self.assertEqual(len(self.days(2023, 2)), 28)
        self.assertEqual(len(self.days(1900, 2)), 28)
        self.assertEqual(len(self.days(2000, 2)), 29)

    def test_all_months_all_days_in_order_and_grid_is_rectangular(self):
        for year in (2023, 2024, 2026):
            for month in range(1, 13):
                weeks = app.build_weeks(year, month)
                self.assertTrue(all(len(w) == 7 for w in weeks))
                self.assertIn(len(weeks), (4, 5, 6))
                self.assertEqual(self.days(year, month),
                                 list(range(1, len(self.days(year, month)) + 1)))

    def test_week_starts_on_monday(self):
        
        first = app.build_weeks(2026, 10)[0]
        self.assertEqual(first[:4], [None, None, None, 1])

    def test_row_counts(self):
        self.assertEqual(len(app.build_weeks(2021, 2)), 4)
        self.assertEqual(len(app.build_weeks(2026, 10)), 5)
        self.assertEqual(len(app.build_weeks(2025, 3)), 6)


class ShiftTest(unittest.TestCase):
    def test_december_to_january(self):
        self.assertEqual(app.shift_month(2025, 12, +1), (2026, 1))

    def test_january_to_december(self):
        self.assertEqual(app.shift_month(2026, 1, -1), (2025, 12))

    def test_regular(self):
        self.assertEqual(app.shift_month(2026, 10, +1), (2026, 11))
        self.assertEqual(app.shift_month(2026, 10, -1), (2026, 9))

    def test_bounds(self):
        self.assertIsNone(app.shift_month(1, 1, -1))
        self.assertIsNone(app.shift_month(9999, 12, +1))


class ParseTest(unittest.TestCase):
    today = date(2026, 10, 19)

    def test_valid(self):
        self.assertEqual(app.parse_period({"year": ["2024"], "month": ["2"]}, self.today), (2024, 2))

    def test_invalid_falls_back_to_today(self):
        for q in ({}, {"year": ["2024"]}, {"month": ["5"]},
                  {"year": ["abc"], "month": ["1"]},
                  {"year": ["2024"], "month": ["13"]},
                  {"year": ["2024"], "month": ["0"]},
                  {"year": ["0"], "month": ["1"]},
                  {"year": ["10000"], "month": ["1"]}):
            self.assertEqual(app.parse_period(q, self.today), (2026, 10), q)


class RenderTest(unittest.TestCase):
    today = date(2026, 10, 19)

    def test_header_and_weekdays(self):
        html = app.render_page(2026, 10, self.today)
        self.assertIn(">Октябрь</h2>", html)
        self.assertIn(">2026</h3>", html)
        for name in ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"):
            self.assertIn(f"<div>{name}</div>", html)

    def test_today_highlighted_only_in_current_month(self):
        html = app.render_page(2026, 10, self.today)
        self.assertEqual(html.count("fc-today"), 1)
        self.assertIn('<div class="fc-today"><span class="fc-date">19</span>', html)
        self.assertNotIn("fc-today", app.render_page(2026, 11, self.today))
        self.assertNotIn("fc-today", app.render_page(2025, 10, self.today))

    def test_weekends(self):
        html = app.render_page(2026, 10, self.today)
        self.assertEqual(html.count("fc-weekend"), 9)

    def test_today_on_weekend_keeps_both_classes(self):
        html = app.render_page(2026, 10, date(2026, 10, 17))
        self.assertIn('class="fc-weekend fc-today"', html)

    def test_day_count_in_html(self):
        for month, expected in ((2, 29), (4, 30), (12, 31)):
            html = app.render_page(2024, month, self.today)
            self.assertEqual(len(re.findall(r'<span class="fc-date">\d+</span>', html)), expected)

    def test_navigation_links_across_year_boundary(self):
        html = app.render_page(2026, 1, self.today)
        self.assertIn('href="/?year=2025&amp;month=12"', html)
        self.assertIn('href="/?year=2026&amp;month=2"', html)
        html = app.render_page(2025, 12, self.today)
        self.assertIn('href="/?year=2026&amp;month=1"', html)

    def test_row_class_matches_week_count(self):
        self.assertIn("fc-four-rows", app.render_page(2021, 2, self.today))
        self.assertIn("fc-five-rows", app.render_page(2026, 10, self.today))
        self.assertIn("fc-six-rows", app.render_page(2025, 3, self.today))

    def test_bounds_have_inactive_arrow(self):
        html = app.render_page(1, 1, self.today)
        self.assertIn('<a class="custom-btn custom-prev"></a>', html)


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = app.make_server(port=0)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def get(self, path):
        with urllib.request.urlopen(self.base + path) as r:
            return r.status, r.headers, r.read()

    def test_default_page_is_current_month(self):
        status, _, body = self.get("/")
        today = date.today()
        text = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn(f">{app.MONTH_NAMES[today.month]}</h2>", text)
        self.assertIn(f">{today.year}</h3>", text)
        self.assertEqual(text.count("fc-today"), 1)

    def test_paging(self):
        _, _, body = self.get("/?year=2024&month=2")
        self.assertIn(">Февраль</h2>", body.decode("utf-8"))

    def test_garbage_query_does_not_crash(self):
        status, _, body = self.get("/?year=%27%3Cscript%3E&month=zzz")
        self.assertEqual(status, 200)
        self.assertNotIn("<script>", body.decode("utf-8"))

    def test_static_and_404(self):
        status, headers, _ = self.get("/calendar.css")
        self.assertEqual(status, 200)
        self.assertIn("text/css", headers["Content-Type"])
        self.assertEqual(self.get("/fonts/fontawesome-selected.woff")[0], 200)
        for bad in ("/app.py", "/../app.py", "/fonts/../app.py", "/nope"):
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                self.get(bad)
            self.assertEqual(ctx.exception.code, 404, bad)


if __name__ == "__main__":
    unittest.main(verbosity=1)
