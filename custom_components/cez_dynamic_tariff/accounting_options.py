"""Nativní administrace účetních podkladů bez JSON v uživatelském formuláři.

Mixin patří pouze OptionsFlow. Rozpracovaný záznam je kopie; teprve potvrzení
uloží seznam do původních options a vyvolá běžný reload integrace.
"""

from __future__ import annotations

import copy
import json
from datetime import date, timedelta

import voluptuous as vol
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.util import dt as dt_util

from .accounting_documents import (
    RATE_KEYS,
    bill_key,
    period,
    records,
    selected_ratio,
    validate_document,
)
from .const import DOMAIN


class AccountingDocumentsFlow:
    """Formuláře faktur, ceníků a kontrola existujícího backfillu."""

    def _document_rows(self, kind):
        key = "settled_bills" if kind == "bill" else "historical_profiles"
        return records(self._accounting_values()[key])

    def _document_start(self):
        return self._accounting_values()["current_price_start"] or (
            self._config_entry.options.get("price_list_trade_effective", "")
        )

    def _document_begin(self, kind, index=None):
        self._document_kind, self._document_index = kind, index
        self._document_baseline = {
            k: self._config_entry.options.get(k)
            for k in (
                "settled_bills",
                "historical_profiles",
                "estimate_bill",
                "current_price_start",
                "price_list_trade_effective",
            )
        }
        self._document = (
            copy.deepcopy(self._document_rows(kind)[index])
            if index is not None
            else {"source": "Ručně ověřený podklad"}
        )
        # Starší uložené faktury mají součty VT/NT jen v měsíčním rozpisu.
        # Předvyplníme je pouze při shodě s doloženou celkovou energií.
        if kind == "bill" and self._document.get("months"):
            nt = sum(m["nt_kwh"] for m in self._document["months"])
            vt = sum(m["vt_kwh"] for m in self._document["months"])
            if abs(nt + vt - self._document.get("energy_kwh", 0)) <= 0.01:
                self._document.setdefault("nt_kwh", nt)
                self._document.setdefault("vt_kwh", vt)

    def _document_assert_current(self):
        """Před validací i zápisem odmítni zastaralou kopii podkladů."""
        if any(
            self._config_entry.options.get(k) != v
            for k, v in self._document_baseline.items()
        ):
            raise ValueError("documents_changed")

    def _document_save(self, *, delete=False):
        """Zápis je atomický; souběžná změna jiného formuláře se nepřepíše."""
        self._document_assert_current()
        kind = self._document_kind
        rows = copy.deepcopy(self._document_rows(kind))
        old_key = None
        if self._document_index is not None:
            old = rows.pop(self._document_index)
            old_key = bill_key(old) if kind == "bill" else None
        if not delete:
            validate_document(
                self._document, rows, kind, dt_util.now().date(), self._document_start()
            )
            rows.append(self._document)
        rows.sort(key=lambda r: r["start"])
        key = "settled_bills" if kind == "bill" else "historical_profiles"
        self._pending_options[key] = json.dumps(rows, ensure_ascii=False)
        if old_key and self._accounting_values().get("estimate_bill") == old_key:
            self._pending_options["estimate_bill"] = (
                bill_key(self._document) if not delete else ""
            )
        return self._finish_options()

    async def async_step_accounting_documents(self, user_input=None):
        """Přehled dokládá skutečně uložené záznamy, nikoli soubory na disku."""
        try:
            bills, profiles = (
                self._document_rows("bill"),
                self._document_rows("profile"),
            )
            summary = (
                f"Vyúčtování: {len(bills)} · Historické ceníky: {len(profiles)}\n\n"
                f"Aktivní ceník od: {self._document_start() or 'neurčeno'}\n\n"
                "Faktury doplňují sezónní profil a mohou sloužit jako zdroj poměru "
                "VT/NT. Součet faktury nahrazuje účetnictví jen při přesné shodě "
                "celého zúčtovacího období. Kontrolní odečet se spravuje samostatně."
            )
        except (ValueError, KeyError, TypeError):
            return self.async_abort(reason="invalid_documents")
        return self.async_show_menu(
            step_id="accounting_documents",
            menu_options=[
                "document_bills",
                "document_profiles",
                "active_prices",
                "estimate_settings",
                "accounting_check",
            ],
            description_placeholders={"summary": summary},
        )

    async def _document_select(self, kind, user_input):
        rows = self._document_rows(kind)
        step = "document_bills" if kind == "bill" else "document_profiles"
        errors = {}
        if user_input is not None:
            try:
                index = (
                    None if user_input["record"] == "new" else int(user_input["record"])
                )
                if index is not None and not 0 <= index < len(rows):
                    raise ValueError("invalid_documents")
                self._document_begin(kind, index)
                if user_input.get("action") == "delete":
                    if index is None:
                        raise ValueError("select_existing_document")
                    return await self.async_step_document_delete()
                if kind == "bill":
                    return await self.async_step_document_bill()
                if index is None:
                    return await self.async_step_document_profile_source()
                return await self.async_step_document_profile()
            except (ValueError, KeyError, TypeError):
                errors["base"] = "select_existing_document"
        current = self._document_start()
        gaps = []
        if kind == "profile":
            values = self._accounting_values()
            cursor = date.fromisoformat(values["billing_start"])
            finish = min(
                date.fromisoformat(values["billing_end"]), dt_util.now().date()
            )
            gap_start = None
            while cursor <= finish + timedelta(days=1):
                covered = (
                    cursor > finish
                    or bool(current and cursor >= date.fromisoformat(current))
                    or any(
                        date.fromisoformat(r["start"])
                        <= cursor
                        <= date.fromisoformat(r["end"])
                        for r in rows
                    )
                )
                if not covered and gap_start is None:
                    gap_start = cursor
                if covered and gap_start is not None:
                    gaps.append(f"{gap_start} → {cursor - timedelta(days=1)}")
                    gap_start = None
                cursor += timedelta(days=1)
        choices = [{"value": "new", "label": "Přidat nový záznam"}]
        for i, row in enumerate(rows):
            detail = (
                f"{row['energy_kwh']:g} kWh · {row['cost']:.2f} Kč"
                if kind == "bill"
                else "Kč s DPH · podrobnosti v editoru"
            )
            choices.append(
                {"value": str(i), "label": f"{row['start']} → {row['end']} · {detail}"}
            )
        return self.async_show_form(
            step_id=step,
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required("record", default="new"): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=choices)
                    ),
                    vol.Required("action", default="edit"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {"value": "edit", "label": "Přidat / upravit"},
                                {"value": "delete", "label": "Odstranit"},
                            ]
                        )
                    ),
                }
            ),
            description_placeholders={
                "current": (current or "neurčeno")
                + "\n\nMezery v cenách za dosavadní období: "
                + (", ".join(gaps) or "žádné"),
            },
        )

    async def async_step_document_bills(self, user_input=None):
        return await self._document_select("bill", user_input)

    async def async_step_active_prices(self, user_input=None):
        """Aktivní sazby sdílejí původní editor i úložiště; nevzniká jejich kopie."""
        return await self.async_step_price_rates(user_input)

    async def async_step_document_profiles(self, user_input=None):
        return await self._document_select("profile", user_input)

    async def async_step_document_profile_source(self, user_input=None):
        return self.async_show_menu(
            step_id="document_profile_source",
            menu_options=["profile_manual", "profile_import", "profile_copy"],
        )

    async def async_step_profile_manual(self, user_input=None):
        return await self.async_step_document_profile()

    async def async_step_profile_copy(self, user_input=None):
        """Kopírování sazeb je výslovná volba; datum a potvrzení zadá uživatel."""
        from .pricing import PROFILE_DEFAULTS

        self._document["rates"] = {
            k: self._config_entry.options.get(k, PROFILE_DEFAULTS[k]) for k in RATE_KEYS
        }
        self._document["source"] = (
            "Ruční kopie aktivních sazeb; platnost ověřena uživatelem"
        )
        return await self.async_step_document_profile()

    async def async_step_profile_import(self, user_input=None):
        """Stejný bezpečný PDF import, ale výstup míří jen do historického záznamu."""
        self._import_historical = True
        self._before_historical_import = dict(self._pending_options)
        return await self.async_step_price_list()

    async def _historical_import_review(self):
        """Náhled ukazuje sazby a obě původní účinnosti; aktivní ceník nezmění."""
        imported = dict(self._pending_options)
        info = self._price_list_info
        self._document.update(
            source=info["source"],
            start=max(info["trade_effective"], info["distribution_effective"]),
            rates={k: imported[k] for k in RATE_KEYS},
            import_metadata=dict(info),
            price_list_sha256=imported["price_list_sha256"],
        )
        current = self._document_start()
        if current and current > self._document["start"]:
            self._document["end"] = (
                date.fromisoformat(current) - timedelta(days=1)
            ).isoformat()
        self._pending_options = self._before_historical_import
        self._price_list_info = None
        self._import_historical = False
        return await self.async_step_document_profile()

    async def async_step_document_bill(self, user_input=None):
        """Celkové kWh se kontrolují proti VT+NT; měsíční rozpis je volitelný."""
        errors = {}
        row = self._document
        if user_input is not None:
            candidate = {
                **row,
                **{
                    k: v
                    for k, v in user_input.items()
                    if k not in ("edit_months", "clear_months")
                },
            }
            # Prázdné volitelné údaje zůstanou neznámé, nikoli nula.
            for k in ("fixed_cost", "paid"):
                if user_input.get(k) is None:
                    candidate.pop(k, None)
            if user_input.get("clear_months"):
                candidate.pop("months", None)
            try:
                self._document_assert_current()
                others = [
                    r
                    for i, r in enumerate(self._document_rows("bill"))
                    if i != self._document_index
                ]
                validate_document(
                    {**candidate, "months": []}
                    if user_input.get("edit_months")
                    else candidate,
                    others,
                    "bill",
                    dt_util.now().date(),
                )
                self._document = candidate
                if user_input.get("edit_months"):
                    return await self.async_step_document_months()
                return self._document_save()
            except (ValueError, KeyError, TypeError) as err:
                errors["base"] = (
                    str(err) if isinstance(err, ValueError) else "invalid_documents"
                )
        values = user_input or row
        schema = self._document_fields(
            values,
            {
                "source": str,
                "start": selector.DateSelector(),
                "end": selector.DateSelector(),
                "energy_kwh": self._number("kWh"),
                "vt_kwh": self._number("kWh"),
                "nt_kwh": self._number("kWh"),
                "cost": self._number("Kč"),
            },
        )
        for key in ("paid", "fixed_cost"):
            schema[
                vol.Optional(
                    key,
                    description={"suggested_value": values[key]}
                    if key in values
                    else {},
                )
            ] = self._number("Kč")
        schema[vol.Required("edit_months", default=False)] = bool
        schema[vol.Required("clear_months", default=False)] = bool
        months = row.get("months", [])
        return self.async_show_form(
            step_id="document_bill",
            errors=errors,
            data_schema=vol.Schema(schema),
            description_placeholders={"months": str(len(months))},
        )

    @staticmethod
    def _number(unit):
        return selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=1e12,
                step="any",
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement=unit,
            )
        )

    @staticmethod
    def _document_fields(values, fields):
        return {
            vol.Required(
                k, description={"suggested_value": values[k]} if k in values else {}
            ): field
            for k, field in fields.items()
        }

    async def async_step_document_months(self, user_input=None):
        """Jen celé měsíce faktury. Neuvedené dvojice nejsou nulová spotřeba."""
        from .settlement import month_starts

        start, end = period(self._document)
        months = [
            d
            for d in month_starts(start, end)
            if d >= start
            and (d.replace(day=28) + timedelta(days=4)).replace(day=1)
            <= end + timedelta(days=1)
        ]
        errors = {}
        if user_input is not None:
            try:
                rows = []
                for i, month in enumerate(months, 1):
                    nt, vt = user_input.get(f"nt_{i}"), user_input.get(f"vt_{i}")
                    if nt is None and vt is None:
                        continue
                    if nt is None or vt is None:
                        raise ValueError("invalid_bill_months")
                    rows.append(
                        {"month": month.strftime("%Y-%m"), "nt_kwh": nt, "vt_kwh": vt}
                    )
                self._document["months"] = rows
                return self._document_save()
            except (ValueError, KeyError, TypeError) as err:
                errors["base"] = (
                    str(err) if isinstance(err, ValueError) else "invalid_documents"
                )
        saved = {m["month"]: m for m in self._document.get("months", [])}
        fields, placeholders = {}, {}
        for i, month in enumerate(months, 1):
            placeholders[f"month_{i}"] = month.strftime("%m/%Y")
            row = saved.get(month.strftime("%Y-%m"), {})
            for tariff in ("nt", "vt"):
                key = f"{tariff}_{i}"
                value = (user_input or {}).get(key, row.get(f"{tariff}_kwh"))
                fields[
                    vol.Optional(
                        key,
                        description={"suggested_value": value}
                        if value is not None
                        else {},
                    )
                ] = self._number("kWh")
        return self.async_show_form(
            step_id="document_months",
            errors=errors,
            data_schema=vol.Schema(fields),
            description_placeholders=placeholders,
        )

    async def async_step_document_profile(self, user_input=None):
        """Všechny složky jsou explicitní ceny s DPH; nenalezené sazby se nedoplňují."""
        errors = {}
        row = self._document
        if user_input is not None:
            self._document = {
                **row,
                **{k: user_input[k] for k in ("source", "start", "end")},
                "rates": {
                    **row.get("rates", {}),
                    **{k: user_input[k] for k in RATE_KEYS},
                },
            }
            try:
                return self._document_save()
            except (ValueError, KeyError, TypeError) as err:
                errors["base"] = (
                    str(err) if isinstance(err, ValueError) else "invalid_documents"
                )
        values = user_input or {**row, **row.get("rates", {})}
        fields = {
            "source": str,
            "start": selector.DateSelector(),
            "end": selector.DateSelector(),
        }
        fields.update(
            {
                k: self._number("Kč/měsíc" if k.endswith("monthly") else "Kč/kWh")
                for k in RATE_KEYS
            }
        )
        info = row.get("import_metadata", {})
        preview = (
            f"Zdroj: {info.get('source', '')} · Sazba: {info.get('rate', '')} · "
            f"Jistič: {info.get('breaker', '')} · Obchodní ceny od: {info.get('trade_effective', '')} · "
            f"Distribuce od: {info.get('distribution_effective', '')} · "
            f"POZE odhadnuta podle ročního odběru: {'ano' if info.get('poze_estimated') == 'yes' else 'ne'}"
            if info
            else "Ruční zadání; hodnoty ověřte podle podkladu."
        )
        return self.async_show_form(
            step_id="document_profile",
            errors=errors,
            data_schema=vol.Schema(self._document_fields(values, fields)),
            description_placeholders={"import_info": preview},
        )

    async def async_step_document_delete(self, user_input=None):
        """Odstranění vyžaduje potvrzení; archiv ověřených nákladů zůstává."""
        errors = {}
        if user_input is not None:
            if not user_input.get("confirm"):
                return await self.async_step_accounting_documents()
            try:
                return self._document_save(delete=True)
            except ValueError as err:
                errors["base"] = str(err)
        return self.async_show_form(
            step_id="document_delete",
            errors=errors,
            data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
            description_placeholders={"period": bill_key(self._document)},
        )

    async def async_step_estimate_settings(self, user_input=None):
        """Výběr zdroje současně povoluje náhradní ocenění; výchozí je vypnuto."""
        bills = self._document_rows("bill")
        errors = {}
        if user_input is not None:
            selected = user_input["estimate_bill"]
            try:
                ratio, _ = selected_ratio(
                    bills,
                    selected,
                    date.fromisoformat(self._accounting_values()["billing_start"]),
                )
                if selected and ratio is None:
                    raise ValueError("estimate_bill_invalid")
                self._pending_options["estimate_bill"] = selected
                return self._finish_options()
            except (ValueError, KeyError, TypeError):
                errors["base"] = "estimate_bill_invalid"
        choices = [{"value": "", "label": "Vypnuto – pouze úplné ocenění historie"}]
        for row in bills:
            choices.append(
                {"value": bill_key(row), "label": f"{row['start']} → {row['end']}"}
            )
        return self.async_show_form(
            step_id="estimate_settings",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "estimate_bill",
                        default=self._accounting_values().get("estimate_bill", ""),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=choices)
                    ),
                }
            ),
        )

    async def async_step_accounting_check(self, user_input=None):
        """Čte poslední runtime výsledek; tlačítko používá existující zamčenou službu."""
        errors = {}
        if user_input and user_input.get("recalculate"):
            try:
                await self.hass.services.async_call(
                    DOMAIN,
                    "backfill_accounting",
                    {"entry_id": self._config_entry.entry_id},
                    blocking=True,
                )
            except HomeAssistantError:
                errors["base"] = "recalculation_unavailable"
        runtime = getattr(self._config_entry, "runtime_data", None)
        accounting = getattr(getattr(runtime, "billing", None), "settlement", None)
        meta = accounting.result.get("metadata", {}) if accounting else {}
        state = accounting.backfill_state if accounting else {}
        lines = [
            f"Stav přepočtu: {state.get('status', 'nenačteno')}",
            f"Bloky: {state.get('processed_blocks', 0)} / {state.get('total_blocks', 0)}",
            f"Neoceněná historie: {meta.get('unpriced_period_kwh', 'neověřeno')} kWh",
            f"Dnešní neoceněný odběr: {meta.get('daily_unpriced_kwh', 'neověřeno')} kWh",
            f"Pokrytí historie: {meta.get('period_energy_coverage', 'neověřeno')}",
            f"Dny bez stálých sazeb: {meta.get('missing_fee_days', 'neověřeno')}",
        ]
        from .accounting_messages import REASONS

        for gap in meta.get("unpriced_intervals", []):
            lines.append(
                f"{gap['start']} → {gap['end']}: {gap['kwh']:.3f} kWh · "
                + REASONS.get(gap["reason"], gap["reason"])
            )
        for gap in state.get("gaps", []):
            lines.append(
                f"{gap['start']} → {gap['end']}: "
                + ", ".join(REASONS.get(r, r) for r in gap.get("reasons", []))
            )
        if meta.get("forecast_blockers"):
            lines.extend(REASONS.get(r, r) for r in meta["forecast_blockers"])
        return self.async_show_form(
            step_id="accounting_check",
            errors=errors,
            data_schema=vol.Schema({vol.Required("recalculate", default=False): bool}),
            description_placeholders={
                "report": "\n\n".join(lines)
                + "\n\nPro obnovení výsledku znovu otevřete tuto kontrolu."
            },
        )
