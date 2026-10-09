"""Read existing Energy compensation preferences without changing them."""


def compensation_statistics(preferences):
    """Support both legacy grid flows and the unified grid configuration."""
    result = set()
    for source in (preferences or {}).get("energy_sources", []):
        if source.get("type") != "grid":
            continue
        for flow in [source, *source.get("flow_to", [])]:
            statistic = flow.get("stat_compensation")
            if isinstance(statistic, str) and statistic:
                result.add(statistic)
    return result


async def async_income_in_energy(hass, statistic):
    """None means preferences could not be checked, not an unused source."""
    if not statistic or "energy" not in hass.config.components:
        return False
    from homeassistant.components.energy.data import async_get_manager
    from homeassistant.exceptions import HomeAssistantError

    try:
        manager = await async_get_manager(hass)
    except (HomeAssistantError, OSError):
        return None
    return statistic in compensation_statistics(manager.data)
