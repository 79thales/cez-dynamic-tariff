"""Default tariff schedules and helpers for user-configured window start times."""

from __future__ import annotations

from dataclasses import dataclass

from .const import (
    CONF_SUMMER_OFFDAY_SCHEDULE,
    CONF_SUMMER_WORKDAY_SCHEDULE,
    CONF_WINTER_OFFDAY_SCHEDULE,
    CONF_WINTER_WORKDAY_SCHEDULE,
)


@dataclass(frozen=True, slots=True)
class TariffWindow:
    """One tariff window during a day."""

    start_minute: int
    end_minute: int
    modifier_percent: int


WINTER_WORKDAY: tuple[TariffWindow, ...] = (
    TariffWindow(0, 180, -10),
    TariffWindow(180, 300, -50),
    TariffWindow(300, 480, 25),
    TariffWindow(480, 660, 10),
    TariffWindow(660, 840, -10),
    TariffWindow(840, 960, 10),
    TariffWindow(960, 1080, -10),
    TariffWindow(1080, 1200, 25),
    TariffWindow(1200, 1380, 10),
    TariffWindow(1380, 1440, -10),
)

WINTER_OFFDAY: tuple[TariffWindow, ...] = (
    TariffWindow(0, 180, -10),
    TariffWindow(180, 300, -50),
    TariffWindow(300, 660, 10),
    TariffWindow(660, 840, -10),
    TariffWindow(840, 960, 10),
    TariffWindow(960, 1080, -10),
    TariffWindow(1080, 1380, 10),
    TariffWindow(1380, 1440, -10),
)

SUMMER_WORKDAY: tuple[TariffWindow, ...] = (
    TariffWindow(0, 180, -10),
    TariffWindow(180, 300, -50),
    TariffWindow(300, 480, 25),
    TariffWindow(480, 660, 10),
    TariffWindow(660, 840, -50),
    TariffWindow(840, 960, 10),
    TariffWindow(960, 1080, -10),
    TariffWindow(1080, 1200, 25),
    TariffWindow(1200, 1380, 10),
    TariffWindow(1380, 1440, -10),
)

SUMMER_OFFDAY: tuple[TariffWindow, ...] = (
    TariffWindow(0, 180, -10),
    TariffWindow(180, 300, -50),
    TariffWindow(300, 660, 10),
    TariffWindow(660, 840, -50),
    TariffWindow(840, 960, 10),
    TariffWindow(960, 1080, -10),
    TariffWindow(1080, 1380, 10),
    TariffWindow(1380, 1440, -10),
)

DEFAULT_SCHEDULES: dict[str, tuple[TariffWindow, ...]] = {
    CONF_WINTER_WORKDAY_SCHEDULE: WINTER_WORKDAY,
    CONF_WINTER_OFFDAY_SCHEDULE: WINTER_OFFDAY,
    CONF_SUMMER_WORKDAY_SCHEDULE: SUMMER_WORKDAY,
    CONF_SUMMER_OFFDAY_SCHEDULE: SUMMER_OFFDAY,
}


def format_schedule_starts(schedule: tuple[TariffWindow, ...]) -> str:
    """Format window starts as a compact value for the options form."""
    return ", ".join(
        f"{window.start_minute // 60:02d}:{window.start_minute % 60:02d}"
        for window in schedule
    )


def parse_schedule_starts(
    value: str,
    default_schedule: tuple[TariffWindow, ...],
) -> tuple[TariffWindow, ...]:
    """Build a schedule from comma-separated HH:MM starts and default modifiers."""
    starts: list[int] = []

    for item in value.split(","):
        hours_text, separator, minutes_text = item.strip().partition(":")
        if not separator or not hours_text.isdigit() or not minutes_text.isdigit():
            raise ValueError("invalid_schedule")

        hours = int(hours_text)
        minutes = int(minutes_text)
        if not 0 <= hours <= 23 or not 0 <= minutes <= 59:
            raise ValueError("invalid_schedule")

        starts.append(hours * 60 + minutes)

    if len(starts) != len(default_schedule):
        raise ValueError("invalid_schedule")
    if not starts or starts[0] != 0 or starts != sorted(set(starts)):
        raise ValueError("invalid_schedule")

    return tuple(
        TariffWindow(
            start_minute=start,
            end_minute=starts[index + 1] if index + 1 < len(starts) else 1440,
            modifier_percent=default_schedule[index].modifier_percent,
        )
        for index, start in enumerate(starts)
    )
