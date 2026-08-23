"""Default tariff schedules and helpers for user-configured tariff bands."""

from __future__ import annotations

import re
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


def format_schedule(schedule: tuple[TariffWindow, ...]) -> str:
    """Format a complete schedule for the options form."""
    return ", ".join(
        f"{window.start_minute // 60:02d}:{window.start_minute % 60:02d}="
        f"{window.modifier_percent:+d}"
        for window in schedule
    )


def parse_schedule(
    value: str,
    default_schedule: tuple[TariffWindow, ...],
) -> tuple[TariffWindow, ...]:
    """Parse a complete schedule while accepting the legacy starts-only format."""
    items = [item.strip() for item in re.split(r"[,;\n]+", value) if item.strip()]
    if not items:
        raise ValueError("invalid_schedule")

    has_modifiers = ["=" in item for item in items]
    if any(has_modifiers) and not all(has_modifiers):
        raise ValueError("invalid_schedule")

    complete_format = all(has_modifiers)
    starts: list[int] = []
    modifiers: list[int] = []

    for item in items:
        time_text = item.partition("=")[0]
        hours_text, separator, minutes_text = time_text.strip().partition(":")
        if not separator or not hours_text.isdigit() or not minutes_text.isdigit():
            raise ValueError("invalid_schedule")

        hours = int(hours_text)
        minutes = int(minutes_text)
        if not 0 <= hours <= 23 or not 0 <= minutes <= 59:
            raise ValueError("invalid_schedule")

        starts.append(hours * 60 + minutes)

    if not starts or starts[0] != 0 or starts != sorted(set(starts)):
        raise ValueError("invalid_schedule")

    if complete_format:
        for item in items:
            _, _, modifier_text = item.partition("=")
            try:
                modifiers.append(int(modifier_text.strip()))
            except ValueError as err:
                raise ValueError("invalid_schedule") from err
    else:
        if len(starts) != len(default_schedule):
            raise ValueError("invalid_schedule")
        modifiers = [window.modifier_percent for window in default_schedule]

    return tuple(
        TariffWindow(
            start_minute=start,
            end_minute=starts[index + 1] if index + 1 < len(starts) else 1440,
            modifier_percent=modifiers[index],
        )
        for index, start in enumerate(starts)
    )
