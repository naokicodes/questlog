from datetime import date, datetime

from app.days import day_for, week_start


def test_day_rolls_over_at_4am():
    assert day_for(datetime(2026, 10, 13, 3, 59), 4) == date(2026, 10, 12)
    assert day_for(datetime(2026, 10, 13, 4, 0), 4) == date(2026, 10, 13)


def test_week_starts_monday():
    assert week_start(date(2026, 10, 18)) == date(2026, 10, 12)  # Sunday -> Monday
    assert week_start(date(2026, 10, 12)) == date(2026, 10, 12)
