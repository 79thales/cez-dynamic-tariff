"""Společná cesta refresh/backfill: archiv, souběh, restart a diagnostika."""

from __future__ import annotations

import asyncio
import copy
import logging
from datetime import date, datetime, time, timedelta
from functools import partial
from pathlib import Path
from uuid import uuid4

from homeassistant.components.recorder import get_instance
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .accounting_archive import AccountingArchive, fingerprint, normalize_rows
from .accounting_storage import AccountingStore
from .const import DOMAIN
from .settlement import default_period

_LOGGER = logging.getLogger(__name__)
READ_TIMEOUT = 60
BLOCK_DAYS = 7


class AccountingRecovery:
    """Mixin pro SettlementHistory, jehož výpočty zůstávají společné.

    Pětiminutový refresh a ruční scan se zamykají stejným asyncio.Lock.
    Recorder I/O běží v jeho executor vlákně. Jeden backfill na instanci
    přežije přerušení pomocí uloženého kurzoru; automaticky se po restartu
    nerozbíhá, pokračuje až stiskem tlačítka. Žádné options ani cizí
    statistiky se zde nezapisují. Časy kurzoru jsou místní kalendářní dny,
    hodinové klíče archivu vždy UTC sekundy.
    """

    def _init_recovery(self):
        self.archive = AccountingArchive()
        self._history_lock = asyncio.Lock()
        self._backfill_task = None
        self._closing = False
        self._store_loaded = False
        self._store_writable = True
        self._reasons = set()
        self._logged_reasons = None
        self._logged_read_error = None
        self._hdo_read_failed = False
        self._last_complete = None
        self._last_success = None
        self._last_attempt = None
        self._last_refresh_successful = False
        self._read_counts = {}
        self._store = None
        entry = getattr(self.coordinator, "entry", None)
        if entry is not None:
            self._store = AccountingStore(
                self.hass,
                1,
                f"{DOMAIN}.accounting_{entry.entry_id}",
                private=True,
                atomic_writes=True,
            )

    def _source_identity(self, entity_id):
        """Registrované unique_id přežije přejmenování; jméno není identita."""
        registry = er.async_get(self.hass)
        item = registry.async_get(entity_id) if entity_id else None
        saved = self.archive.data["bindings"].get(entity_id, {})
        if item is None and saved.get("identity"):
            return saved["identity"]
        return fingerprint(
            {
                "entity": None if item else entity_id,
                "unique_id": item.unique_id if item else None,
                "registry_id": item.id if item else None,
                "device_id": item.device_id if item else None,
                "platform": item.platform if item else None,
                "entry": item.config_entry_id if item else None,
            }
        )

    def _resolve_source(self, configured):
        """Přejmenování sledujeme podle uloženého registry ID, bez zápisu options.

        Registry ID označuje konkrétní entitu; nevyhledáváme podle názvu
        ani podobné přípony. Pokud původní entita neexistuje, vrátíme
        původní ID a výslovnou diagnostiku, nikoli náhodnou náhradu.
        """
        registry = er.async_get(self.hass)
        item = registry.async_get(configured) if configured else None
        bindings = self.archive.data["bindings"]
        if item is not None:
            bindings[configured] = {
                "registry_id": item.id,
                "identity": self._source_identity(item.entity_id),
            }
            return item.entity_id
        binding = bindings.get(configured)
        if binding:
            matches = [
                e for e in registry.entities.values() if e.id == binding["registry_id"]
            ]
            if len(matches) == 1:
                return matches[0].entity_id
        return configured

    def _identities(self):
        # Výpočetní klon čte neměnný snapshot options. Při kooperativním
        # yield se mohou změnit živé rozvrhy; nesmí vzniknout směs starých
        # sazeb a nových dynamických pásem pod původním otiskem ceny.
        self._calculation_coordinator = copy.copy(self.coordinator)
        entry = getattr(self.coordinator, "entry", None)
        if entry is not None:
            frozen = {**getattr(entry, "data", {}), **dict(entry.options)}
            self._calculation_coordinator._option = lambda key, default: frozen.get(
                key, default
            )
        self._resolved_meter = self._resolve_source(
            self.values["accounting_energy_entity"]
            or self.billing.values["import_energy_entity"]
        )
        self._resolved_schedule = self._resolve_source(
            self.billing.values["hdo_schedule_entity"]
        )
        self._resolved_cost = self._resolve_source(
            self.values["historical_cost_entity"]
        )
        self._billing_meter = self._resolve_source(
            self.billing.values["import_energy_entity"]
        )
        registry = er.async_get(self.hass)
        own = er.async_entries_for_config_entry(registry, self._entry_id)
        self._financial_ids = {}
        for key in ("actual_cost", "unpriced_energy", "realized_savings"):
            candidates = [
                e.entity_id
                for e in own
                if e.platform == DOMAIN and e.unique_id == f"{self._entry_id}_{key}"
            ]
            self._financial_ids[key] = (
                candidates[0] if len(candidates) == 1 else f"sensor.{DOMAIN}_{key}"
            )
        self._source_warnings = []
        for label, entity in (
            ("energy", self.meter_id),
            ("hdo", self._resolved_schedule),
        ):
            item = registry.async_get(entity) if entity else None
            if not entity or (item is None and self.hass.states.get(entity) is None):
                self._source_warnings.append(f"{label}_source_missing")
            elif item and item.disabled_by is not None:
                self._source_warnings.append(f"{label}_source_disabled")
        self._energy_identity = self._source_identity(self.meter_id)
        self._hdo_identity = self._source_identity(self._resolved_schedule)
        # Výsledek nesmí přežít změnu cenové logiky jako platná cena.
        # Platby/odečet mění celek, nikoli cenu již odebrané hodiny.
        price_values = {
            k: v
            for k, v in self.billing.values.items()
            if k
            not in {
                "annual_import_kwh",
                "include_standing_fees",
                "import_energy_entity",
                "hdo_entity",
                "hdo_valid_entity",
                "hdo_schedule_entity",
            }
        }
        schedule_keys = (
            "summer_workday_schedule",
            "summer_offday_schedule",
            "winter_workday_schedule",
            "winter_offday_schedule",
            "include_holidays",
        )
        self._cost_revision = fingerprint(
            {
                "algorithm": 1,
                "energy": self._energy_identity,
                "hdo": self._hdo_identity,
                "prices": price_values,
                "history": {
                    k: self.values[k]
                    for k in (
                        "dynamic_start",
                        "dynamic_contract_mode",
                        "current_price_start",
                        "historical_profiles",
                    )
                },
                "monetary_source": self._source_identity(self._resolved_cost),
                "price_list_trade_effective": self.coordinator._option(
                    "price_list_trade_effective", ""
                ),
                "schedules": {
                    k: self.coordinator._option(k, None) for k in schedule_keys
                },
                "tz": str(self.coordinator._local_tz()),
            }
        )

    async def async_initialize(self):
        """Načte archiv jednou; poškozený Store se nesmí přepsat prázdnem."""
        if self._store_loaded:
            return
        self._store_loaded = True
        try:
            existed = (
                await self.hass.async_add_executor_job(Path(self._store.path).is_file)
                if self._store
                else False
            )
            saved = await self._store.async_load() if self._store else None
            if existed and saved is None:
                # HA může syntakticky poškozený JSON odsunout do .corrupt.
                # Záloha zůstane zachována, tato instance ho nepřepíše.
                raise ValueError("archive_load_empty_existing_file")
            self.archive = AccountingArchive(saved)
            self._identities()
            previous = self.archive.data.get("last_complete_forecast")
            self._last_complete = (
                previous
                if isinstance(previous, dict)
                and previous.get("revision") == self._cost_revision
                else None
            )
            state = self.archive.data["backfill"]
            if state.get("status") == "running":
                state["status"] = "paused"
        except (
            ValueError,
            TypeError,
            OSError,
            HomeAssistantError,
            NotImplementedError,
        ):
            self._identities()
            self._store_writable = False
            self._reasons.add("archive_invalid")
            _LOGGER.exception(
                "Accounting archive rejected entry=%s; original file preserved",
                self._entry_id,
            )

    @property
    def _entry_id(self):
        return getattr(getattr(self.coordinator, "entry", None), "entry_id", "test")

    @property
    def backfill_state(self):
        return {"status": "idle", **self.archive.data["backfill"]}

    def _period(self, now):
        first, last = default_period(now.date())
        return date.fromisoformat(
            self.values["billing_start"] or first
        ), date.fromisoformat(self.values["billing_end"] or last)

    async def _persist(self):
        if self._store and self._store_writable:
            try:
                self.archive.data["last_complete_forecast"] = self._last_complete
                task = self.hass.async_create_task(
                    self._store.async_save(self.archive.snapshot())
                )
                try:
                    # Zrušený scan nechá právě zahájený atomický zápis
                    # dokončit. Jinak by executor mohl později přepsat novější
                    # paused snapshot starším stavem running.
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    await task
                    raise
                self._reasons.discard("archive_write_failed")
            except (OSError, HomeAssistantError):
                self._reasons.add("archive_write_failed")
                raise

    async def _ingest(self, raw, now, horizon):
        """Validuje a ukládá zavřené energie; peněžní součty neduplikuje.

        Konflikt v čerstvé odpovědi nevymaže archiv, ale zůstává důvodem
        neúplnosti. Archiv může vyplnit chybějící odpověď, nikoli potichu
        označit konfliktní čtení za ověřené. Finanční a EDC řady mají
        vlastní validaci a stejný klíč UTC.
        """
        counts = {"duplicates": 0, "invalid": 0, "conflicts": 0}

        def record_quality(key, result):
            # Chyba příjmu/úspory má vlastní závislost. Nesmí zneplatnit
            # samotný odběr ani jeho úplné hrubé ocenění.
            prefix = (
                "statistics"
                if key == self.meter_id
                else "income_statistics"
                if key == raw["revenue_id"]
                else "cost_statistics"
            )
            if result["invalid"]:
                self._reasons.add(f"{prefix}_invalid")
            if result["conflicts"]:
                self._reasons.add(f"{prefix}_conflict")
            for name in counts:
                counts[name] += result[name]

        for key, rows in list(raw["hourly"].items()):
            normalized, result = normalize_rows(
                rows, nonnegative=key != raw["revenue_id"]
            )
            lower = raw.get("requested_start", horizon.timestamp())
            upper = raw.get("requested_end", raw["closed_hour"].timestamp())
            accepted = [
                r for r in normalized if lower <= r["start"] and r["end"] <= upper
            ]
            result["invalid"] += len(normalized) - len(accepted)
            normalized = accepted
            raw["hourly"][key] = normalized
            record_quality(key, result)
        for key, rows in list(raw.get("short_today", {}).items()):
            normalized, result = normalize_rows(
                rows, seconds=300, nonnegative=key != raw["revenue_id"]
            )
            raw["short_today"][key] = normalized
            record_quality(key, result)
        self._read_counts = {
            **counts,
            **self.archive.merge_energy(
                self._energy_identity, raw["hourly"].get(self.meter_id, [])
            ),
        }
        # Do profilu zahrneme jen horizon; archiv může uchovat další revize,
        # ale různé zdroje nikdy nesčítáme. Dnešní tail není uzavřená hodina.
        midnight = datetime.combine(now.date(), time.min, tzinfo=now.tzinfo).timestamp()
        raw["hourly"][self.meter_id] = self.archive.energy_rows(
            self._energy_identity, horizon.timestamp(), midnight
        )
        self.raw = raw
        schedules = self._intervals(now)
        costs = {r["start"]: r["change"] for r in raw["hourly"].get(raw["cost_id"], [])}
        if not self.values["historical_cost_entity"]:
            if costs:
                costs.pop(min(costs))
            for row in raw["hourly"].get(raw["unpriced_id"], []):
                if row["change"] > 1e-6:
                    costs.pop(row["start"], None)
        timelines = {}
        period_start, period_end = self._period(now)
        for index, row in enumerate(raw["hourly"][self.meter_id]):
            day = datetime.fromtimestamp(row["start"], now.tzinfo).date()
            if not period_start <= day <= period_end:
                # Starší sezony potřebují měřenou energii, nikoli dnešní
                # účetní ceník. Chybějící ceny mimo období nejsou jeho chyba.
                continue
            # Výpočetní cesta stejná jako při běžném ocenění. Trial součet
            # musí zahrnout savings; jeho složení provádí _calculate.
            monetary = costs.get(row["start"]) if not self.trial else None
            if not self.contract_known and not self.values["historical_cost_entity"]:
                monetary = None
            self._hour_cost(row, monetary, schedules, now, timelines)
            if index % 24 == 23:
                # Dlouhé přecenění po změně sazeb nezabere celou smyčku HA.
                # Zámek chrání archiv, ostatní integrace mezi dny pokračují.
                await asyncio.sleep(0)
        self.archive.prune(horizon.timestamp())

    async def _load_raw(self, now, start, *, scan_end=None):
        """Timeout nezmění úspěšná data; opakujeme jen timeout/OSError.

        Timeout může nechat čtecí executor doběhnout. Čte pouze lokální
        Recorder a vrací výsledek; nevlastní Store a neprovádí žádný zápis.
        """
        for attempt in range(3):
            try:
                job = partial(
                    self._read, now, start, self._revenue_id(), scan_end=scan_end
                )
                return await asyncio.wait_for(
                    get_instance(self.hass).async_add_executor_job(job), READ_TIMEOUT
                )
            except (TimeoutError, OSError):
                if attempt == 2:
                    raise
                await asyncio.sleep(2**attempt)

    def _decorate(self, now):
        """Konkrétní příčiny a poslední úplný výsledek s výslovným stářím."""
        meta = self.result.setdefault("metadata", {})
        self._reasons.difference_update(
            {
                "historical_hdo_missing",
                "energy_history_gap",
                "live_hdo_unavailable",
                "today_energy_gap",
                "advances_missing",
                "consumption_profile_missing",
                "shared_income_pending",
                "contract_unconfirmed",
            }
        )
        if (
            meta.get("unpriced_period_kwh", 0) > 1e-6
            and "historical_price_missing" not in self._reasons
        ):
            self._reasons.add("historical_hdo_missing")
        if meta.get("period_energy_coverage", 1) < 1:
            self._reasons.add("energy_history_gap")
        if meta.get("missing_fee_days", 0):
            self._reasons.add("price_profile_missing")
        if meta.get("daily_unpriced_kwh", 0) > 1e-6:
            self._reasons.add("live_hdo_unavailable")
        if meta.get("daily_energy_complete") is False:
            self._reasons.add("today_energy_gap")
        if meta.get("missing_advance_months"):
            self._reasons.add("advances_missing")
        if meta.get("missing_profile_months"):
            self._reasons.add("consumption_profile_missing")
        if (
            self.values["deduct_shared_income"]
            and self.result.get("period_shared_income") is None
        ):
            self._reasons.add("shared_income_pending")
        if not self.contract_known:
            self._reasons.add("contract_unconfirmed")
        blocking = self._reasons & {
            "statistics_invalid",
            "statistics_conflict",
            "archive_write_failed",
            "hdo_schedule_conflict",
        }
        if blocking:
            self.result["accounting_status"] = "incomplete"
            for key in (
                "period_gross_cost",
                "forecast_gross_cost",
                "forecast_net_cost",
                "forecast_balance",
            ):
                self.result[key] = None
            meta["cost_forecast_series"] = []
        if (
            self.result.get("accounting_status") == "complete"
            and self.result.get("forecast_gross_cost") is not None
        ):
            self._last_complete = {
                "calculated_at": now.isoformat(),
                "revision": self._cost_revision,
                "cost_forecast_series": meta.get("cost_forecast_series", []),
            }
        meta.update(
            {
                "reason_codes": sorted(self._reasons),
                "last_success_at": self._last_success,
                "last_complete_forecast": self._last_complete,
                "forecast_stale": bool(
                    self._last_complete
                    and self.result.get("forecast_gross_cost") is None
                ),
                "backfill": self.backfill_state,
                "read_counts": self._read_counts,
                "archive_hours": len(
                    self.archive.data["energy"].get(self._energy_identity, {})
                ),
                "source_warnings": self._source_warnings,
                "reference_source": self.values.get(
                    "reference_source", "legacy_unspecified"
                ),
            }
        )
        reasons = tuple(sorted(self._reasons))
        if reasons != self._logged_reasons:
            if reasons:
                _LOGGER.warning(
                    "Accounting state entry=%s reasons=%s", self._entry_id, reasons
                )
            elif self._logged_reasons:
                _LOGGER.info("Accounting recovered entry=%s", self._entry_id)
            self._logged_reasons = reasons

    async def async_refresh(self, now, *, force=False):
        """Pravidelný refresh, atomický archiv a nové potvrzení výsledku."""
        if not self.values["accounting_enabled"] or self._closing:
            return
        async with self._history_lock:
            await self.async_initialize()
            entry = getattr(self.coordinator, "entry", None)
            if self._closing or (
                entry and self.coordinator.options_snapshot != dict(entry.options)
            ):
                return
            self._identities()
            now = now.astimezone(self.coordinator._local_tz())
            start, end = self._period(now)
            if (
                not force
                and self._last_attempt is not None
                and self._last_attempt.date() == now.date()
                and 0 <= now.timestamp() - self._last_attempt.timestamp() < 300
            ):
                # I při použití cache se plán/úhrady mohly změnit.
                if self.raw is not None and self._last_refresh_successful:
                    self.result = self._calculate(now, start, end)
                # Po chybě nepublikujeme staré raw jako nový úspěšný výpočet.
                # Opakování má stejný pětiminutový odstup, force ho obejde.
                self._decorate(now)
                return
            self._last_attempt = now
            self._reasons = set() if self._store_writable else {"archive_invalid"}
            phase = "reading"
            try:
                horizon = datetime.combine(
                    min(start, now.date() - timedelta(days=730)),
                    time.min,
                    tzinfo=now.tzinfo,
                )
                raw = await self._load_raw(
                    now, datetime.combine(start, time.min, tzinfo=now.tzinfo)
                )
                entry = getattr(self.coordinator, "entry", None)
                if self._closing or (
                    entry and self.coordinator.options_snapshot != dict(entry.options)
                ):
                    self._reasons.add("configuration_changed")
                    self._last_refresh_successful = False
                    self.result = {"accounting_status": "history_unavailable"}
                    self._decorate(now)
                    return
                self._reasons.update(raw.get("reason_codes", []))
                phase = "calculating"
                await self._ingest(raw, now, horizon)
                if self._closing or (
                    entry and self.coordinator.options_snapshot != dict(entry.options)
                ):
                    self._last_refresh_successful = False
                    return
                self.last_read = now
                self._last_success = now.isoformat()
                self.result = self._calculate(now, start, end)
                self._decorate(now)
                phase = "saving"
                await self._persist()
                self._last_refresh_successful = True
                self._logged_read_error = None
            except asyncio.CancelledError:
                raise
            except Exception as err:
                # Neočekávaná porucha zůstává viditelná v logu s tracebackem;
                # nepřevádíme ji na nulu a nevymažeme ověřený archiv.
                self._reasons.add(
                    {
                        "reading": "recorder_unavailable",
                        "calculating": "calculation_failed",
                        "saving": "archive_write_failed",
                    }[phase]
                )
                failure = (phase, type(err).__name__)
                if failure != self._logged_read_error:
                    _LOGGER.exception(
                        "Accounting refresh failed entry=%s phase=%s",
                        self._entry_id,
                        phase,
                    )
                else:
                    _LOGGER.debug(
                        "Accounting failure persists entry=%s phase=%s",
                        self._entry_id,
                        phase,
                    )
                self._logged_read_error = failure
                self._last_refresh_successful = False
                self.result = {"accounting_status": "history_unavailable"}
            self._decorate(now)

    def async_start_history_backfill(self, *, start=None, end=None):
        """Přijme jeden scan; druhý stisk vrátí False a běh nezdvojí."""
        if self._closing or not self.values["accounting_enabled"]:
            raise HomeAssistantError("Accounting runtime is not available")
        if not self._store_writable:
            raise HomeAssistantError(
                "Accounting archive is invalid; original file preserved"
            )
        if self._backfill_task and not self._backfill_task.done():
            return False
        now = dt_util.now().astimezone(self.coordinator._local_tz())
        period_start, _ = self._period(now)
        first = start or min(period_start, now.date() - timedelta(days=730))
        last = end or now.date()
        if first > last or last > now.date() or (last - first).days > 1096:
            raise HomeAssistantError(
                "Backfill range must be ordered, not future, and at most three years"
            )
        state = self.archive.data["backfill"]
        if (
            start is None
            and end is None
            and state.get("status") in {"paused", "failed"}
            and state.get("revision") == self._cost_revision
        ):
            try:
                first, last = (
                    date.fromisoformat(state["start"]),
                    date.fromisoformat(state["end"]),
                )
                cursor = date.fromisoformat(state["cursor"])
                if not first <= cursor <= last + timedelta(days=1):
                    raise ValueError("cursor outside range")
            except (KeyError, ValueError, TypeError):
                raise HomeAssistantError("Saved backfill cursor is invalid") from None
        else:
            cursor = first
            state = {
                "run_id": uuid4().hex,
                "start": first.isoformat(),
                "end": last.isoformat(),
                "cursor": cursor.isoformat(),
                "processed_blocks": 0,
                "total_blocks": ((last - first).days // BLOCK_DAYS) + 1,
                "revision": self._cost_revision,
                "gaps": [],
                "started_at": now.isoformat(),
                "last_success_at": state.get("last_success_at"),
                "counts": {},
            }
            self.archive.data["backfill"] = state
        state.update(status="running", phase="waiting", error=None, completed_at=None)
        entry = getattr(self.coordinator, "entry", None)
        coro = self._async_backfill(first, last, cursor)
        if entry is not None:
            self._backfill_task = entry.async_create_background_task(
                self.hass, coro, f"{DOMAIN} accounting backfill"
            )
        else:
            self._backfill_task = self.hass.async_create_task(coro)
        self.coordinator.async_update_listeners()
        return True

    async def _async_backfill(self, first, last, cursor):
        state = self.archive.data["backfill"]
        started_clock = self.hass.loop.time()
        _LOGGER.info(
            "Backfill started entry=%s run=%s range=%s/%s",
            self._entry_id,
            state["run_id"],
            first,
            last,
        )
        try:
            while cursor <= last:
                right = min(
                    last + timedelta(days=1), cursor + timedelta(days=BLOCK_DAYS)
                )
                async with self._history_lock:
                    now = dt_util.now().astimezone(self.coordinator._local_tz())
                    entry = getattr(self.coordinator, "entry", None)
                    if self._closing or (
                        entry
                        and self.coordinator.options_snapshot != dict(entry.options)
                    ):
                        state["status"] = "paused"
                        break
                    self._reasons = set()
                    state["phase"] = "reading"
                    left_dt = datetime.combine(cursor, time.min, tzinfo=now.tzinfo)
                    right_dt = min(
                        now, datetime.combine(right, time.min, tzinfo=now.tzinfo)
                    )
                    raw = await self._load_raw(now, left_dt, scan_end=right_dt)
                    if self._closing or (
                        entry
                        and self.coordinator.options_snapshot != dict(entry.options)
                    ):
                        # Kontrola také po await: uživatel mohl během čtení
                        # změnit zdroj/ceny. Výsledek staré revize nezapíšeme.
                        state["status"] = "paused"
                        break
                    self._reasons.update(raw.get("reason_codes", []))
                    state["phase"] = "calculating"
                    period_start, _ = self._period(now)
                    retention_start = min(
                        first, period_start, now.date() - timedelta(days=730)
                    )
                    previous_raw = self.raw
                    try:
                        await self._ingest(
                            raw,
                            now,
                            datetime.combine(
                                retention_start, time.min, tzinfo=now.tzinfo
                            ),
                        )
                    finally:
                        # Mezi bloky nesmí cache běžného refreshu používat
                        # částečné EDC/peněžní řady z posledního bloku scanu.
                        self.raw = previous_raw
                    if self._closing or (
                        entry
                        and self.coordinator.options_snapshot != dict(entry.options)
                    ):
                        state["status"] = "paused"
                        break
                    # Pokrytí požadovaného uzavřeného bloku hodnotíme zvlášť
                    # od celého profilu. Před kontrolním bodem chybějící
                    # hodinový rozpis nesmí být označen za nově dotažený.
                    closed_right = min(
                        right_dt,
                        datetime.combine(now.date(), time.min, tzinfo=now.tzinfo),
                    )
                    rows = self.archive.energy_rows(
                        self._energy_identity,
                        left_dt.timestamp(),
                        closed_right.timestamp(),
                    )
                    expected = max(
                        0, (closed_right.timestamp() - left_dt.timestamp()) / 3600
                    )
                    if len(rows) < expected:
                        self._reasons.add("energy_history_gap")
                    reference = (
                        date.fromisoformat(self.values["reference_date"])
                        if self.values["reference_date"]
                        and self.values["reference_period_start"]
                        == period_start.isoformat()
                        else None
                    )
                    cost_start = datetime.combine(
                        max(
                            period_start,
                            reference + timedelta(days=1)
                            if reference
                            else period_start,
                        ),
                        time.min,
                        tzinfo=now.tzinfo,
                    ).timestamp()
                    if any(
                        r["start"] >= cost_start
                        and self.archive.cost(
                            self._cost_revision, r["start"], r["change"]
                        )
                        is None
                        for r in rows
                    ):
                        self._reasons.add("historical_hdo_missing")
                    if self._reasons:
                        state["gaps"] = (
                            state.get("gaps", [])
                            + [
                                {
                                    "start": cursor.isoformat(),
                                    "end": (right - timedelta(days=1)).isoformat(),
                                    "reasons": sorted(self._reasons),
                                }
                            ]
                        )[-160:]
                    state.update(
                        cursor=right.isoformat(),
                        phase="saving",
                        processed_blocks=state["processed_blocks"] + 1,
                        current_range=[
                            cursor.isoformat(),
                            (right - timedelta(days=1)).isoformat(),
                        ],
                    )
                    state["counts"] = {
                        k: state.get("counts", {}).get(k, 0) + v
                        for k, v in self._read_counts.items()
                    }
                    state["duration_seconds"] = round(
                        self.hass.loop.time() - started_clock, 3
                    )
                    # Archiv a kurzor jsou jedním snapshotem; disková chyba
                    # neukáže uložený úspěch a obnovení blok zopakuje.
                    await self._persist()
                    _LOGGER.debug(
                        "Backfill block entry=%s run=%s range=%s/%s counts=%s reasons=%s",
                        self._entry_id,
                        state["run_id"],
                        cursor,
                        right,
                        self._read_counts,
                        sorted(self._reasons),
                    )
                self.coordinator.async_update_listeners()
                cursor = right
                await asyncio.sleep(0)
            if state["status"] == "running":
                # Závěrečný refresh načte i dnešní tail a EDC; scan samotný
                # nesmí publikovat výsledek z posledního sedmidenního bloku.
                await self.async_refresh(dt_util.now(), force=True)
                state.update(
                    status="incomplete"
                    if state.get("gaps") or self._reasons
                    else "completed",
                    phase="finished",
                    completed_at=dt_util.now().isoformat(),
                )
                if state["status"] == "completed":
                    state["last_success_at"] = state["completed_at"]
            self.archive.data["runs"] = (
                self.archive.data["runs"]
                + [
                    {
                        k: state.get(k)
                        for k in (
                            "run_id",
                            "status",
                            "started_at",
                            "completed_at",
                            "processed_blocks",
                            "error",
                        )
                    }
                ]
            )[-20:]
            await self._persist()
            _LOGGER.info(
                "Backfill finished entry=%s run=%s status=%s blocks=%s",
                self._entry_id,
                state["run_id"],
                state["status"],
                state["processed_blocks"],
            )
        except asyncio.CancelledError:
            state["status"] = "paused"
            await self._persist()
            raise
        except Exception as err:
            state.update(status="failed", error=type(err).__name__)
            _LOGGER.exception(
                "Backfill failed entry=%s run=%s", self._entry_id, state["run_id"]
            )
            try:
                await self._persist()
            except (OSError, HomeAssistantError):
                _LOGGER.exception(
                    "Backfill failure state could not be saved entry=%s", self._entry_id
                )
        finally:
            if self.result.get("metadata") is not None:
                self.result["metadata"]["backfill"] = self.backfill_state
            self.coordinator.async_update_listeners()

    async def async_close(self):
        """Unload zastaví scan před finálním uložením; nový runtime načte paused."""
        self._closing = True
        if self._backfill_task and not self._backfill_task.done():
            self._backfill_task.cancel()
            try:
                await self._backfill_task
            except asyncio.CancelledError:
                pass
        async with self._history_lock:
            await self._persist()
