"""Archiv testujeme skutečnými vstupy, nikoli kopiemi implementačních větví."""

import importlib.util
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location(
    "archive_test",
    Path(__file__).parents[1]
    / "custom_components/cez_dynamic_tariff/accounting_archive.py",
)
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
STAMP = datetime(2026, 10, 1, tzinfo=UTC).timestamp()


class ArchiveTests(unittest.TestCase):
    def test_duplicates_conflicts_units_and_nonfinite_are_not_counted(self):
        row = {"start": STAMP, "change": 12.9}
        rows, counts = a.normalize_rows(
            [
                row,
                row,
                {"start": STAMP + 3600, "change": 0},
                {"start": STAMP + 7200, "change": float("nan")},
            ]
        )
        self.assertEqual([r["change"] for r in rows], [12.9, 0])
        self.assertEqual(counts, {"duplicates": 1, "invalid": 1, "conflicts": 0})
        rows, counts = a.normalize_rows([row, {**row, "change": 13}])
        self.assertEqual(rows, [])
        self.assertEqual(counts["conflicts"], 1)
        rows, counts = a.normalize_rows(
            [
                {**row, "change": True},
                {**row, "end": STAMP + 1800},
                {**row, "state": None},
            ]
        )
        self.assertEqual(rows, [])
        self.assertEqual(counts["invalid"], 3)

    def test_replay_overlap_correction_and_restart_are_idempotent(self):
        archive = a.AccountingArchive()
        rows, _ = a.normalize_rows([{"start": STAMP, "change": 12.9}])
        self.assertEqual(archive.merge_energy("meter", rows)["new"], 1)
        archive.save_cost("price1", STAMP, 12.9, 60, "historical_hdo")
        saved = archive.snapshot()
        archive.merge_energy("meter", rows)
        archive.save_cost("price1", STAMP, 12.9, 60, "historical_hdo")
        self.assertEqual(saved, archive.snapshot())
        restored = a.AccountingArchive(saved)
        self.assertEqual(restored.cost("price1", STAMP, 12.9), 60)
        self.assertIsNone(restored.cost("price1", STAMP, 13))
        self.assertIsNone(restored.cost("price2", STAMP, 12.9))
        self.assertEqual(restored.energy_rows("another_meter", STAMP, STAMP + 3600), [])
        restored.merge_energy("meter", [{**rows[0], "change": 13}])
        self.assertEqual(len(restored.energy_rows("meter", STAMP, STAMP + 3600)), 1)
        restored.merge_energy("meter", [])
        self.assertEqual(
            restored.energy_rows("meter", STAMP, STAMP + 3600)[0]["change"], 13
        )

    def test_same_hdo_revision_cannot_silently_change(self):
        archive = a.AccountingArchive()
        updated = datetime.fromtimestamp(STAMP, UTC)
        rows = [
            SimpleNamespace(
                start=updated,
                end=datetime.fromtimestamp(STAMP + 3600, UTC),
                tariff="NT",
            )
        ]
        self.assertTrue(archive.save_schedule("hdo", updated, rows))
        self.assertTrue(archive.save_schedule("hdo", updated, rows))
        rows[0].tariff = "VT"
        self.assertFalse(archive.save_schedule("hdo", updated, rows))
        self.assertEqual(
            archive.data["schedules"]["hdo"][str(STAMP)][0]["tariff"], "NT"
        )

    def test_corrupt_schema_records_and_snapshot_mutation(self):
        archive = a.AccountingArchive()
        archive.merge_energy("meter", [{"start": STAMP, "change": 0}])
        saved = archive.snapshot()
        saved["energy"]["meter"][str(int(STAMP))] = float("nan")
        self.assertEqual(
            archive.energy_rows("meter", STAMP, STAMP + 3600)[0]["change"], 0
        )
        with self.assertRaises(ValueError):
            a.AccountingArchive(saved)
        with self.assertRaises(ValueError):
            a.AccountingArchive({"schema": 999})

    def test_dst_repeated_hour_has_distinct_keys(self):
        archive = a.AccountingArchive()
        first = datetime(2026, 10, 25, 0, tzinfo=UTC).timestamp()
        rows, _ = a.normalize_rows(
            [{"start": first, "change": 1}, {"start": first + 3600, "change": 2}]
        )
        archive.merge_energy("meter", rows)
        self.assertEqual(
            sum(r["change"] for r in archive.energy_rows("meter", first, first + 7200)),
            3,
        )
