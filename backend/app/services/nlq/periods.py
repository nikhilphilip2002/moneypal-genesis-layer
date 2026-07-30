"""Fiscal calendar and relative-period resolution.

The Indian financial year runs 1 April to 31 March and is labelled by its ending year:
FY26 is Apr 2025 - Mar 2026. Almost every reporting question in this domain means the
fiscal year, and almost every user says "year" — which is why `last_year` is deliberately
absent from the vocabulary in contracts.py. A question that says only "last year" is
ambiguous between FY25 and CY2025 and must be clarified, not guessed.

Everything here is pure date arithmetic: no database, no LLM, fully testable.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta

FY_START_MONTH = 4  # April


class PeriodError(ValueError):
    """A period that cannot be resolved to concrete dates."""


@dataclass(frozen=True, slots=True)
class DateRange:
    start: date
    end: date  # inclusive
    label: str

    def __post_init__(self) -> None:
        if self.start > self.end:
            raise PeriodError(f"{self.label}: start {self.start} is after end {self.end}")

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1


# --------------------------------------------------------------------------------------
# Fiscal year helpers
# --------------------------------------------------------------------------------------


def fy_of(day: date) -> int:
    """The fiscal year a date falls in, labelled by its ending year.

    2026-03-31 -> FY26; 2026-04-01 -> FY27.
    """
    return day.year + 1 if day.month >= FY_START_MONTH else day.year


def fy_bounds(fy: int) -> DateRange:
    """FY26 -> 2025-04-01 .. 2026-03-31."""
    return DateRange(date(fy - 1, FY_START_MONTH, 1), date(fy, FY_START_MONTH - 1, 31), f"FY{fy % 100:02d}")


def fy_quarter_of(day: date) -> tuple[int, int]:
    """(fiscal year, fiscal quarter 1-4). Q1 is Apr-Jun."""
    fy = fy_of(day)
    quarter = ((day.month - FY_START_MONTH) % 12) // 3 + 1
    return fy, quarter


def fy_quarter_bounds(fy: int, quarter: int) -> DateRange:
    if not 1 <= quarter <= 4:
        raise PeriodError(f"fiscal quarter must be 1-4, got {quarter}")
    start_month = FY_START_MONTH + (quarter - 1) * 3
    start_year = fy - 1 + (start_month - 1) // 12
    start_month = (start_month - 1) % 12 + 1
    start = date(start_year, start_month, 1)
    end = _add_months(start, 3) - timedelta(days=1)
    return DateRange(start, end, f"Q{quarter} FY{fy % 100:02d}")


def fy_label(fy: int) -> str:
    return f"FY{fy % 100:02d}"


# --------------------------------------------------------------------------------------
# Generic helpers
# --------------------------------------------------------------------------------------


def _add_months(day: date, months: int) -> date:
    month_index = day.month - 1 + months
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def month_bounds(day: date) -> DateRange:
    last = calendar.monthrange(day.year, day.month)[1]
    return DateRange(
        date(day.year, day.month, 1), date(day.year, day.month, last), day.strftime("%b %Y")
    )


def quarter_bounds(day: date) -> DateRange:
    """Calendar quarter — distinct from `fy_quarter_bounds`."""
    first_month = (day.month - 1) // 3 * 3 + 1
    start = date(day.year, first_month, 1)
    end = _add_months(start, 3) - timedelta(days=1)
    return DateRange(start, end, f"Q{(first_month - 1) // 3 + 1} {day.year}")


def week_bounds(day: date) -> DateRange:
    start = day - timedelta(days=day.weekday())
    return DateRange(start, start + timedelta(days=6), f"week of {start.isoformat()}")


# --------------------------------------------------------------------------------------
# Relative period resolution
# --------------------------------------------------------------------------------------


def resolve_relative(relative: str, today: date | None = None) -> DateRange:
    """Turn a closed-vocabulary relative period into concrete dates.

    `today` is injectable so tests are not time-dependent and so a report can be re-run
    "as of" a past date and reproduce its original numbers.
    """
    now = today or date.today()

    if relative == "today":
        return DateRange(now, now, now.isoformat())
    if relative == "yesterday":
        day = now - timedelta(days=1)
        return DateRange(day, day, day.isoformat())
    if relative == "this_month":
        return month_bounds(now)
    if relative == "last_month":
        return month_bounds(date(now.year, now.month, 1) - timedelta(days=1))
    if relative == "this_quarter":
        return quarter_bounds(now)
    if relative == "last_quarter":
        return quarter_bounds(quarter_bounds(now).start - timedelta(days=1))
    if relative == "this_fy":
        return fy_bounds(fy_of(now))
    if relative == "last_fy":
        return fy_bounds(fy_of(now) - 1)
    if relative == "fy_to_date":
        fy = fy_bounds(fy_of(now))
        return DateRange(fy.start, now, f"{fy.label} to date")
    if relative == "ytd":
        return DateRange(date(now.year, 1, 1), now, f"{now.year} to date")
    if relative == "last_12_months":
        return DateRange(_add_months(now, -12) + timedelta(days=1), now, "last 12 months")
    if relative == "last_30_days":
        return DateRange(now - timedelta(days=29), now, "last 30 days")
    if relative == "last_90_days":
        return DateRange(now - timedelta(days=89), now, "last 90 days")
    if relative == "all_time":
        # Bounded rather than open-ended: an unbounded scan of the 260k-row schedule table
        # would also sweep in instalments dated to 2031.
        return DateRange(date(2000, 1, 1), now, "all time")

    raise PeriodError(f"unknown relative period {relative!r}")


def previous_period(current: DateRange, today: date | None = None) -> DateRange:
    """The comparable prior period, for `compare_to` when the user says "vs last year".

    Aligned to the same calendar shape where one is recognisable (a whole month compares to
    the previous whole month) and by equal day count otherwise.
    """
    start, end = current.start, current.end

    # A span of whole months (one month, a quarter, a fiscal year) shifts by that many
    # months, so Q1 compares to Q4 rather than to "the 91 days before Q1" — which lands
    # mid-December and quietly makes every quarter-on-quarter comparison wrong.
    spans_whole_months = start.day == 1 and end == month_bounds(end).end
    if spans_whole_months:
        months = (end.year - start.year) * 12 + end.month - start.month + 1
        prior_start = _add_months(start, -months)
        prior_end = _add_months(start, -1)
        prior_end = month_bounds(prior_end).end
        return DateRange(prior_start, prior_end, "previous period")

    span = current.days
    return DateRange(start - timedelta(days=span), start - timedelta(days=1), "previous period")


# --------------------------------------------------------------------------------------
# SQL grain truncation
# --------------------------------------------------------------------------------------

# date_trunc handles everything except the fiscal grains, which have no native support.
# Shifting the date back three months maps the Indian FY onto the calendar year, so
# Postgres' own year/quarter truncation then does the work.
_TRUNC = {
    "day": "DATE_TRUNC('day', {col})::date",
    "week": "DATE_TRUNC('week', {col})::date",
    "month": "DATE_TRUNC('month', {col})::date",
    "quarter": "DATE_TRUNC('quarter', {col})::date",
    "year": "DATE_TRUNC('year', {col})::date",
    "fy": "(DATE_TRUNC('year', ({col} - INTERVAL '3 months')) + INTERVAL '3 months')::date",
    "fy_quarter": "(DATE_TRUNC('quarter', ({col} - INTERVAL '3 months')) + INTERVAL '3 months')::date",
}


def truncate_sql(grain: str, column: str) -> str:
    """The GROUP BY expression for a time grain."""
    template = _TRUNC.get(grain)
    if template is None:
        raise PeriodError(f"no SQL truncation defined for grain {grain!r}")
    return template.format(col=column)


def format_bucket(grain: str, value: date) -> str:
    """Human label for a truncated time bucket. Fiscal grains get fiscal labels."""
    if not isinstance(value, date):
        return str(value)
    if grain == "day":
        return value.strftime("%d %b %Y")
    if grain == "week":
        return f"w/c {value.strftime('%d %b %Y')}"
    if grain == "month":
        return value.strftime("%b %Y")
    if grain == "quarter":
        return f"Q{(value.month - 1) // 3 + 1} {value.year}"
    if grain == "year":
        return str(value.year)
    if grain == "fy":
        return fy_label(fy_of(value))
    if grain == "fy_quarter":
        fy, quarter = fy_quarter_of(value)
        return f"Q{quarter} {fy_label(fy)}"
    return value.isoformat()
