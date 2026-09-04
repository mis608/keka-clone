"""Office wall clock for Ekkaa HRMS.

Attendance is wall-clock business: "I clocked in at 11:04" has to read 11:04 in the office's own
timezone. Web dynos (Railway, Render, Fly, a plain Docker host, most VPS images) run their OS clock
in UTC, so ``datetime.now()`` writes 05:34 into a TIME column and every punch looks five and a half
hours early in the cloud while behaving perfectly on a laptop in India. ``app.py`` and ``mock_data.py``
both take their date and time from here, so the seeded demo rows and the live "today" queries agree
even between midnight and 05:30 IST, when the UTC and IST calendars are a whole day apart.

Set ``APP_TIMEZONE`` to an IANA name (``Asia/Kolkata``) or to a fixed offset (``+05:30``) on a host
with no tz database - which includes Windows boxes that have not installed the ``tzdata`` wheel.
"""
import os
import re
from datetime import datetime, timedelta, timezone

APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Kolkata")


def _resolve(spec):
    """Return (tzinfo, label). Never raises: a bad zone degrades to UTC and says so in the label."""
    match = re.fullmatch(r"([+-])(\d{1,2}):?(\d{2})", (spec or "").strip())
    if match:
        delta = timedelta(hours=int(match.group(2)), minutes=int(match.group(3)))
        return timezone(delta if match.group(1) == "+" else -delta), spec
    try:
        from zoneinfo import ZoneInfo          # needs the tzdata wheel on Windows
        return ZoneInfo(spec), spec
    except Exception:                          # noqa: BLE001 - missing zone must not kill the app
        return (timezone.utc,
                f"{spec} (zone not found -> UTC; install tzdata or set APP_TIMEZONE=+05:30)")


TZ, TZ_LABEL = _resolve(APP_TIMEZONE)


def now_local():
    """The office wall clock, tz-aware. Do not use datetime.now() for anything a person reads."""
    return datetime.now(TZ)


def today():
    """The office's calendar day - what "today" means on attendance, payslips and trend charts."""
    return now_local().date()


def offset_minutes():
    """Minutes ahead (+) or behind (-) UTC, for /api/health and for debugging a deployment."""
    return round(now_local().utcoffset().total_seconds() / 60)
