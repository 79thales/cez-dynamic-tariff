from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

import holidays
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BASE_PRICE_KWH,
    CONF_CHEAP_THRESHOLD,
    CONF_EXPENSIVE_THRESHOLD,
    CONF_INCLUDE_HOLIDAYS,
    CONF_NAME,
    CONF_SUMMER_OFFDAY_SCHEDULE,
    CONF_SUMMER_WORKDAY_SCHEDULE,
    CONF_SUPER_CHEAP_THRESHOLD,
    CONF_WINTER_OFFDAY_SCHEDULE,
    CONF_WINTER_WORKDAY_SCHEDULE,
    DEFAULT_BASE_PRICE_KWH,
    DEFAULT_CHEAP_THRESHOLD,
    DEFAULT_EXPENSIVE_THRESHOLD,
    DEFAULT_INCLUDE_HOLIDAYS,
    DEFAULT_NAME,
    DEFAULT_SUPER_CHEAP_THRESHOLD,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
    DOMAIN,
)
from .schedule import DEFAULT_SCHEDULES, TariffWindow, parse_schedule

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TariffSnapshot:
    """Calculated tariff state."""

    current_modifier_percent: int
    current_band: str
    current_window_start: str
    current_window_end: str
    season: str
    day_type: str
    is_holiday: bool
    cheap_threshold_percent: int
    super_cheap_threshold_percent: int
    expensive_now: bool
    base_price_kwh: float
    effective_price_kwh: float | None
    next_cheap_start: datetime | None
    next_cheap_end: datetime | None
    next_cheap_modifier_percent: int | None
    today_map_code: str
    today_schedule: list[dict[str, Any]]
    today_display_map: str
    legend: list[dict[str, str]]


class CezDynamicTariffCoordinator(DataUpdateCoordinator[TariffSnapshot]):
    """Coordinator that calculates the current tariff state."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        self.entry = entry
        self._holidays = None

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL_SECONDS),
        )

    def _local_tz(self):
        """Return the configured Home Assistant timezone."""
        timezone = dt_util.get_time_zone(str(self.hass.config.time_zone))
        if timezone is None:
            return dt_util.DEFAULT_TIME_ZONE
        return timezone

    def _option(self, key: str, default):
        """Read option with fallback to config entry data."""
        if key in self.entry.options:
            return self.entry.options[key]
        if key in self.entry.data:
            return self.entry.data[key]
        return default

    def _is_holiday(self, day: date) -> bool:
        """Return True if the day is a Czech public holiday."""
        include_holidays = bool(self._option(CONF_INCLUDE_HOLIDAYS, DEFAULT_INCLUDE_HOLIDAYS))
        if not include_holidays:
            return False
        if self._holidays is None:
            return False
        return day in self._holidays

    @staticmethod
    def _is_summer(day: date) -> bool:
        """Return True for April-September."""
        return 4 <= day.month <= 9

    def _is_offday(self, day: date) -> bool:
        """Return True for weekend or holiday."""
        return day.weekday() >= 5 or self._is_holiday(day)

    def _schedule_from_option(
        self,
        option: str,
        default_schedule: tuple[TariffWindow, ...],
    ) -> tuple[TariffWindow, ...]:
        """Read a custom schedule, falling back safely to the project default."""
        value = self._option(option, None)
        if not isinstance(value, str):
            return default_schedule

        try:
            return parse_schedule(value, default_schedule)
        except ValueError:
            _LOGGER.warning("Ignoring invalid saved tariff schedule: %s", option)
            return default_schedule

    def _schedule_for_day(self, day: date) -> tuple[TariffWindow, ...]:
        """Return the correct schedule for the given day."""
        if self._is_summer(day):
            option = (
                CONF_SUMMER_OFFDAY_SCHEDULE
                if self._is_offday(day)
                else CONF_SUMMER_WORKDAY_SCHEDULE
            )
        else:
            option = (
                CONF_WINTER_OFFDAY_SCHEDULE
                if self._is_offday(day)
                else CONF_WINTER_WORKDAY_SCHEDULE
            )

        return self._schedule_from_option(option, DEFAULT_SCHEDULES[option])

    @staticmethod
    def _minute_of_day(when: datetime) -> int:
        """Return minute-of-day."""
        return when.hour * 60 + when.minute

    @staticmethod
    def _format_minute(value: int) -> str:
        """Format minute-of-day as HH:MM."""
        if value == 1440:
            return "00:00"
        return f"{value // 60:02d}:{value % 60:02d}"

    def _window_to_datetimes(self, day: date, window: TariffWindow) -> tuple[datetime, datetime]:
        """Convert a tariff window into local datetimes."""
        tzinfo = self._local_tz()

        start_day = day
        start_minute = window.start_minute

        end_day = day
        end_minute = window.end_minute
        if end_minute >= 1440:
            end_day = day + timedelta(days=1)
            end_minute -= 1440

        start_dt = datetime.combine(
            start_day,
            time(start_minute // 60, start_minute % 60),
            tzinfo=tzinfo,
        )
        end_dt = datetime.combine(
            end_day,
            time(end_minute // 60, end_minute % 60),
            tzinfo=tzinfo,
        )

        return start_dt, end_dt

    @staticmethod
    def _modifier_style(
        modifier_percent: int,
        super_cheap_threshold: int,
        cheap_threshold: int,
        expensive_threshold: int,
    ) -> tuple[str, str]:
        """Return display token and semantic level for a modifier."""
        if modifier_percent <= super_cheap_threshold:
            return "🟢", "super_cheap"
        if modifier_percent <= cheap_threshold:
            return "🟩", "cheap"
        if modifier_percent < expensive_threshold:
            return "▫️", "normal"
        if modifier_percent == expensive_threshold:
            return "⬜", "expensive"
        return "◻️", "very_expensive"

    def _serialize_schedule(
        self,
        schedule: tuple[TariffWindow, ...],
        super_cheap_threshold: int,
        cheap_threshold: int,
        expensive_threshold: int,
    ) -> list[dict[str, Any]]:
        """Convert a daily schedule into Lovelace-friendly dictionaries."""
        items: list[dict[str, Any]] = []

        for window in schedule:
            token, level = self._modifier_style(
                window.modifier_percent,
                super_cheap_threshold,
                cheap_threshold,
                expensive_threshold,
            )
            modifier_label = f"{window.modifier_percent:+d} %"
            items.append(
                {
                    "start": self._format_minute(window.start_minute),
                    "end": self._format_minute(window.end_minute),
                    "modifier_percent": window.modifier_percent,
                    "level": level,
                    "token": token,
                    "label": (
                        f"{token} {self._format_minute(window.start_minute)}-"
                        f"{self._format_minute(window.end_minute)} ({modifier_label})"
                    ),
                }
            )

        return items

    def _display_map(
        self,
        schedule: tuple[TariffWindow, ...],
        super_cheap_threshold: int,
        cheap_threshold: int,
        expensive_threshold: int,
    ) -> str:
        """Render a compact one-line map for Markdown cards."""
        parts: list[str] = []

        for window in schedule:
            token, _ = self._modifier_style(
                window.modifier_percent,
                super_cheap_threshold,
                cheap_threshold,
                expensive_threshold,
            )
            parts.append(
                f"`{token} {self._format_minute(window.start_minute)}-"
                f"{self._format_minute(window.end_minute)} "
                f"({window.modifier_percent:+d} %)`"
            )

        return " ".join(parts)

    def _legend(
        self,
        schedule: tuple[TariffWindow, ...],
        super_cheap_threshold: int,
        cheap_threshold: int,
        expensive_threshold: int,
    ) -> list[dict[str, str]]:
        """Build a legend from all modifiers present in today's schedule."""
        legend: list[dict[str, str]] = []
        for modifier_percent in sorted({window.modifier_percent for window in schedule}):
            token, level = self._modifier_style(
                modifier_percent,
                super_cheap_threshold,
                cheap_threshold,
                expensive_threshold,
            )
            legend.append(
                {
                    "token": token,
                    "level": level,
                    "label": level.replace("_", " "),
                    "modifier_percent": f"{modifier_percent:+d}",
                }
            )
        return legend

    def _current_window(self, when: datetime) -> TariffWindow:
        """Return the currently active tariff window."""
        minute = self._minute_of_day(when)
        schedule = self._schedule_for_day(when.date())

        for window in schedule:
            if window.start_minute <= minute < window.end_minute:
                return window

        return schedule[-1]

    def _next_matching_window(
        self,
        when: datetime,
        threshold: int,
    ) -> tuple[datetime | None, datetime | None, int | None]:
        """Find current or next tariff window matching the threshold."""
        for offset in range(8):
            day = when.date() + timedelta(days=offset)
            schedule = self._schedule_for_day(day)

            for window in schedule:
                if window.modifier_percent > threshold:
                    continue

                start_dt, end_dt = self._window_to_datetimes(day, window)
                if start_dt <= when:
                    continue

                return start_dt, end_dt, window.modifier_percent

        return None, None, None

    async def _async_update_data(self) -> TariffSnapshot:
        """Calculate the current tariff state."""
        if self._holidays is None:
            self._holidays = await self.hass.async_add_executor_job(
                holidays.country_holidays,
                "CZ",
            )

        now = dt_util.now()
        current_window = self._current_window(now)

        season = "Letní" if self._is_summer(now.date()) else "Zimní"
        is_holiday = self._is_holiday(now.date())
        day_type = "Víkend nebo Svátek" if self._is_offday(now.date()) else "Pracovní den"
        schedule = self._schedule_for_day(now.date())

        cheap_threshold = int(self._option(CONF_CHEAP_THRESHOLD, DEFAULT_CHEAP_THRESHOLD))
        super_cheap_threshold = int(
            self._option(CONF_SUPER_CHEAP_THRESHOLD, DEFAULT_SUPER_CHEAP_THRESHOLD)
        )
        expensive_threshold = int(
            self._option(CONF_EXPENSIVE_THRESHOLD, DEFAULT_EXPENSIVE_THRESHOLD)
        )
        base_price_kwh = float(self._option(CONF_BASE_PRICE_KWH, DEFAULT_BASE_PRICE_KWH))

        current_modifier_percent = current_window.modifier_percent
        current_window_start = self._format_minute(current_window.start_minute)
        current_window_end = self._format_minute(current_window.end_minute)
        current_band = f"{current_window_start}-{current_window_end}"

        effective_price_kwh = None
        if base_price_kwh > 0:
            effective_price_kwh = round(
                base_price_kwh * (1 + (current_modifier_percent / 100)),
                4,
            )

        next_cheap_start, next_cheap_end, next_cheap_modifier_percent = self._next_matching_window(
            now,
            cheap_threshold,
        )

        today_map_code = (
            "summer_workday"
            if self._is_summer(now.date()) and not self._is_offday(now.date())
            else "summer_weekend_or_holiday"
            if self._is_summer(now.date())
            else "winter_workday"
            if not self._is_offday(now.date())
            else "winter_weekend_or_holiday"
        )

        return TariffSnapshot(
            current_modifier_percent=current_modifier_percent,
            current_band=current_band,
            current_window_start=current_window_start,
            current_window_end=current_window_end,
            season=season,
            day_type=day_type,
            is_holiday=is_holiday,
            cheap_threshold_percent=cheap_threshold,
            super_cheap_threshold_percent=super_cheap_threshold,
            expensive_now=current_modifier_percent >= expensive_threshold,
            base_price_kwh=base_price_kwh,
            effective_price_kwh=effective_price_kwh,
            next_cheap_start=next_cheap_start,
            next_cheap_end=next_cheap_end,
            next_cheap_modifier_percent=next_cheap_modifier_percent,
            today_map_code=today_map_code,
            today_schedule=self._serialize_schedule(
                schedule,
                super_cheap_threshold,
                cheap_threshold,
                expensive_threshold,
            ),
            today_display_map=self._display_map(
                schedule,
                super_cheap_threshold,
                cheap_threshold,
                expensive_threshold,
            ),
            legend=self._legend(
                schedule,
                super_cheap_threshold,
                cheap_threshold,
                expensive_threshold,
            ),
        )

    @property
    def title(self) -> str:
        """Return coordinator title."""
        return str(self.entry.data.get(CONF_NAME, DEFAULT_NAME))
