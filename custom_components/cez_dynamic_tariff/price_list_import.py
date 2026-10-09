"""Home Assistant PDF upload/download adapter with bounded reads."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urljoin

from aiohttp import ClientError, ClientTimeout
from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .price_list import (
    MAX_PDF_BYTES,
    PriceListError,
    parse_price_list,
    validate_cez_url,
)


def _read_uploaded(hass, file_id):
    """Read through the HA upload store; never accept arbitrary filesystem paths."""
    try:
        with process_uploaded_file(hass, file_id) as path:
            with Path(path).open("rb") as stream:
                pdf = stream.read(MAX_PDF_BYTES + 1)
            return pdf, Path(path).name
    except (OSError, ValueError) as err:
        raise PriceListError("invalid_price_list_pdf") from err


async def _download(hass, url):
    url = validate_cez_url(url)
    session = async_get_clientsession(hass)
    try:
        # Explicitly check every redirect before issuing the next request.
        for _ in range(4):
            async with session.get(
                url, allow_redirects=False, timeout=ClientTimeout(total=20)
            ) as response:
                if response.status in (301, 302, 303, 307, 308):
                    url = validate_cez_url(
                        urljoin(url, response.headers.get("Location", ""))
                    )
                    continue
                response.raise_for_status()
                length = response.headers.get("Content-Length", "")
                if length.isdigit() and int(length) > MAX_PDF_BYTES:
                    raise PriceListError("price_list_too_large")
                content = bytearray()
                async for chunk in response.content.iter_chunked(65536):
                    content.extend(chunk)
                    if len(content) > MAX_PDF_BYTES:
                        raise PriceListError("price_list_too_large")
                return bytes(content), url
    except (ClientError, TimeoutError) as err:
        raise PriceListError("cannot_download_price_list") from err
    raise PriceListError("cannot_download_price_list")


async def async_import_price_list(hass, user_input):
    """Only the proposed rates are returned; the caller owns review and saving."""
    if user_input.get("price_list_file"):
        pdf, source = await hass.async_add_executor_job(
            _read_uploaded, hass, user_input["price_list_file"]
        )
    else:
        pdf, source = await _download(hass, user_input["price_list_url"])
    result = await hass.async_add_executor_job(
        parse_price_list,
        pdf,
        user_input["distribution_rate"],
        user_input["breaker_amperes"],
        user_input["breaker_phases"],
        user_input["annual_import_kwh"],
    )
    return result, source
