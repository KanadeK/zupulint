"""Backward-compatible date-normalization imports.

New integrations should import from :mod:`zupulint.normalizers`.
"""

from zupulint.normalizers import DatePrecision, DateQualifier, parse_date, year_delta

__all__ = ["DatePrecision", "DateQualifier", "parse_date", "year_delta"]
