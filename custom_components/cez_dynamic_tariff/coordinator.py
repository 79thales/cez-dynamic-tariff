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
    CONF_VERY_EXPENSIVE_THRESHOLD,
    CONF_WINTER_OFFDAY_SCHEDULE,
    CONF_WINTER_WORKDAY_SCHEDULE,
    DEFAULT_BASE_PRICE_KWH,
    DEFAULT_CHEAP_THRESHOLD,
    DEFAULT_EXPENSIVE_THRESHOLD,
    DEFAULT_INCLUDE_HOLIDAYS,
    DEFAULT_NAME,
    DEFAULT_SCHEDULE_REVISION,
    DEFAULT_SCHEDULE_SOURCE_URL,
    DEFAULT_SUPER_CHEAP_THRESHOLD,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
    DEFAULT_VERY_EXPENSIVE_THRESHOLD,
    DOMAIN,
)
from .schedule import DEFAULT_SCHEDULES, TariffWindow, classify_modifier, parse_schedule

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TariffSnapshot:
    """Calculated tariff state."""

    current_modifier_percent: int
    current_band: str
    current_window_start: str
    current_window_end: str
    season: str
    season_code: str
    day_type: str
    day_type_code: str
    is_holiday: bool
    cheap_threshold_percent: int
    super_cheap_threshold_percent: int
    expensive_threshold_percent: int
    very_expensive_threshold_percent: int
    cheap_now: bool
    super_cheap_now: bool
    expensive_now: bool
    very_expensive_now: bool
    base_price_kwh: float
    effective_price_kwh: float | None
    next_cheap_start: datetime | None
    next_cheap_end: datetime | None
    next_cheap_modifier_percent: int | None
    next_change: datetime | None
    next_modifier_percent: int | None
    today_map_code: str
    today_schedule_revision: str
    today_schedule_source_url: str | None
    today_schedule: list[dict[str, Any]]
    today_display_map: str
    today_legend: list[dict[str, str]]
    tomorrow_map_code: str
    tomorrow_schedule_revision: str
    tomorrow_schedule_source_url: str | None
    tomorrow_schedule: list[dict[str, Any]]
    tomorrow_display_map: str
    tomorrow_legend: list[dict[str, str]]
    tomorrow_season: str
    tomorrow_season_code: str
    tomorrow_day_type: str
    tomorrow_day_type_code: str


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

    @classmethod
    def _season_code(cls, day: date) -> str:
        """Return a stable machine-readable season code."""
        return "summer" if cls._is_summer(day) else "winter"

    def _day_type_code(self, day: date) -> str:
        """Return a stable machine-readable day type code."""
        return "weekend_or_holiday" if self._is_offday(day) else "workday"

    @classmethod
    def _season_label(cls, day: date) -> str:
        """Return the backward-compatible Czech season label."""
        return "Letní" if cls._is_summer(day) else "Zimní"

    def _day_type_label(self, day: date) -> str:
        """Return the backward-compatible Czech day type label."""
        return "Víkend nebo Svátek" if self._is_offday(day) else "Pracovní den"

    def _map_code(self, day: date) -> str:
        """Return a stable code describing the schedule used for a day."""
        return f"{self._season_code(day)}_{self._day_type_code(day)}"

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

    def _schedule_option_for_day(self, day: date) -> str:
        """Return the config option containing the schedule for a day."""
        if self._is_summer(day):
            return (
                CONF_SUMMER_OFFDAY_SCHEDULE
                if self._is_offday(day)
                else CONF_SUMMER_WORKDAY_SCHEDULE
            )
        return (
            CONF_WINTER_OFFDAY_SCHEDULE
            if self._is_offday(day)
            else CONF_WINTER_WORKDAY_SCHEDULE
        )

    def _schedule_for_day(self, day: date) -> tuple[TariffWindow, ...]:
        """Return the correct schedule for the given day."""
        option = self._schedule_option_for_day(day)

        return self._schedule_from_option(option, DEFAULT_SCHEDULES[option])

    def _schedule_metadata_for_day(self, day: date) -> tuple[str, str | None]:
        """Return provenance for the schedule selected for a day."""
        option = self._schedule_option_for_day(day)
        if isinstance(self._option(option, None), str):
            return "custom", None
        return DEFAULT_SCHEDULE_REVISION, DEFAULT_SCHEDULE_SOURCE_URL

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
        very_expensive_threshold: int,
    ) -> tuple[str, str]:
        """Return display token and semantic level for a modifier."""
        level = classify_modifier(
            modifier_percent,
            super_cheap_threshold,
            cheap_threshold,
            expensive_threshold,
            very_expensive_threshold,
        )
        token = {
            "super_cheap": "🟢",
            "cheap": "🟩",
            "normal": "▫️",
            "expensive": "⬜",
            "very_expensive": "◻️",
        }[level]
        return token, level

    def _serialize_schedule(
        self,
        schedule: tuple[TariffWindow, ...],
        super_cheap_threshold: int,
        cheap_threshold: int,
        expensive_threshold: int,
        very_expensive_threshold: int,
    ) -> list[dict[str, Any]]:
        """Convert a daily schedule into Lovelace-friendly dictionaries."""
        items: list[dict[str, Any]] = []

        for window in schedule:
            token, level = self._modifier_style(
                window.modifier_percent,
                super_cheap_threshold,
                cheap_threshold,
                expensive_threshold,
                very_expensive_threshold,
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
        very_expensive_threshold: int,
    ) -> str:
        """Render a compact one-line map for Markdown cards."""
        parts: list[str] = []

        for window in schedule:
            token, _ = self._modifier_style(
                window.modifier_percent,
                super_cheap_threshold,
                cheap_threshold,
                expensive_threshold,
                very_expensive_threshold,
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
        very_expensive_threshold: int,
    ) -> list[dict[str, str]]:
        """Build a legend from all modifiers present in today's schedule."""
        legend: list[dict[str, str]] = []
        for modifier_percent in sorted({window.modifier_percent for window in schedule}):
            token, level = self._modifier_style(
                modifier_percent,
                super_cheap_threshold,
                cheap_threshold,
                expensive_threshold,
                very_expensive_threshold,
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
        """Find the next future tariff window matching the threshold."""
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

    def _next_change(
        self,
        when: datetime,
        current_modifier: int,
    ) -> tuple[datetime | None, int | None]:
        """Find the next future boundary with a different modifier."""
        for offset in range(8):
            day = when.date() + timedelta(days=offset)
            for window in self._schedule_for_day(day):
                start_dt, _ = self._window_to_datetimes(day, window)
                if start_dt <= when or window.modifier_percent == current_modifier:
                    continue
                return start_dt, window.modifier_percent

        return None, None

    async def _async_update_data(self) -> TariffSnapshot:
        """Calculate the current tariff state."""
        if self._holidays is None:
            self._holidays = await self.hass.async_add_executor_job(
                holidays.country_holidays,
                "CZ",
            )

        now = dt_util.now()
        current_window = self._current_window(now)

        today = now.date()
        tomorrow = today + timedelta(days=1)
        season = self._season_label(today)
        season_code = self._season_code(today)
        is_holiday = self._is_holiday(today)
        day_type = self._day_type_label(today)
        day_type_code = self._day_type_code(today)
        schedule = self._schedule_for_day(today)
        tomorrow_schedule = self._schedule_for_day(tomorrow)

        cheap_threshold = int(self._option(CONF_CHEAP_THRESHOLD, DEFAULT_CHEAP_THRESHOLD))
        super_cheap_threshold = int(
            self._option(CONF_SUPER_CHEAP_THRESHOLD, DEFAULT_SUPER_CHEAP_THRESHOLD)
        )
        expensive_threshold = int(
            self._option(CONF_EXPENSIVE_THRESHOLD, DEFAULT_EXPENSIVE_THRESHOLD)
        )
        very_expensive_threshold = int(
            self._option(
                CONF_VERY_EXPENSIVE_THRESHOLD,
                DEFAULT_VERY_EXPENSIVE_THRESHOLD,
            )
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
        next_change, next_modifier_percent = self._next_change(
            now,
            current_modifier_percent,
        )

        today_map_code = self._map_code(today)
        tomorrow_map_code = self._map_code(tomorrow)
        today_schedule_revision, today_schedule_source_url = (
            self._schedule_metadata_for_day(today)
        )
        tomorrow_schedule_revision, tomorrow_schedule_source_url = (
            self._schedule_metadata_for_day(tomorrow)
        )

        return TariffSnapshot(
            current_modifier_percent=current_modifier_percent,
            current_band=current_band,
            current_window_start=current_window_start,
            current_window_end=current_window_end,
            season=season,
            season_code=season_code,
            day_type=day_type,
            day_type_code=day_type_code,
            is_holiday=is_holiday,
            cheap_threshold_percent=cheap_threshold,
            super_cheap_threshold_percent=super_cheap_threshold,
            expensive_threshold_percent=expensive_threshold,
            very_expensive_threshold_percent=very_expensive_threshold,
            cheap_now=current_modifier_percent <= cheap_threshold,
            super_cheap_now=current_modifier_percent <= super_cheap_threshold,
            expensive_now=current_modifier_percent >= expensive_threshold,
            very_expensive_now=current_modifier_percent >= very_expensive_threshold,
            base_price_kwh=base_price_kwh,
            effective_price_kwh=effective_price_kwh,
            next_cheap_start=next_cheap_start,
            next_cheap_end=next_cheap_end,
            next_cheap_modifier_percent=next_cheap_modifier_percent,
            next_change=next_change,
            next_modifier_percent=next_modifier_percent,
            today_map_code=today_map_code,
            today_schedule_revision=today_schedule_revision,
            today_schedule_source_url=today_schedule_source_url,
            today_schedule=self._serialize_schedule(
                schedule,
                super_cheap_threshold,
                cheap_threshold,
                expensive_threshold,
                very_expensive_threshold,
            ),
            today_display_map=self._display_map(
                schedule,
                super_cheap_threshold,
                cheap_threshold,
                expensive_threshold,
                very_expensive_threshold,
            ),
            today_legend=self._legend(
                schedule,
                super_cheap_threshold,
                cheap_threshold,
                expensive_threshold,
                very_expensive_threshold,
            ),
            tomorrow_map_code=tomorrow_map_code,
            tomorrow_schedule_revision=tomorrow_schedule_revision,
            tomorrow_schedule_source_url=tomorrow_schedule_source_url,
            tomorrow_schedule=self._serialize_schedule(
                tomorrow_schedule,
                super_cheap_threshold,
                cheap_threshold,
                expensive_threshold,
                very_expensive_threshold,
            ),
            tomorrow_display_map=self._display_map(
                tomorrow_schedule,
                super_cheap_threshold,
                cheap_threshold,
                expensive_threshold,
                very_expensive_threshold,
            ),
            tomorrow_legend=self._legend(
                tomorrow_schedule,
                super_cheap_threshold,
                cheap_threshold,
                expensive_threshold,
                very_expensive_threshold,
            ),
            tomorrow_season=self._season_label(tomorrow),
            tomorrow_season_code=self._season_code(tomorrow),
            tomorrow_day_type=self._day_type_label(tomorrow),
            tomorrow_day_type_code=self._day_type_code(tomorrow),
        )

    @property
    def title(self) -> str:
        """Return coordinator title."""
        return str(self.entry.data.get(CONF_NAME, DEFAULT_NAME))
