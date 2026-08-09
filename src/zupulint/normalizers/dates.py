"""Lossless GEDCOM and tabular date normalization."""

from __future__ import annotations

import re
from datetime import date
from typing import Literal

from dateutil import parser

from zupulint.models import GenealogyDate

GEDCOM_MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}


DatePrecision = Literal["unknown", "year", "month", "day", "range", "unparsed"]
DateQualifier = Literal[
    "exact", "about", "calculated", "estimated", "before", "after", "between", "unknown"
]


def year_delta(start: date, end: date) -> int:
    """Return completed calendar years between two normalized dates."""

    return end.year - start.year - ((end.month, end.day) < (start.month, start.day))


def _single_date(text: str) -> tuple[date | None, DatePrecision]:
    year = re.fullmatch(r"(\d{3,4})", text)
    if year:
        return date(int(year.group(1)), 1, 1), "year"
    month = re.fullmatch(r"(\d{4})[-/](\d{1,2})", text)
    if month:
        return date(int(month.group(1)), int(month.group(2)), 1), "month"
    ged_month = re.fullmatch(r"(?:(\d{1,2})\s+)?([A-Z]{3})\s+(\d{3,4})", text, re.I)
    if ged_month and ged_month.group(2).upper() in GEDCOM_MONTHS:
        return (
            date(
                int(ged_month.group(3)),
                GEDCOM_MONTHS[ged_month.group(2).upper()],
                int(ged_month.group(1) or 1),
            ),
            "day" if ged_month.group(1) else "month",
        )
    try:
        return parser.parse(text, dayfirst=True).date(), "day"
    except (OverflowError, TypeError, ValueError):
        return None, "unparsed"


def parse_date(raw: object) -> GenealogyDate:
    """Parse common exact, approximate, bounded, and ranged genealogy dates.

    The original text is always retained, including unsupported traditional-era
    strings, so callers can report uncertainty without silently discarding evidence.
    """

    if raw is None or str(raw).strip() == "":
        return GenealogyDate(raw=None, value=None, precision="unknown", qualifier="unknown")
    if isinstance(raw, date):
        return GenealogyDate(raw=raw.isoformat(), value=raw, precision="day", qualifier="exact")

    text = str(raw).strip()
    qualifier_match = re.match(r"^(ABT|CAL|EST|BEF|AFT)\s+(.+)$", text, re.I)
    qualifier_map: dict[str, DateQualifier] = {
        "ABT": "about",
        "CAL": "calculated",
        "EST": "estimated",
        "BEF": "before",
        "AFT": "after",
    }
    if qualifier_match:
        value, precision = _single_date(qualifier_match.group(2).strip())
        return GenealogyDate(
            raw=text,
            value=value,
            precision=precision,
            qualifier=qualifier_map[qualifier_match.group(1).upper()],
        )

    between = re.match(r"^(?:BET)\s+(.+?)\s+(?:AND)\s+(.+)$", text, re.I)
    from_to = re.match(r"^(?:FROM)\s+(.+?)\s+(?:TO)\s+(.+)$", text, re.I)
    numeric_range = re.match(r"^(\d{3,4})\s*[-–]\s*(\d{3,4})$", text)
    range_match = between or from_to
    if range_match:
        start, _ = _single_date(range_match.group(1).strip())
        end, _ = _single_date(range_match.group(2).strip())
        return GenealogyDate(
            raw=text,
            value=start,
            end_value=end,
            precision="range" if start and end else "unparsed",
            qualifier="between",
        )
    if numeric_range:
        start = date(int(numeric_range.group(1)), 1, 1)
        end = date(int(numeric_range.group(2)), 1, 1)
        return GenealogyDate(
            raw=text, value=start, end_value=end, precision="range", qualifier="between"
        )

    value, precision = _single_date(text)
    return GenealogyDate(
        raw=text,
        value=value,
        precision=precision,
        qualifier="exact" if value else "unknown",
    )
