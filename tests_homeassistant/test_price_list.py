"""Real HA upload, review, persistence and restricted download regressions."""

import importlib.util
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from homeassistant.components.file_upload import FileUploadData
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cez_dynamic_tariff.const import DOMAIN
from custom_components.cez_dynamic_tariff.price_list import (
    MAX_PDF_BYTES,
    PriceListError,
)
from custom_components.cez_dynamic_tariff.price_list_import import _download
from custom_components.cez_dynamic_tariff.pricing import PROFILE_DEFAULTS

spec = importlib.util.spec_from_file_location(
    "_ha_price_list_fixture", Path(__file__).parents[1] / "tests/price_list_fixture.py"
)
fixture_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture_module)
make_pdf = fixture_module.make_pdf


def upload(hass, tmp_path, pdf):
    file_id = uuid4().hex
    folder = tmp_path / file_id
    folder.mkdir()
    (folder / "cez-test.pdf").write_bytes(pdf)
    hass.data["file_upload"] = FileUploadData(tmp_path, {file_id: "cez-test.pdf"})
    return file_id, folder


async def start_import(hass):
    original = {
        **PROFILE_DEFAULTS,
        "pricing_enabled": True,
        "dynamic_pricing": True,
        "base_price_kwh": 2.5,
        "include_holidays": False,
        "winter_workday_schedule": "00:00=-20, 08:00=+30",
        "hdo_entity": "binary_sensor.existing_hdo",
        "other_monthly": 12.5,
    }
    entry = MockConfigEntry(
        domain=DOMAIN, title="Tariff", unique_id=DOMAIN, data={}, options=original
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "base_price_kwh": 99,
            "include_holidays": True,
            "reset_schedules": True,
            "configure_pricing": False,
            "import_price_list": True,
        },
    )
    assert result["step_id"] == "price_list"
    return entry, original, result


async def test_upload_review_then_save_preserves_original_settings(
    hass, tmp_path, freezer
):
    freezer.move_to("2026-10-09T06:00:00Z")
    with patch("custom_components.cez_dynamic_tariff.async_reload_entry"):
        entry, original, result = await start_import(hass)
        file_id, folder = upload(hass, tmp_path, make_pdf(trade_vt=4000))
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "price_list_file": file_id,
                "distribution_rate": "D57d",
                "breaker_amperes": 32,
                "breaker_phases": 3,
                "annual_import_kwh": 5500,
            },
        )
        assert result["step_id"] == "price_list_review"
        assert not folder.exists()
        assert entry.options == original
        assert result["description_placeholders"]["trade_effective"] == "2026-01-30"
        values = {key.schema: key.default() for key in result["data_schema"].schema}
        assert values["trade_vt"] == 4
        assert values["breaker_monthly"] == 859.10
        assert values["other_monthly"] == 12.5
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=values
        )
        assert result["errors"] == {"base": "confirm_price_list"}
        assert entry.options == original
        values["confirm_price_list"] = True
        values["trade_nt"] = 3.10
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=values
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()
        assert entry.options["trade_vt"] == 4
        assert entry.options["trade_nt"] == 3.1
        assert entry.options["price_list_source"] == "cez-test.pdf"
        assert entry.options["price_list_rates_edited"] is True
        for key in (
            "base_price_kwh",
            "include_holidays",
            "winter_workday_schedule",
            "hdo_entity",
            "dynamic_pricing",
            "pricing_enabled",
            "other_monthly",
        ):
            assert entry.options[key] == original[key]


async def test_invalid_future_and_double_sources_do_not_save(hass, tmp_path, freezer):
    freezer.move_to("2026-10-09T06:00:00Z")
    entry, original, result = await start_import(hass)
    for pdf, error in (
        (b"bad", "invalid_price_list_pdf"),
        (make_pdf(effective="1. 1. 2099"), "future_price_list"),
    ):
        file_id, _ = upload(hass, tmp_path, pdf)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "price_list_file": file_id,
                "distribution_rate": "D57d",
                "breaker_amperes": 25,
                "breaker_phases": 3,
                "annual_import_kwh": 0,
            },
        )
        assert result["errors"] == {"base": error}
        assert entry.options == original
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "price_list_file": uuid4().hex,
            "price_list_url": "https://www.cez.cz/test.pdf",
            "distribution_rate": "D57d",
            "breaker_amperes": 25,
            "breaker_phases": 3,
            "annual_import_kwh": 0,
        },
    )
    assert result["errors"] == {"base": "choose_one_price_list_source"}
    assert entry.options == original


async def test_download_only_follows_cez_redirects(hass, aioclient_mock):
    url = "https://www.cez.cz/original.pdf"
    target = "https://www.cez.cz/updated.pdf"
    pdf = make_pdf()
    aioclient_mock.get(url, status=302, headers={"Location": target})
    aioclient_mock.get(target, content=pdf)
    assert await _download(hass, url) == (pdf, target)
    assert aioclient_mock.call_count == 2
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        url, status=302, headers={"Location": "http://192.168.1.1/private.pdf"}
    )
    with pytest.raises(PriceListError, match="invalid_price_list_url"):
        await _download(hass, url)
    assert aioclient_mock.call_count == 1


async def test_download_rejects_oversized_pdf(hass, aioclient_mock):
    url = "https://www.cez.cz/oversized.pdf"
    aioclient_mock.get(url, content=b"%PDF-" + b"x" * MAX_PDF_BYTES)
    with pytest.raises(PriceListError, match="price_list_too_large"):
        await _download(hass, url)
