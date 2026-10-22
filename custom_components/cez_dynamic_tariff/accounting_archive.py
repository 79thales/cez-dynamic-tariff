"""Ověřené hodinové podklady; žádný zápis do cizích statistik nebo měřidel."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import date, timedelta
from math import isfinite

SCHEMA_VERSION = 1


def fingerprint(value):
    """Stabilní otisk identity/revize; pořadí klíčů nemění význam vstupu."""
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False).encode()
    ).hexdigest()


def number(value):
    """Nula je validní číslo, None/NaN/boolean nejsou měřením."""
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return result if isfinite(result) else None


def normalize_rows(rows, *, seconds=3600, nonnegative=True):
    """UTC intervaly bez duplicit; konfliktní klíč se celý odmítne.

    Vstup jsou HA statistiky s change v již převedených kWh/CZK. Výstup
    je seřazená kopie a počty odmítnutí/shod/konfliktů. Nepřítomné change
    není nula. Povolujeme záporné finanční opravy jen při výslovné volbě.
    """
    found, conflicts = {}, set()
    counts = {"duplicates": 0, "invalid": 0, "conflicts": 0}
    for row in rows:
        if not isinstance(row, dict):
            counts["invalid"] += 1
            continue
        stamp, amount = number(row.get("start")), number(row.get("change"))
        end = number(row.get("end", stamp + seconds if stamp is not None else None))
        if (
            stamp is None
            or amount is None
            or end is None
            or stamp % seconds != 0
            or end - stamp != seconds
            or (nonnegative and amount < 0)
            or ("state" in row and number(row["state"]) is None)
        ):
            counts["invalid"] += 1
            continue
        normalized = {"start": stamp, "end": end, "change": amount}
        if "state" in row:
            normalized["state"] = number(row["state"])
        if stamp in found:
            if found[stamp] == normalized:
                counts["duplicates"] += 1
            else:
                conflicts.add(stamp)
        else:
            found[stamp] = normalized
    counts["conflicts"] = len(conflicts)
    return [found[k] for k in sorted(found) if k not in conflicts], counts


class AccountingArchive:
    """Energie podle zdroje, náklady podle revize a nezávislé rozvrhy HDO.

    Klíčem hodin je UTC epoch sekund, nikoli místní hodina (DST). Cena je
    pouze variabilní Kč bez stálých plateb/EDC. Shodná energie a revize
    jsou podmínkou opětovného použití. Aktualizace nahrazuje stejný klíč.
    Snapshot pro HA Store je kopie, aby probíhající zápis nebyl mutován.
    """

    def __init__(self, saved=None):
        self.data = {
            "schema": SCHEMA_VERSION,
            "energy": {},
            "costs": {},
            "schedules": {},
            "backfill": {},
            "runs": [],
            "bindings": {},
        }
        if saved is not None:
            if not isinstance(saved, dict) or saved.get("schema") != SCHEMA_VERSION:
                raise ValueError("archive_schema_invalid")
            for key in ("energy", "costs", "schedules", "backfill"):
                if not isinstance(saved.get(key), dict):
                    raise TypeError("archive_structure_invalid")
            if not isinstance(saved.get("runs"), list) or len(saved["runs"]) > 20:
                raise ValueError("archive_runs_invalid")
            # Ověříme i vnořené údaje před použitím; chyba nesmí spustit
            # přepsání poškozeného souboru prázdnou strukturou.
            for records in saved["energy"].values():
                if not isinstance(records, dict):
                    raise TypeError("archive_energy_invalid")
                for stamp, amount in records.items():
                    if (
                        number(stamp) is None
                        or float(stamp) % 3600
                        or number(amount) is None
                        or amount < 0
                    ):
                        raise ValueError("archive_energy_invalid")
            for records in saved["costs"].values():
                if not isinstance(records, dict):
                    raise TypeError("archive_cost_invalid")
                for stamp, row in records.items():
                    if (
                        number(stamp) is None
                        or float(stamp) % 3600
                        or not isinstance(row, dict)
                        or any(
                            number(row.get(k)) is None or row[k] < 0
                            for k in ("energy", "cost")
                        )
                        or row.get("source")
                        not in {"monetary_statistic", "historical_hdo"}
                    ):
                        raise ValueError("archive_cost_invalid")
            for records in saved["schedules"].values():
                if not isinstance(records, dict):
                    raise TypeError("archive_schedule_invalid")
                for updated, rows in records.items():
                    if number(updated) is None or not isinstance(rows, list):
                        raise ValueError("archive_schedule_invalid")
                    cursor = None
                    for row in rows:
                        if (
                            not isinstance(row, dict)
                            or any(number(row.get(k)) is None for k in ("start", "end"))
                            or row["end"] <= row["start"]
                            or row.get("tariff") not in {"NT", "VT"}
                            or (cursor is not None and row["start"] < cursor)
                        ):
                            raise ValueError("archive_schedule_invalid")
                        cursor = row["end"]
            self.data = copy.deepcopy(saved)
            bindings = self.data.setdefault("bindings", {})
            if not isinstance(bindings, dict) or any(
                not isinstance(v, dict) or not isinstance(v.get("registry_id"), str)
                for v in bindings.values()
            ):
                raise ValueError("archive_bindings_invalid")
            state = self.data["backfill"]
            if state:
                if (
                    state.get("status")
                    not in {
                        "idle",
                        "running",
                        "paused",
                        "completed",
                        "incomplete",
                        "failed",
                    }
                    or not isinstance(state.get("run_id"), str)
                    or not isinstance(state.get("revision"), str)
                    or any(
                        not isinstance(state.get(k), int) or state[k] < 0
                        for k in ("processed_blocks", "total_blocks")
                    )
                    or not isinstance(state.get("gaps", []), list)
                ):
                    raise ValueError("archive_cursor_invalid")
                first, last, cursor = (
                    date.fromisoformat(state[k]) for k in ("start", "end", "cursor")
                )
                if first > last or not first <= cursor <= last + timedelta(days=1):
                    raise ValueError("archive_cursor_invalid")

    def snapshot(self):
        return copy.deepcopy(self.data)

    def merge_energy(self, source, rows):
        """Vrací počty upsertů; kompletní archiv nikdy nemaže prázdná odpověď."""
        records = self.data["energy"].setdefault(source, {})
        counts = {"new": 0, "updated": 0, "unchanged": 0}
        for row in rows:
            key = str(int(row["start"]))
            old = records.get(key)
            counts[
                "new"
                if old is None
                else "unchanged"
                if old == row["change"]
                else "updated"
            ] += 1
            records[key] = row["change"]
        return counts

    def energy_rows(self, source, left, right):
        return [
            {"start": float(k), "end": float(k) + 3600, "change": v}
            for k, v in sorted(
                self.data["energy"].get(source, {}).items(), key=lambda p: int(p[0])
            )
            if left <= float(k) < right
        ]

    def cost(self, revision, stamp, energy):
        row = self.data["costs"].get(revision, {}).get(str(int(stamp)))
        return row["cost"] if row and abs(row["energy"] - energy) < 1e-9 else None

    def save_cost(self, revision, stamp, energy, cost, source):
        if number(energy) is None or number(cost) is None or energy < 0 or cost < 0:
            return
        self.data["costs"].setdefault(revision, {})[str(int(stamp))] = {
            "energy": energy,
            "cost": cost,
            "source": source,
        }

    def save_schedule(self, source, updated, rows):
        """Spoj kompatibilní části stejné revize, rozpor tarifu odmítni.

        Zdroj po půlnoci odstraní minulý den, aniž změní last_update.
        Zkrácení či doplnění pokrytí není změna tarifu. UTC intervaly proto
        sjednotíme; rozdílný tarif ve společném nenulovém čase je skutečný
        konflikt. Při konfliktu neprovedeme žádný zápis a archiv zůstane celý.
        """
        records = self.data["schedules"].setdefault(source, {})
        key = str(updated.timestamp())
        encoded = [
            {"start": r.start.timestamp(), "end": r.end.timestamp(), "tariff": r.tariff}
            for r in rows
        ]
        combined = sorted(
            records.get(key, []) + encoded,
            key=lambda r: (r["start"], r["end"]),
        )
        merged = []
        for row in combined:
            if merged and row["start"] < merged[-1]["end"] and row["tariff"] != merged[-1]["tariff"]:
                return False
            if merged and row["start"] <= merged[-1]["end"] and row["tariff"] == merged[-1]["tariff"]:
                merged[-1]["end"] = max(merged[-1]["end"], row["end"])
            else:
                merged.append(dict(row))
        records[key] = merged
        return True

    def prune(self, horizon):
        """Retence podle nejstarší potřebné hranice; prázdné namespace odstraníme."""
        for section in ("energy", "costs"):
            for identity, records in list(self.data[section].items()):
                self.data[section][identity] = {
                    k: v for k, v in records.items() if float(k) >= horizon
                }
                if not self.data[section][identity]:
                    del self.data[section][identity]
        for identity, records in list(self.data["schedules"].items()):
            self.data["schedules"][identity] = {
                k: v for k, v in records.items() if any(r["end"] > horizon for r in v)
            }
