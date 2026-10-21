"""HA Store s potvrzením zápisu potřebným pro spolehlivý kurzor backfillu."""

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.util import json as json_util
from homeassistant.util.file import WriteError


class AccountingStore(Store):
    """Propaguje chybu zápisu, kterou běžný Store pouze zaloguje.

    Atomické ukládání, souběh a konečný zápis při shutdownu zajišťuje HA.
    Převod chyby v úzkém I/O hooku zajistí, že caller neposune/potvrdí
    kurzor při neúspěšném zápisu. Původní výjimka zůstane v tracebacku.
    HA 2025 předává hooku cestu a data, HA 2026 pouze data. Argumenty
    předáme beze změny nadřazenému Store téže instalace; nepřepočítáváme
    cestu ani nepřeskakujeme jeho zámek a atomický zápis. Testy pokrývají
    oba tvary volání, skutečné opětovné načtení i chybu zapisovače.
    """

    async def _async_write_data(self, *args):
        try:
            await super()._async_write_data(*args)
        except (json_util.SerializationError, WriteError) as err:
            raise HomeAssistantError("accounting_archive_write_failed") from err
