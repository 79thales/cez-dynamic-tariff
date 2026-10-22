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
    Tento hook je krytý testem se skutečným Store a chybou jeho zapisovače.
    """

    async def _async_write_data(self, path, data):
        try:
            await super()._async_write_data(path, data)
        except (json_util.SerializationError, WriteError) as err:
            raise HomeAssistantError("accounting_archive_write_failed") from err
