"""Suggest the existing EDC monetary statistic, never a kWh or price sensor."""


def income_statistic_id(state, entity_id):
    """Use the same existing monetary history for accounting and Energy checks."""
    if state is None:
        return entity_id
    return (
        state.attributes.get("energy_revenue_statistic_id")
        or state.attributes.get("hourly_statistic_id")
        or entity_id
    )


def suggest_edc_income(states):
    candidates = [
        state
        for state in states
        if state.entity_id.startswith("sensor.")
        and isinstance(state.attributes.get("energy_revenue_statistic_id"), str)
        and state.attributes["energy_revenue_statistic_id"].startswith("edc_sharing:")
    ]
    aggregate = [
        s
        for s in candidates
        if s.entity_id.endswith("_edc_data_available_since")
        or ("history_backfill_status" in s.attributes and not s.attributes.get("role"))
    ]
    candidates = aggregate or [s for s in candidates if not s.attributes.get("role")]
    if (
        not candidates
        or len({s.attributes["energy_revenue_statistic_id"] for s in candidates}) != 1
    ):
        return None
    # Multiple diagnostic entities can point to the same statistic. Select one
    # representative, rather than summing duplicate financial sources.
    return min(
        candidates,
        key=lambda s: (not s.entity_id.endswith("_data_available_since"), s.entity_id),
    ).entity_id
